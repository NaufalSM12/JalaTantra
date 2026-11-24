"""JalaTantra HTTP API. Device checks and automation run only in the worker."""
import ipaddress
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request

import ai
import db
import metrics
import policy
import security
from security import audit, fail, payload, require_admin, require_operator, text

app = Flask(__name__, static_folder='static', static_url_path='/static')
security.install(app)
ACTIVE = ('awaiting_approval', 'queued', 'running')
DEVICE_FIELDS = ('name', 'address', 'environment', 'kind', 'site', 'services', 'notes', 'parent_id', 'exporter_port')
JOB_SELECT = ('SELECT j.*,d.name AS device_name,u.username AS requester,au.username AS approver FROM jobs j '
              'JOIN devices d ON d.id=j.device_id JOIN users u ON u.id=j.requested_by '
              'LEFT JOIN users au ON au.id=j.approved_by ')
INCIDENT_SELECT = ('SELECT i.*,d.name AS device_name,ua.username AS assignee FROM incidents i '
                   'JOIN devices d ON d.id=i.device_id LEFT JOIN users ua ON ua.id=i.assigned_to ')
AI_WINDOW_SECONDS = 600
AI_REQUEST_LIMIT = 30
_ai_requests = {}


def environment(required=False):
    value = request.args.get('environment')
    if value is None and not required:
        value = 'demo'
    if value not in ('demo', 'real'):
        fail('Lingkungan harus demo atau real.')
    return value


def positive_id(value, label='ID perangkat'):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 9223372036854775807:
        fail(label + ' tidak valid.')
    return value


def query_id():
    raw = request.args.get('device_id')
    if raw is None:
        return None
    if not re.fullmatch(r'[0-9]{1,19}', raw):
        fail('ID perangkat tidak valid.')
    return positive_id(int(raw))


def device(identifier, cursor=None, include_archived=False):
    positive_id(identifier)
    sql = 'SELECT * FROM devices WHERE id=%s'
    if not include_archived:
        sql += ' AND archived_at IS NULL'
    if cursor is None:
        row = db.one(sql, (identifier,))
    else:
        cursor.execute(sql + ' FOR UPDATE', (identifier,))
        row = cursor.fetchone()
    if not row:
        fail('Perangkat tidak ditemukan.', 404)
    return row


def public_device(row, config=None):
    result = db.public(row)
    config = db.settings() if config is None else config
    result['managed'] = row['environment'] == 'demo' or bool(policy.managed_host(row['address'], config))
    result['checks_allowed'] = row['environment'] == 'demo' or policy.allowed_address(row['address'], config)
    result['auto_approve'] = bool(row.get('auto_approve'))
    checked = row.get('last_checked_at')
    if checked is None:
        result['status'] = 'unknown'
    else:
        now = datetime.now(timezone.utc)
        checked = checked.replace(tzinfo=timezone.utc) if checked.tzinfo is None else checked
        age = (now - checked).total_seconds()
        if age > 180 or age < 0:
            result['status'] = 'unknown'
    return result


def active_jobs(cursor, identifier):
    cursor.execute('SELECT id FROM jobs WHERE device_id=%s AND status IN (%s,%s,%s) LIMIT 1 FOR UPDATE',
                   (identifier, *ACTIVE))
    if cursor.fetchone():
        fail('Perangkat masih memiliki pekerjaan aktif.', 409)


def parent_valid(cursor, parent_id, env, own_id=None):
    seen = {own_id}
    while parent_id is not None:
        if parent_id in seen:
            fail('Relasi induk tidak boleh membentuk siklus.', 409)
        seen.add(parent_id)
        cursor.execute('SELECT id,parent_id,environment,archived_at FROM devices WHERE id=%s FOR UPDATE', (parent_id,))
        parent = cursor.fetchone()
        if not parent or parent['archived_at'] is not None:
            fail('Perangkat induk tidak ditemukan.', 400)
        if parent['environment'] != env:
            fail('Perangkat induk harus berada di lingkungan yang sama.')
        parent_id = parent['parent_id']


def validate_device(data, current=None):
    result = {} if current is None else {key: current[key] for key in DEVICE_FIELDS if key != 'services'}
    if current is not None:
        result['services'] = json.loads(current['services_json'])
    result.update(data)
    if current is None:
        result.setdefault('kind', 'server')
        result.setdefault('site', '')
        result.setdefault('notes', '')
        result.setdefault('services', [])
        result.setdefault('parent_id', None)
        result.setdefault('exporter_port', 9100)
    name = result.get('name')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', name):
        fail('Nama perangkat harus 1–80 karakter: huruf, angka, titik, garis bawah, atau tanda hubung.')
    address = result.get('address')
    if not isinstance(address, str) or len(address) > 45 or '%' in address:
        fail('Alamat harus berupa IP literal yang valid.')
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        fail('Alamat harus berupa IP literal, bukan nama host.')
    if ip.is_multicast or ip.is_unspecified or ip.is_link_local:
        fail('Alamat multicast, kosong, atau link-local tidak diizinkan.')
    result['address'] = str(ip)
    if result.get('environment') not in ('demo', 'real'):
        fail('Lingkungan harus demo atau real.')
    if result['kind'] not in ('server', 'router', 'switch', 'storage'):
        fail('Jenis perangkat tidak valid.')
    result['site'] = text(result['site'], 'Lokasi', 100)
    result['notes'] = text(result['notes'], 'Catatan', 4000)
    services = result['services']
    if (not isinstance(services, list) or len(services) > len(policy.SERVICES)
            or any(not isinstance(item, str) or item not in policy.SERVICES for item in services)
            or len(set(services)) != len(services)):
        fail('Daftar layanan tidak valid.')
    if result['parent_id'] is not None:
        positive_id(result['parent_id'], 'ID induk')
    port = result['exporter_port']
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        fail('Port exporter harus antara 1 dan 65535.')
    return result


def sync_demo_state(cursor, identifier, services, create=False):
    state = {}
    if not create:
        cursor.execute('SELECT services_json FROM demo_state WHERE device_id=%s FOR UPDATE', (identifier,))
        previous = cursor.fetchone()
        if previous:
            state = json.loads(previous['services_json'])
    state = {key: state.get(key, 1) for key in services}
    cursor.execute('INSERT INTO demo_state(device_id,online,services_json,disk_percent) VALUES(%s,%s,%s,%s) '
                   'ON DUPLICATE KEY UPDATE services_json=VALUES(services_json)',
                   (identifier, 1, json.dumps(state), 30))


def check_target(row, automation=False):
    if row['environment'] == 'demo':
        return
    config = db.settings()
    if not policy.allowed_address(row['address'], config):
        fail('Alamat belum terdaftar dalam jaringan yang diizinkan. Minta admin mendaftarkan jaringan perangkat.', 403)
    if automation and not policy.managed_host(row['address'], config):
        fail('Perangkat belum terdaftar sebagai host terkelola. Minta admin mendaftarkan host sebelum otomasi.', 403)


def validate_action(row, action, service):
    if not isinstance(action, str) or action not in policy.ACTIONS:
        fail('Aksi tidak diizinkan.')
    if action in policy.SERVICE_ACTIONS:
        if not isinstance(service, str) or service not in policy.SERVICES or service not in json.loads(row['services_json']):
            fail('Pilih layanan yang terdaftar pada perangkat.')
        if action == 'reload_service' and service not in policy.RELOADABLE_SERVICES:
            fail('Muat ulang hanya tersedia untuk DNS dan Prometheus yang mendukung reload aman.')
    elif service is not None:
        fail('Aksi ini tidak menerima layanan.')
    check_target(row, automation=True)


def public_incident(row):
    result = db.public(row)
    fingerprint = row.get('fingerprint') or ''
    result['category'] = 'metric' if ':anomaly:' in fingerprint else 'service' if fingerprint else 'manual'
    return result


def result_limit(default=100, maximum=500):
    raw = request.args.get('limit', str(default))
    if not re.fullmatch(r'[0-9]{1,3}', raw) or not 20 <= int(raw) <= maximum:
        fail(f'Batas hasil harus antara 20 dan {maximum}.')
    return int(raw)


def allow_ai_request():
    now = time.monotonic()
    entries = [stamp for stamp in _ai_requests.get(g.user['id'], []) if now - stamp < AI_WINDOW_SECONDS]
    if len(entries) >= AI_REQUEST_LIMIT:
        remaining = max(1, int(AI_WINDOW_SECONDS - (now - entries[0])))
        fail('Batas penggunaan asisten tercapai. Tunggu sebentar sebelum meminta analisis lagi.', 429,
             {'Retry-After': str(remaining)})
    entries.append(now)
    _ai_requests[g.user['id']] = entries


def public_job(identifier, cursor=None):
    if cursor is None:
        result = db.one(JOB_SELECT + 'WHERE j.id=%s', (identifier,))
    else:
        cursor.execute(JOB_SELECT + 'WHERE j.id=%s', (identifier,))
        result = cursor.fetchone()
    if not result:
        fail('Pekerjaan tidak ditemukan.', 404)
    return db.public(result)


def enqueue(identifier, action, service=None, is_check=False):
    with db.connection() as client, client.cursor() as cursor:
        target = device(identifier, cursor)
        if is_check:
            check_target(target)
        else:
            validate_action(target, action, service)
        # Device lock serializes requests with inventory edits and other enqueues.
        cursor.execute('SELECT id FROM jobs WHERE device_id=%s AND action=%s '
                       'AND status IN (%s,%s,%s) LIMIT 1 FOR UPDATE', (identifier, action, *ACTIVE))
        if cursor.fetchone():
            fail('Aksi yang sama masih aktif pada perangkat ini.', 409)
        auto = (not is_check and action in policy.AUTO_APPROVABLE
                and bool(target.get('auto_approve')))
        status = ('queued' if auto else
                  'awaiting_approval' if not is_check and policy.ACTIONS[action]['requires_approval'] else 'queued')
        cursor.execute('INSERT INTO jobs(device_id,environment,action,service,status,requested_by,approved_by,approved_at,device_updated_at,logs) '
                       'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                       (identifier, target['environment'], action, service, status, g.user['id'],
                        g.user['id'] if auto else None,
                        datetime.now(timezone.utc).replace(tzinfo=None) if auto else None,
                        target['updated_at'], ''))
        job_id = cursor.lastrowid
        audit(cursor, 'job_requested', target['environment'],
              ('Pekerjaan diminta: ' + action + ' (auto-approve perangkat aktif; eksekusi langsung).'
               if auto else 'Pekerjaan diminta: ' + action), identifier)
        result = public_job(job_id, cursor)
    return jsonify({'job': result}), 201


@app.get('/api/health')
def health():
    try:
        if db.one('SELECT 1 AS healthy')['healthy'] != 1:
            raise RuntimeError()
    except Exception:
        return jsonify({'error': 'Database belum tersedia.'}), 503
    return jsonify({'ok': True})


app.add_url_rule('/api/login', 'login', security.login, methods=['POST'])
app.add_url_rule('/api/logout', 'logout', security.logout, methods=['POST'])
app.add_url_rule('/api/password', 'password', security.change_password, methods=['POST'])


@app.get('/api/session')
def session():
    return jsonify(security.session_view())


@app.get('/api/catalog')
def catalog():
    config = db.settings()
    return jsonify({'services': list(policy.SERVICES.values()), 'actions': list(policy.ACTIONS.values()),
                    'allowed_networks': config.get('allowed_networks', ['127.0.0.0/8']),
                    'managed_addresses': list(config.get('managed_hosts', {'127.0.0.1': 'local'}))})


@app.get('/api/devices')
def list_devices():
    env = environment()
    search = text(request.args.get('search', ''), 'Pencarian', 100)
    sql = 'SELECT * FROM devices WHERE environment=%s AND archived_at IS NULL'
    params = [env]
    if search:
        sql += ' AND (LOCATE(%s,name)>0 OR LOCATE(%s,address)>0 OR LOCATE(%s,site)>0)'
        params.extend([search] * 3)
    rows = db.rows(sql + ' ORDER BY name,id', tuple(params))
    config = db.settings()
    return jsonify({'items': [public_device(row, config) for row in rows]})


@app.get('/api/devices/<int:identifier>')
def get_device(identifier):
    return jsonify(public_device(device(identifier)))


@app.post('/api/devices')
def create_device():
    require_operator()
    data = validate_device(payload(DEVICE_FIELDS, ('name', 'address', 'environment')))
    with db.connection() as client, client.cursor() as cursor:
        parent_valid(cursor, data['parent_id'], data['environment'])
        cursor.execute('INSERT INTO devices(name,address,environment,kind,site,services_json,notes,parent_id,exporter_port,metric_key) '
                       'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                       (data['name'], data['address'], data['environment'], data['kind'], data['site'],
                        json.dumps(data['services']), data['notes'], data['parent_id'], data['exporter_port'], ''))
        identifier = cursor.lastrowid
        if data['environment'] == 'demo':
            sync_demo_state(cursor, identifier, data['services'], create=True)
        audit(cursor, 'device_created', data['environment'], 'Perangkat ditambahkan: ' + data['name'], identifier)
        result = public_device(device(identifier, cursor))
    return jsonify(result), 201


@app.patch('/api/devices/<int:identifier>')
def edit_device(identifier):
    require_operator()
    data = payload(tuple(key for key in DEVICE_FIELDS if key != 'environment'))
    if not data:
        fail('Tidak ada perubahan yang diberikan.')
    with db.connection() as client, client.cursor() as cursor:
        current = device(identifier, cursor)
        active_jobs(cursor, identifier)
        values = validate_device(data, current)
        parent_valid(cursor, values['parent_id'], current['environment'], identifier)
        cursor.execute('UPDATE devices SET name=%s,address=%s,kind=%s,site=%s,services_json=%s,notes=%s,'
                       "parent_id=%s,exporter_port=%s,status='unknown',last_checked_at=NULL,latency_ms=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=%s",
                       (values['name'], values['address'], values['kind'], values['site'], json.dumps(values['services']),
                        values['notes'], values['parent_id'], values['exporter_port'], identifier))
        if current['environment'] == 'demo':
            sync_demo_state(cursor, identifier, values['services'])
        audit(cursor, 'device_updated', current['environment'], 'Inventaris perangkat diperbarui.', identifier)
        result = public_device(device(identifier, cursor))
    return jsonify(result)


@app.patch('/api/devices/<int:identifier>/auto-approve')
def edit_auto_approve(identifier):
    require_admin()
    positive_id(identifier, 'ID perangkat')
    data = payload(('enabled',), ('enabled',))
    enabled = data['enabled']
    if not isinstance(enabled, bool):
        fail('Nilai auto-approve harus true atau false.')
    with db.connection() as client, client.cursor() as cursor:
        target = device(identifier, cursor)
        active_jobs(cursor, identifier)
        cursor.execute('UPDATE devices SET auto_approve=%s,updated_at=UTC_TIMESTAMP(6) WHERE id=%s',
                       (1 if enabled else 0, identifier))
        audit(cursor, 'auto_approve_changed', target['environment'],
              ('Auto-approve diaktifkan: perubahan layanan pada perangkat ini dieksekusi tanpa persetujuan terpisah.' if enabled
               else 'Auto-approve dinonaktifkan; persetujuan admin kembali diwajibkan.'), identifier)
        result = public_device(device(identifier, cursor))
    return jsonify(result)


@app.delete('/api/devices/<int:identifier>')
def delete_device(identifier):
    require_operator()
    payload(())
    with db.connection() as client, client.cursor() as cursor:
        target = device(identifier, cursor)
        active_jobs(cursor, identifier)
        cursor.execute('SELECT id FROM devices WHERE parent_id=%s AND archived_at IS NULL LIMIT 1 FOR UPDATE', (identifier,))
        if cursor.fetchone():
            fail('Pindahkan atau arsipkan perangkat anak terlebih dahulu.', 409)
        cursor.execute('UPDATE devices SET archived_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=%s', (identifier,))
        audit(cursor, 'device_archived', target['environment'], 'Perangkat diarsipkan.', identifier)
    return jsonify({'ok': True})


@app.get('/api/checks')
def list_checks():
    env, identifier = environment(), query_id()
    raw = request.args.get('limit', '50')
    if not re.fullmatch(r'[0-9]{1,3}', raw) or not 20 <= int(raw) <= 100:
        fail('Batas hasil harus antara 20 dan 100.')
    sql = ('SELECT c.*,d.name AS device_name FROM checks c JOIN devices d ON d.id=c.device_id '
           'WHERE c.environment=%s AND d.archived_at IS NULL')
    params = [env]
    if identifier is not None:
        sql += ' AND c.device_id=%s'
        params.append(identifier)
    params.append(int(raw))
    return jsonify({'items': [db.public(row) for row in db.rows(sql + ' ORDER BY c.id DESC LIMIT %s', tuple(params))]})


@app.post('/api/devices/<int:identifier>/check')
def request_check(identifier):
    require_operator()
    payload(())
    return enqueue(identifier, 'check', is_check=True)


@app.get('/api/jobs')
def list_jobs():
    rows = db.rows(JOB_SELECT + 'WHERE j.environment=%s ORDER BY j.id DESC LIMIT %s', (environment(), result_limit()))
    return jsonify({'items': [db.public(row) for row in rows]})


@app.get('/api/jobs/<int:identifier>')
def get_job(identifier):
    positive_id(identifier, 'ID pekerjaan')
    return jsonify(public_job(identifier))


@app.post('/api/jobs')
def request_job():
    require_operator()
    data = payload(('device_id', 'action', 'service'), ('device_id', 'action'))
    return enqueue(positive_id(data['device_id']), data['action'], data.get('service'))


def lock_job(cursor, identifier):
    positive_id(identifier, 'ID pekerjaan')
    # Discover the immutable foreign key, then use device-before-job lock ordering.
    initial = db.one('SELECT device_id FROM jobs WHERE id=%s', (identifier,))
    if not initial:
        fail('Pekerjaan tidak ditemukan.', 404)
    target = device(initial['device_id'], cursor, include_archived=True)
    cursor.execute('SELECT * FROM jobs WHERE id=%s FOR UPDATE', (identifier,))
    job = cursor.fetchone()
    if not job:
        fail('Pekerjaan tidak ditemukan.', 404)
    return job, target


@app.post('/api/jobs/<int:identifier>/approve')
def approve_job(identifier):
    require_admin()
    data = payload(('confirmation',), ('confirmation',))
    with db.connection() as client, client.cursor() as cursor:
        job, target = lock_job(cursor, identifier)
        if job['status'] != 'awaiting_approval':
            fail('Pekerjaan tidak lagi menunggu persetujuan.', 409)
        if target['archived_at'] is not None or target['updated_at'] != job['device_updated_at']:
            fail('Target telah berubah atau diarsipkan. Batalkan dan buat permintaan baru.', 409)
        if job['environment'] != target['environment']:
            fail('Lingkungan target tidak sesuai.', 409)
        if not isinstance(data['confirmation'], str) or data['confirmation'] != target['name']:
            fail('Konfirmasi harus sama persis dengan nama perangkat.')
        validate_action(target, job['action'], job['service'])
        if not policy.ACTIONS[job['action']]['requires_approval']:
            fail('Aksi ini tidak memerlukan persetujuan.', 409)
        cursor.execute('UPDATE jobs SET status=%s,approved_by=%s,approved_at=UTC_TIMESTAMP(6) WHERE id=%s AND status=%s',
                       ('queued', g.user['id'], identifier, 'awaiting_approval'))
        if cursor.rowcount != 1:
            fail('Status pekerjaan telah berubah.', 409)
        audit(cursor, 'job_approved', target['environment'], 'Pekerjaan disetujui: ' + str(identifier), target['id'])
        result = public_job(identifier, cursor)
    return jsonify({'job': result})


@app.post('/api/jobs/<int:identifier>/cancel')
def cancel_job(identifier):
    require_operator()
    payload(())
    with db.connection() as client, client.cursor() as cursor:
        job, target = lock_job(cursor, identifier)
        if g.user['role'] != 'admin' and job['requested_by'] != g.user['id']:
            fail('Anda hanya dapat membatalkan pekerjaan sendiri.', 403)
        if job['status'] not in ('awaiting_approval', 'queued'):
            fail('Hanya pekerjaan yang belum berjalan dapat dibatalkan.', 409)
        cursor.execute('UPDATE jobs SET status=%s,finished_at=UTC_TIMESTAMP(6) WHERE id=%s AND status IN (%s,%s)',
                       ('cancelled', identifier, 'awaiting_approval', 'queued'))
        if cursor.rowcount != 1:
            fail('Status pekerjaan telah berubah.', 409)
        audit(cursor, 'job_cancelled', target['environment'], 'Pekerjaan dibatalkan: ' + str(identifier), target['id'])
        result = public_job(identifier, cursor)
    return jsonify({'job': result})


@app.get('/api/incidents')
def list_incidents():
    sql = INCIDENT_SELECT + 'WHERE i.environment=%s AND d.archived_at IS NULL'
    params = [environment()]
    status = request.args.get('status')
    if status is not None:
        if status not in ('open', 'acknowledged', 'resolved'):
            fail('Status insiden tidak valid.')
        sql += ' AND i.status=%s'
        params.append(status)
    return jsonify({'items': [public_incident(row) for row in db.rows(sql + ' ORDER BY i.id DESC LIMIT %s', tuple(params + [result_limit()]))]})


@app.post('/api/incidents')
def create_incident():
    require_operator()
    data = payload(('device_id', 'title', 'severity', 'details'), ('device_id', 'title', 'severity', 'details'))
    identifier = positive_id(data['device_id'])
    title = text(data['title'], 'Judul', 160, 1)
    details = text(data['details'], 'Rincian', 8000)
    if data['severity'] not in ('info', 'warning', 'critical'):
        fail('Tingkat keparahan tidak valid.')
    with db.connection() as client, client.cursor() as cursor:
        target = device(identifier, cursor)
        cursor.execute('INSERT INTO incidents(device_id,environment,title,severity,details,fingerprint) VALUES(%s,%s,%s,%s,%s,%s)',
                       (identifier, target['environment'], title, data['severity'], details, None))
        incident_id = cursor.lastrowid
        audit(cursor, 'incident_created', target['environment'], 'Insiden manual dibuat: ' + title, identifier)
        db.note_incident(cursor, incident_id, g.user['username'], 'created', 'open', details)
        cursor.execute(INCIDENT_SELECT + 'WHERE i.id=%s', (incident_id,))
        result = public_incident(cursor.fetchone())
    return jsonify(result), 201


@app.patch('/api/incidents/<int:identifier>')
def edit_incident(identifier):
    require_operator()
    positive_id(identifier, 'ID insiden')
    data = payload(('status', 'note'), ('status',))
    status = data['status']
    if status not in ('open', 'acknowledged', 'resolved'):
        fail('Status insiden tidak valid.')
    note = text(data.get('note', ''), 'Catatan', 4000)
    if status == 'resolved' and sum(character.isalnum() for character in note) < 8:
        fail('Tuliskan catatan penyelesaian yang bermakna (minimal 8 huruf atau angka).')
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute('SELECT * FROM incidents WHERE id=%s FOR UPDATE', (identifier,))
        incident = cursor.fetchone()
        if not incident:
            fail('Insiden tidak ditemukan.', 404)
        assigned = g.user['id'] if status == 'acknowledged' else incident['assigned_to']
        cursor.execute('UPDATE incidents SET status=%s,assigned_to=%s,resolution_note=%s,resolved_at=%s,'
                       'updated_at=UTC_TIMESTAMP(6) WHERE id=%s',
                       (status, assigned, note or None,
                        datetime.now(timezone.utc).replace(tzinfo=None) if status == 'resolved' else None, identifier))
        audit(cursor, 'incident_updated', incident['environment'], 'Status insiden: ' + status + ('. ' + note if note else ''),
              incident['device_id'])
        db.note_incident(cursor, identifier, g.user['username'], 'status_changed', status, note)
        cursor.execute(INCIDENT_SELECT + 'WHERE i.id=%s', (identifier,))
        result = public_incident(cursor.fetchone())
    return jsonify(result)


def validate_ai_settings(data):
    if not isinstance(data.get('enabled'), bool):
        fail('Kolom enabled harus true atau false.')
    base_url = text(data.get('base_url', ''), 'Base URL', 300)
    model = text(data.get('model', ''), 'Nama model', 120)
    api_key = data.get('api_key')
    if api_key is None:
        api_key = ''
    if not isinstance(api_key, str):
        fail('Kunci API tidak valid.')
    timeout = data.get('timeout', 20)
    max_tokens = data.get('max_tokens', 600)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 2 <= timeout <= 60:
        fail('Batas waktu harus antara 2 dan 60 detik.')
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 64 <= max_tokens <= 2000:
        fail('Batas token keluaran harus antara 64 dan 2000.')
    if base_url:
        try:
            parts = urlsplit(base_url)
        except ValueError:
            fail('Base URL tidak valid.')
        if parts.scheme not in ('http', 'https') or not parts.netloc or parts.username or parts.password \
                or parts.query or parts.fragment:
            fail('Base URL harus http(s) tanpa kredensial, query, atau fragmen. Contoh: https://api.provider.com/v1')
    if not base_url or not model:
        # Only enforce presence when the assistant is being turned on; the
        # stored key is merged in by the caller before this check is repeated.
        if data.get('enabled'):
            fail('Isi base URL, nama model, dan kunci API sebelum mengaktifkan asisten.')
    return {'enabled': data['enabled'], 'base_url': base_url.rstrip('/'), 'model': model,
            'api_key': api_key, 'timeout': timeout, 'max_tokens': max_tokens}


@app.get('/api/ai/settings')
def get_ai_settings():
    require_admin()
    return jsonify(ai.public_view())


@app.post('/api/ai/settings')
def set_ai_settings():
    require_admin()
    data = validate_ai_settings(payload(('enabled', 'base_url', 'model', 'api_key', 'timeout', 'max_tokens'),
                                        ('enabled', 'base_url', 'model', 'timeout', 'max_tokens')))
    with db.connection() as client, client.cursor() as cursor:
        existing = ai.stored_settings(cursor)
        stored = dict(existing or {})
        # An empty api_key means "keep the stored key"; it is never echoed back.
        if not data['api_key']:
            if not stored.get('api_key'):
                if data['enabled']:
                    fail('Kunci API belum tersimpan; isi kunci terlebih dahulu.')
                data['api_key'] = ''
            else:
                old_host = urlsplit(stored.get('base_url', '')).netloc.casefold()
                new_host = urlsplit(data['base_url']).netloc.casefold() if data['base_url'] else ''
                if old_host and new_host and old_host != new_host:
                    fail('Host Base URL berubah. Masukkan kembali kunci API agar kunci lama tidak dikirim ke penyedia baru.')
                data['api_key'] = stored['api_key']
        stored.update({key: value for key, value in data.items() if value != '' or key != 'api_key'})
        stored['api_key'] = data['api_key']
        if data['enabled'] and not (data['base_url'] and data['model'] and data['api_key']):
            fail('Isi base URL, nama model, dan kunci API sebelum mengaktifkan asisten.')
        cursor.execute('INSERT INTO ai_settings(id,settings_json,updated_by) VALUES(1,%s,%s) '
                       'ON DUPLICATE KEY UPDATE settings_json=VALUES(settings_json),updated_by=VALUES(updated_by)',
                       (json.dumps(stored), g.user['id']))
        audit(cursor, 'ai_settings_changed', 'system',
              'Konfigurasi asisten AI diperbarui (status: ' + ('aktif' if data['enabled'] else 'nonaktif') + ').')
    return jsonify(ai.public_view())


@app.post('/api/ai/settings/verify')
def verify_ai_settings():
    require_admin()
    data = payload(('base_url', 'model', 'api_key', 'timeout', 'max_tokens'),
                   ('base_url', 'model'))
    if not data.get('api_key'):
        try:
            with db.connection() as client, client.cursor() as cursor:
                stored = ai.stored_settings(cursor) or {}
        except db.pymysql.MySQLError:
            stored = {}
        data['api_key'] = stored.get('api_key', '')
    try:
        result = ai.verify(data)
    except ai.AIUnavailable as error:
        fail(str(error), 503)
    return jsonify(result)


@app.get('/api/ai/status')
def ai_status():
    return jsonify(ai.status())


def scoped_incident(identifier):
    env = environment(required=True)
    incident = db.one(INCIDENT_SELECT + 'WHERE i.id=%s AND d.archived_at IS NULL', (identifier,))
    if not incident or incident['environment'] != env:
        fail('Insiden tidak ditemukan pada lingkungan ini.', 404)
    return incident


@app.get('/api/incidents/<int:identifier>')
def get_incident(identifier):
    positive_id(identifier, 'ID insiden')
    incident = scoped_incident(identifier)
    result = public_incident(incident)
    result['history'] = [db.public(row) for row in db.rows(
        'SELECT actor,action,status,note,created_at FROM incident_events WHERE incident_id=%s ORDER BY id DESC LIMIT 100',
        (identifier,))]
    return jsonify(result)


def ai_failure(error):
    status = 429 if error.retry_after else 503
    fail(str(error), status, {'Retry-After': str(error.retry_after)} if error.retry_after else None)


@app.post('/api/incidents/<int:identifier>/explain')
def explain_incident(identifier):
    require_operator()
    positive_id(identifier, 'ID insiden')
    payload(())
    incident = scoped_incident(identifier)
    allow_ai_request()
    try:
        result = ai.summarise_incident(identifier)
    except ai.AIUnavailable as error:
        ai_failure(error)
    db.audit('AI-Advisor', 'incident_explained', incident['environment'],
             'Ringkasan insiden dibuat oleh asisten AI (baca saja).', incident['device_id'])
    return jsonify(result)


@app.post('/api/incidents/<int:identifier>/followup')
def incident_followup(identifier):
    require_operator()
    positive_id(identifier, 'ID insiden')
    payload(())
    incident = scoped_incident(identifier)
    allow_ai_request()
    try:
        result = ai.followup_incident(identifier)
    except ai.AIUnavailable as error:
        ai_failure(error)
    db.audit('AI-Advisor', 'incident_followup_suggested', incident['environment'],
             'Saran tindak lanjut dibuat oleh asisten AI (baca saja).', incident['device_id'])
    return jsonify(result)


@app.post('/api/ai/ask')
def ask_ai():
    require_operator()
    data = payload(('question',), ('question',))
    question = text(data['question'], 'Pertanyaan', 1000, 3)
    allow_ai_request()
    try:
        env = environment(required=True)
        result = ai.ask(env, question)
    except ai.AIUnavailable as error:
        ai_failure(error)
    db.audit('AI-Advisor', 'operational_question_answered', env, 'Tanya jawab operasional melalui asisten AI (baca saja).')
    return jsonify(result)


@app.post('/api/ai/triage')
def ai_triage():
    require_operator()
    payload(())
    env = environment(required=True)
    allow_ai_request()
    try:
        result = ai.triage(env)
    except ai.AIUnavailable as error:
        ai_failure(error)
    db.audit('AI-Advisor', 'environment_triaged', env, 'Prioritas insiden dibuat oleh asisten AI (baca saja).')
    return jsonify(result)


@app.post('/api/ai/handover')
def ai_handover():
    require_operator()
    payload(())
    env = environment(required=True)
    allow_ai_request()
    try:
        result = ai.handover(env)
    except ai.AIUnavailable as error:
        ai_failure(error)
    db.audit('AI-Advisor', 'environment_handover_created', env, 'Ringkasan handover dibuat oleh asisten AI (baca saja).')
    return jsonify(result)


@app.post('/api/ai/settings/models')
def ai_models():
    require_admin()
    data = payload(('base_url', 'api_key', 'timeout', 'max_tokens'), ('base_url',))
    if not data.get('api_key'):
        try:
            with db.connection() as client, client.cursor() as cursor:
                data['api_key'] = (ai.stored_settings(cursor) or {}).get('api_key', '')
        except db.pymysql.MySQLError:
            data['api_key'] = ''
    data.setdefault('model', 'model-list')
    try:
        return jsonify(ai.list_models(data))
    except ai.AIUnavailable as error:
        ai_failure(error)


@app.get('/api/audit')
def list_audit():
    rows = db.rows('SELECT * FROM audit_events WHERE environment IN (%s,%s) ORDER BY id DESC LIMIT %s',
                   (environment(), 'system', result_limit()))
    return jsonify({'items': [db.public(row) for row in rows]})


@app.get('/api/overview')
def overview():
    env = environment()
    config = db.settings()
    devices = [public_device(row, config) for row in db.rows(
        'SELECT * FROM devices WHERE environment=%s AND archived_at IS NULL ORDER BY name,id', (env,))]
    counts = {'devices': len(devices), 'up': 0, 'warning': 0, 'down': 0, 'unknown': 0}
    for row in devices:
        counts[row['status']] += 1
    counts['open_incidents'] = db.one(
        'SELECT COUNT(*) AS total FROM incidents i JOIN devices d ON d.id=i.device_id '
        'WHERE i.environment=%s AND i.status IN (%s,%s) AND d.archived_at IS NULL', (env, 'open', 'acknowledged'))['total']
    counts['pending_jobs'] = db.one(
        'SELECT COUNT(*) AS total FROM jobs j JOIN devices d ON d.id=j.device_id '
        'WHERE j.environment=%s AND j.status IN (%s,%s,%s) AND d.archived_at IS NULL', (env, *ACTIVE))['total']
    incidents = db.rows(INCIDENT_SELECT + 'WHERE i.environment=%s AND i.status IN (%s,%s) '
                        'AND d.archived_at IS NULL ORDER BY i.id DESC LIMIT %s', (env, 'open', 'acknowledged', 5))
    jobs = db.rows(JOB_SELECT + 'WHERE j.environment=%s AND d.archived_at IS NULL ORDER BY j.id DESC LIMIT %s', (env, 5))
    activity = db.rows('SELECT a.* FROM audit_events a LEFT JOIN devices d ON d.id=a.device_id '
                       'WHERE a.environment IN (%s,%s) AND (a.device_id IS NULL OR d.archived_at IS NULL) '
                       'ORDER BY a.id DESC LIMIT %s', (env, 'system', 8))
    worker = db.one("SELECT heartbeat_at,detail_json FROM service_state WHERE name='worker'")
    worker_view = db.public(worker) if worker else {'heartbeat_at': None, 'detail': None}
    if worker_view.get('heartbeat_at'):
        heartbeat = datetime.fromisoformat(worker_view['heartbeat_at'].replace('Z', '+00:00'))
        worker_view['healthy'] = (datetime.now(timezone.utc) - heartbeat).total_seconds() <= 180
    else:
        worker_view['healthy'] = False
    return jsonify({'counts': counts, 'devices': devices, 'incidents': [public_incident(row) for row in incidents],
                    'jobs': [db.public(row) for row in jobs], 'activity': [db.public(row) for row in activity],
                    'worker': worker_view})


@app.get('/api/metrics')
def get_metrics():
    env, identifier = environment(), query_id()
    sql = 'SELECT * FROM devices WHERE environment=%s AND archived_at IS NULL'
    params = [env]
    if identifier is not None:
        sql += ' AND id=%s'
        params.append(identifier)
    devices = db.rows(sql + ' ORDER BY id', tuple(params))
    if identifier is not None and not devices:
        fail('Perangkat tidak ditemukan pada lingkungan ini.', 404)
    return jsonify(metrics.collect(env, devices, db.settings()))


@app.get('/')
@app.get('/<path:path>')
def spa(path=''):
    if path == 'api' or path.startswith('api/') or path == 'static' or path.startswith('static/'):
        fail('Data tidak ditemukan.', 404)
    return app.send_static_file('index.html')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(db.settings().get('port', 3080)), debug=False)

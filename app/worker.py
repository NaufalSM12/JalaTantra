import fcntl
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import traceback
import urllib.error
import urllib.request

import dns.exception
import dns.resolver
import pymysql

import db
import metrics
from policy import ACTIONS, AUTO_APPROVABLE, RELOADABLE_SERVICES, SERVICE_ACTIONS, SERVICES, allowed_address, managed_host

STOP = False
CHECK_WORKERS = 8
CHECK_INTERVAL = 60
HEARTBEAT_INTERVAL = 20
HOUSEKEEPING_INTERVAL = 3600
QUEUE_TTL = timedelta(minutes=30)
RUNNING_TTL = timedelta(minutes=10)
APPROVAL_TTL = timedelta(days=7)
ANOMALY_CONFIRMATIONS = 2
ANOMALY_RULES = {
    'cpu': 'lonjakan sedikitnya 25 poin di atas baseline dengan nilai 70% ke atas',
    'memory': 'lonjakan sedikitnya 25 poin di atas baseline dengan nilai 70% ke atas',
    'disk': 'kenaikan sedikitnya 3 poin dalam 30 menit dengan nilai 80% ke atas',
    'rx': 'sedikitnya 5 kali baseline dengan nilai 1 MB/s ke atas',
    'tx': 'sedikitnya 5 kali baseline dengan nilai 1 MB/s ke atas',
}
_anomaly_hits = {}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def report(subject, error):
    """Frames locate the failure; the message is omitted because it may hold request data."""
    frames = ''.join(traceback.format_tb(error.__traceback__)[-4:])
    print(f'{subject} failed ({type(error).__name__})\n{frames}', flush=True)


def probe(address, service, config):
    definition = SERVICES[service]
    start = time.monotonic()
    status, detail = 'up', 'Koneksi TCP berhasil.'
    try:
        if definition['protocol'] == 'dns':
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = [address]
            answer = resolver.resolve(config['dns_probe_name'], 'A', lifetime=2)
            if not answer:
                raise ValueError('Jawaban DNS kosong.')
            detail = 'Resolusi DNS berhasil.'
        elif service in ('grafana', 'prometheus'):
            route = '/api/health' if service == 'grafana' else '/-/ready'
            host = '[' + address + ']' if ':' in address else address
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(f'http://{host}:{definition["port"]}{route}', timeout=3) as response:
                content = response.read(4096)
            if service == 'grafana' and json.loads(content).get('database') != 'ok':
                raise ValueError('Pemeriksaan database layanan gagal.')
            detail = 'Endpoint kesehatan merespons dengan baik.'
        else:
            with socket.create_connection((address, definition['port']), timeout=2):
                pass
            if service == 'mariadb' and address == '127.0.0.1':
                db.one('SELECT 1 AS ready')
                detail = 'Koneksi TCP dan query database lokal berhasil.'
    except (OSError, ValueError, dns.exception.DNSException, urllib.error.URLError, pymysql.MySQLError):
        status, detail = 'down', 'Layanan tidak merespons pemeriksaan atau respons tidak valid.'
    return {'service': service, 'label': definition['label'], 'status': status,
            'latency_ms': round((time.monotonic() - start) * 1000, 2), 'detail': detail}


def evaluate_device(device, config):
    services = json.loads(device['services_json'])
    if device['environment'] == 'demo':
        state = db.one('SELECT * FROM demo_state WHERE device_id=%s', (device['id'],))
        if not state:
            raise ValueError('State simulasi belum tersedia.')
        simulated = json.loads(state['services_json'])
        results = [{'service': service, 'label': SERVICES[service]['label'],
                    'status': 'up' if state['online'] and simulated.get(service, 0) else 'down',
                    'latency_ms': 2.5 if state['online'] else None,
                    'detail': 'Hasil simulasi tersimpan; tidak ada koneksi ke perangkat nyata.'}
                   for service in services]
        if state['disk_percent'] >= 80:
            results.append({'service': 'disk', 'label': 'Kapasitas disk', 'status': 'warning',
                            'latency_ms': None, 'detail': f'Simulasi kapasitas disk {state["disk_percent"]:.0f}%.'})
    else:
        if not allowed_address(device['address'], config):
            raise ValueError('Alamat belum diizinkan untuk pemeriksaan.')
        results = [probe(device['address'], service, config) for service in services]
    up = sum(item['status'] == 'up' for item in results)
    bad = sum(item['status'] in ('down', 'warning') for item in results)
    status = 'up' if up and not bad else 'warning' if up and bad else 'down' if bad else 'unknown'
    latencies = [item['latency_ms'] for item in results if item['latency_ms'] is not None]
    return status, results, round(sum(latencies) / len(latencies), 2) if latencies else None


def sync_incidents(cursor, device, results):
    for item in results:
        fingerprint = f'{device["id"]}:{item["service"]}'
        cursor.execute('SELECT * FROM incidents WHERE fingerprint=%s FOR UPDATE', (fingerprint,))
        previous = cursor.fetchone()
        if item['status'] in ('down', 'warning'):
            severity = 'critical' if item['status'] == 'down' else 'warning'
            title = f'{item["label"]} memerlukan perhatian'
            if previous:
                if previous['status'] == 'resolved':
                    cursor.execute("UPDATE incidents SET status='open',severity=%s,details=%s,resolved_at=NULL,resolution_note=NULL WHERE id=%s", (severity, item['detail'], previous['id']))
                    db.note_incident(cursor, previous['id'], 'System', 'reopened', 'open', item['detail'])
                    cursor.execute('INSERT INTO audit_events(actor,action,environment,device_id,detail) VALUES(%s,%s,%s,%s,%s)', ('System', 'incident.reopened', device['environment'], device['id'], title))
            else:
                cursor.execute('INSERT INTO incidents(device_id,environment,title,severity,details,fingerprint) VALUES(%s,%s,%s,%s,%s,%s)', (device['id'], device['environment'], title, severity, item['detail'], fingerprint))
                db.note_incident(cursor, cursor.lastrowid, 'System', 'detected', 'open', item['detail'])
                cursor.execute('INSERT INTO audit_events(actor,action,environment,device_id,detail) VALUES(%s,%s,%s,%s,%s)', ('System', 'incident.detected', device['environment'], device['id'], title))
        elif item['status'] == 'up' and previous and previous['status'] != 'resolved':
            note = item['label'] + ' kembali merespons.'
            cursor.execute("UPDATE incidents SET status='resolved',resolution_note=%s,resolved_at=UTC_TIMESTAMP(6) WHERE id=%s", (note, previous['id']))
            db.note_incident(cursor, previous['id'], 'System', 'recovered', 'resolved', note)
            cursor.execute('INSERT INTO audit_events(actor,action,environment,device_id,detail) VALUES(%s,%s,%s,%s,%s)', ('System', 'incident.recovered', device['environment'], device['id'], note))


def measure(device, config):
    """Network and simulation work only; safe to run on a shared thread pool."""
    start = time.monotonic()
    status, results, latency = evaluate_device(device, config)
    return status, results, latency, round((time.monotonic() - start) * 1000, 2)


def save_check(device, measurement):
    status, results, latency, duration = measurement
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute('SELECT updated_at,archived_at FROM devices WHERE id=%s FOR UPDATE', (device['id'],))
        current = cursor.fetchone()
        if not current or current['archived_at'] or current['updated_at'] != device['updated_at']:
            raise ValueError('Konfigurasi perangkat berubah saat pemeriksaan; ulangi pemeriksaan.')
        cursor.execute('INSERT INTO checks(device_id,environment,status,results_json,duration_ms) VALUES(%s,%s,%s,%s,%s)', (device['id'], device['environment'], status, json.dumps(results), duration))
        check_id = cursor.lastrowid
        cursor.execute('UPDATE devices SET status=%s,last_checked_at=UTC_TIMESTAMP(6),latency_ms=%s,updated_at=updated_at WHERE id=%s', (status, latency, device['id']))
        sync_incidents(cursor, device, results)
    return {'check_id': check_id, 'status': status, 'results': results, 'duration_ms': duration}


def run_check(device, config):
    return save_check(device, measure(device, config))


def sweep_checks(config):
    """Check every active device within one interval, regardless of how many there are.

    Probes run with bounded parallelism so a few unreachable devices cannot stretch
    the sweep past the freshness window, and one failing device never cancels the rest.
    """
    last_id, failures, checked = 0, 0, 0
    while not STOP:
        page = db.rows('SELECT * FROM devices WHERE archived_at IS NULL AND id>%s ORDER BY id LIMIT 200', (last_id,))
        if not page:
            return failures, checked
        targets = [row for row in page if row['environment'] == 'demo' or allowed_address(row['address'], config)]

        def guarded(row):
            try:
                return measure(row, config)
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
            outcomes = list(pool.map(guarded, targets))
        for row, outcome in zip(targets, outcomes):
            if STOP:
                return failures, checked
            try:
                if isinstance(outcome, Exception):
                    raise outcome
                save_check(row, outcome)
                checked += 1
            except Exception as error:
                failures += 1
                report(f'Check for device {row["id"]}', error)
        last_id = page[-1]['id']


def active_devices():
    rows, last_id = [], 0
    while True:
        page = db.rows('SELECT * FROM devices WHERE archived_at IS NULL AND id>%s ORDER BY id LIMIT 200', (last_id,))
        if not page:
            return rows
        rows.extend(page)
        last_id = page[-1]['id']


def format_metric(field, value):
    if field not in ('rx', 'tx'):
        return f'{value:.0f}%'
    for unit, scale in (('GB/s', 1e9), ('MB/s', 1e6), ('kB/s', 1e3)):
        if value >= scale:
            return f'{value / scale:.1f} {unit}'
    return f'{value:.0f} B/s'


def sync_anomalies(devices, config):
    """Flag metric deviations as attention incidents; device status is never touched."""
    global _anomaly_hits
    now = time.time()
    history = {}
    for environment in ('demo', 'real'):
        group = [row for row in devices if row['environment'] == environment
                 and (environment == 'demo' or allowed_address(row['address'], config))]
        history.update(metrics.device_history(environment, group, config))
    current = {(item['device_id'], item['field']): item for item in metrics.anomalies(history, now)}
    previous = _anomaly_hits
    _anomaly_hits = {key: min(previous.get(key, 0) + 1, ANOMALY_CONFIRMATIONS) for key in current}
    by_id = {row['id']: row for row in devices}
    for key, item in current.items():
        if _anomaly_hits[key] >= ANOMALY_CONFIRMATIONS:
            open_anomaly(by_id[key[0]], item)
    for key, count in previous.items():
        if (key not in current and key[0] in by_id and count >= ANOMALY_CONFIRMATIONS
                and metrics.has_recent_sample(history, key[0], key[1], now)):
            resolve_anomaly(by_id[key[0]], key[1])


def anomaly_incident(cursor, device_id, field):
    cursor.execute('SELECT id,status FROM incidents WHERE fingerprint=%s FOR UPDATE', (f'{device_id}:anomaly:{field}',))
    return cursor.fetchone()


def open_anomaly(device, item):
    field = item['field']
    detail = (f'Nilai terakhir {item["label"]} {format_metric(field, item["current"])}; baseline 30 menit '
              f'{format_metric(field, item["baseline"])}. Melebihi ambang: {ANOMALY_RULES[field]}. '
              + ('Data metrik simulasi. ' if device['environment'] == 'demo' else 'Data dari layanan pemantauan. ')
              + 'Hanya menandai perhatian; status perangkat tidak berubah dan tidak ada tindakan otomatis.')
    title = f'{item["label"].capitalize()} naik tajam'
    with db.connection() as client, client.cursor() as cursor:
        existing = anomaly_incident(cursor, device['id'], field)
        if existing and existing['status'] != 'resolved':
            return
        if existing:
            cursor.execute("UPDATE incidents SET status='open',details=%s,resolved_at=NULL,resolution_note=NULL WHERE id=%s", (detail, existing['id']))
            incident_id, action = existing['id'], 'incident.reopened'
        else:
            cursor.execute('INSERT INTO incidents(device_id,environment,title,severity,details,fingerprint) VALUES(%s,%s,%s,%s,%s,%s)', (device['id'], device['environment'], title, 'warning', detail, f'{device["id"]}:anomaly:{field}'))
            incident_id, action = cursor.lastrowid, 'incident.detected'
        db.note_incident(cursor, incident_id, 'System', 'anomaly', 'open', detail)
        cursor.execute('INSERT INTO audit_events(actor,action,environment,device_id,detail) VALUES(%s,%s,%s,%s,%s)', ('System', action, device['environment'], device['id'], title + ' (anomali metrik)'))


def resolve_anomaly(device, field):
    note = 'Nilai kembali mendekati baseline menurut data pemantauan terbaru.'
    with db.connection() as client, client.cursor() as cursor:
        incident = anomaly_incident(cursor, device['id'], field)
        if not incident or incident['status'] == 'resolved':
            return
        cursor.execute("UPDATE incidents SET status='resolved',resolution_note=%s,resolved_at=UTC_TIMESTAMP(6) WHERE id=%s", (note, incident['id']))
        db.note_incident(cursor, incident['id'], 'System', 'recovered', 'resolved', note)
        cursor.execute('INSERT INTO audit_events(actor,action,environment,device_id,detail) VALUES(%s,%s,%s,%s,%s)',
                       ('System', 'incident.recovered', device['environment'], device['id'], note))


def validate_job(job, device, config):
    if device is None or device['archived_at'] is not None:
        raise ValueError('Perangkat tidak lagi aktif dalam inventaris.')
    if job['environment'] != device['environment'] or job['device_updated_at'] != device['updated_at']:
        raise ValueError('Konfigurasi perangkat berubah; buat rencana tindakan baru.')
    queued_at = job.get('approved_at') or job.get('created_at')
    if queued_at is not None and utcnow() - queued_at > QUEUE_TTL:
        raise ValueError('Pekerjaan kedaluwarsa: sudah lebih dari 30 menit dalam antrean. Ajukan ulang jika masih diperlukan.')
    if job['action'] not in ('check', *ACTIONS.keys()):
        raise ValueError('Tindakan tidak dikenal.')
    if job['action'] in SERVICE_ACTIONS:
        if job['service'] not in SERVICES or job['service'] not in json.loads(device['services_json']):
            raise ValueError('Layanan tidak termasuk rencana perangkat.')
        if job['action'] == 'reload_service' and job['service'] not in RELOADABLE_SERVICES:
            raise ValueError('Layanan tidak mendukung reload aman.')
    if job['action'] in AUTO_APPROVABLE:
        # A device explicitly marked by an administrator carries its own
        # standing approval. The fixed allowlist above still applies, and the
        # decision is re-checked here at execution time (disabling auto-approve
        # before the worker runs cancels the standing approval).
        if not device.get('auto_approve'):
            approver = db.one('SELECT role FROM users WHERE id=%s', (job['approved_by'],)) if job['approved_by'] else None
            if not job['approved_at'] or not approver or approver['role'] != 'admin':
                raise ValueError('Persetujuan administrator diperlukan.')
    if device['environment'] == 'real':
        if not allowed_address(device['address'], config):
            raise ValueError('Alamat di luar jaringan yang diizinkan.')
        if job['action'] != 'check' and not managed_host(device['address'], config):
            raise ValueError('Perangkat belum didaftarkan untuk otomasi.')


def run_ansible(job, device, config):
    host = managed_host(device['address'], config)
    playbook = Path(config['automation_dir']) / (job['action'] + '.yml')
    variables = {'service_unit': SERVICES[job['service']]['unit']} if job['service'] else {}
    with tempfile.NamedTemporaryFile(mode='w+', dir=config['runner_temp'], prefix='job-', suffix='.json') as parameter_file:
        json.dump(variables, parameter_file)
        parameter_file.flush()
        command = ['/usr/bin/ansible-playbook', '-i', config['automation_inventory'], str(playbook), '--limit', host, '-e', '@' + parameter_file.name]
        environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                       'ANSIBLE_CONFIG': config['ansible_config'], 'HOME': config['runner_temp'],
                       'ANSIBLE_NOCOLOR': '1', 'ANSIBLE_LOCAL_TEMP': config['runner_temp'] + '/local'}
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   env=environment, cwd=config['automation_dir'], start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            raise ValueError('Batas waktu eksekusi Ansible tercapai; verifikasi perangkat sebelum mencoba kembali.') from None
    output = (stdout + '\n' + stderr)[-48000:]
    return process.returncode == 0, output


def attach_diagnosis(device, job, result, success):
    """Store read-only diagnosis output on the device's newest open incident."""
    if not success or job['action'] != 'diagnose' or not result:
        return
    summary = []
    for item in (result.get('results') if isinstance(result, dict) else None) or []:
        summary.append(f"{item.get('label', '')}: {item.get('detail', '')}".strip(': '))
    if not summary:
        summary.append('Diagnosis selesai tanpa keluaran terstruktur.')
    detail = '\n'.join(summary)[:3800]
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute('SELECT id,status FROM incidents WHERE device_id=%s AND status IN (%s,%s) ORDER BY id DESC LIMIT 1',
                       (device['id'], 'open', 'acknowledged'))
        incident = cursor.fetchone()
        if not incident:
            return
        cursor.execute('UPDATE incidents SET details=CONCAT(LEFT(details,4000),%s,LEFT(%s,4000)),updated_at=UTC_TIMESTAMP(6) WHERE id=%s',
                       ('\n\n[Lampiran diagnosis]', detail, incident['id']))
        db.note_incident(cursor, incident['id'], 'System', 'diagnosed', incident['status'], 'Lampiran diagnosis ' + str(job['service']) + ':\n' + detail)
        db.audit('Automation', 'incident.diagnosed', device['environment'],
                 f"Hasil diagnosis layanan {job['service']} dilampirkan ke insiden #{incident['id']}.", device['id'])


def finish_job(job_id, status, logs, result):
    """A job that already ran must never stay 'running' because one write failed."""
    for attempt in range(3):
        try:
            db.execute('UPDATE jobs SET status=%s,logs=%s,result_json=%s,finished_at=UTC_TIMESTAMP(6) WHERE id=%s',
                       (status, '\n'.join(logs)[-60000:], json.dumps(result) if result is not None else None, job_id))
            return
        except pymysql.MySQLError as error:
            if attempt == 2:
                raise
            report(f'Job {job_id} result write', error)
            time.sleep(2 * (attempt + 1))


def process_job(job, config):
    device = db.one('SELECT * FROM devices WHERE id=%s', (job['device_id'],))
    logs = []
    success, result = False, None
    try:
        validate_job(job, device, config)
        logs.append('Mode: SIMULASI' if device['environment'] == 'demo' else 'Mode: PERANGKAT NYATA')
        logs.append(f'Perangkat: {device["name"]} | Tindakan: {job["action"]}')
        if job['action'] == 'check':
            result = run_check(device, config)
            success = True
            logs.append('Pemeriksaan selesai. Kondisi perangkat: ' + result['status'])
        else:
            if device['environment'] == 'demo':
                logs.append('Simulator memproses tindakan; Ansible tidak dijalankan pada perangkat nyata.')
                state = db.one('SELECT * FROM demo_state WHERE device_id=%s', (device['id'],))
                if not state or not state['online']:
                    raise ValueError('Perangkat simulasi offline; layanan tidak dapat dikelola.')
                if job['service'] and job['action'] != 'diagnose':
                    values = json.loads(state['services_json'])
                    values[job['service']] = 1
                    db.execute('UPDATE demo_state SET services_json=%s WHERE device_id=%s', (json.dumps(values), device['id']))
                success = True
                if job['action'] == 'diagnose':
                    logs.append('Diagnosis pada perangkat demo menggunakan kondisi simulasi tersimpan.')
            else:
                success, output = run_ansible(job, device, config)
                logs.append(output)
            result = run_check(device, config)
            if job['action'] in ('ensure_service', 'restart_service', 'reload_service') and success:
                success = any(item['service'] == job['service'] and item['status'] == 'up' for item in result['results'])
            logs.append('Verifikasi selesai: ' + ('sesuai rencana.' if success else 'hasil belum sesuai rencana.'))
    except ValueError as error:
        success = False
        logs.append(str(error))
    except Exception as error:
        success = False
        logs.append('Eksekusi gagal karena kesalahan layanan internal; periksa log operator.')
        print(f'Job {job["id"]}: internal execution failure', flush=True)
        report(f'Job {job["id"]}', error)
    finish_job(job['id'], 'succeeded' if success else 'failed', logs, result)
    db.audit('Automation', 'job.succeeded' if success else 'job.failed', job['environment'], f'Tindakan {job["action"]} #{job["id"]} selesai.', job['device_id'])
    if job['action'] == 'diagnose':
        try:
            attach_diagnosis(device, job, result, success)
        except Exception as error:
            report(f'Job {job["id"]} diagnosis attachment', error)


def claim_job():
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED")
        job = cursor.fetchone()
        if job:
            cursor.execute("UPDATE jobs SET status='running',started_at=UTC_TIMESTAMP(6) WHERE id=%s", (job['id'],))
        return job


def execute_counting(sql, params=()):
    with db.connection() as client, client.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


def housekeeping():
    """Close jobs that can no longer be executed safely or never got a decision."""
    now = utcnow()
    abandoned = execute_counting(
        "UPDATE jobs SET status='failed',finished_at=UTC_TIMESTAMP(6),logs=CONCAT(logs,%s) WHERE status='running' AND started_at<%s",
        ('\nPekerjaan melewati batas waktu pelaporan; hasil tidak diverifikasi. Periksa perangkat sebelum mencoba lagi.', now - RUNNING_TTL))
    expired = execute_counting(
        "UPDATE jobs SET status='cancelled',finished_at=UTC_TIMESTAMP(6),logs=CONCAT(logs,%s) WHERE status='awaiting_approval' AND created_at<%s",
        ('\nPekerjaan dibatalkan karena tidak memperoleh keputusan dalam 7 hari.', now - APPROVAL_TTL))
    if abandoned or expired:
        db.audit('System', 'jobs_expired', 'system',
                 f'{abandoned} pekerjaan tanpa hasil terverifikasi ditandai gagal; {expired} permintaan lama dibatalkan.')


def prune_history(config):
    """Bound the growth of time-ordered history; settings come from the server configuration."""
    now, removed = utcnow(), {}
    for table, setting, default in (('checks', 'check_retention_days', 30), ('jobs', 'job_retention_days', 180),
                                    ('audit_events', 'audit_retention_days', 400)):
        days = max(1, int(config.get(setting, default)))
        total = 0
        while True:
            count = execute_counting(f'DELETE FROM {table} WHERE created_at<%s LIMIT 5000', (now - timedelta(days=days),))
            total += count
            if count < 5000:
                break
        removed[table] = total
    execute_counting('DELETE FROM sessions WHERE expires_at<=%s', (now,))
    execute_counting('DELETE FROM login_attempts WHERE window_start<%s', (now - timedelta(days=1),))
    if any(removed.values()):
        db.audit('System', 'history_pruned', 'system',
                 f"Riwayat melewati masa simpan dihapus: {removed['checks']} pemeriksaan, {removed['jobs']} pekerjaan, {removed['audit_events']} aktivitas.")


def heartbeat(detail):
    db.execute("INSERT INTO service_state(name,heartbeat_at,detail_json) VALUES('worker',UTC_TIMESTAMP(6),%s) "
               'ON DUPLICATE KEY UPDATE heartbeat_at=VALUES(heartbeat_at),detail_json=VALUES(detail_json)', (json.dumps(detail),))


def stop(signum, frame):
    global STOP
    STOP = True


def main():
    config = db.settings()
    with open(Path(config['runner_temp']) / 'worker.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db.execute("UPDATE jobs SET status='failed',finished_at=UTC_TIMESTAMP(6),logs=CONCAT(logs,'\nWorker berhenti sebelum hasil terverifikasi; tidak dijalankan ulang otomatis.') WHERE status='running'")
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        next_checks = next_housekeeping = next_heartbeat = 0.0
        stats = {'jobs': 0, 'checks': 0, 'check_failures': 0, 'last_sweep': None, 'sweep_ms': None}
        while not STOP:
            try:
                now = time.monotonic()
                if now >= next_heartbeat:
                    try:
                        if now >= next_housekeeping:
                            housekeeping()
                            prune_history(config)
                            next_housekeeping = now + HOUSEKEEPING_INTERVAL
                        heartbeat({'jobs': stats['jobs'], 'checks': stats['checks'], 'check_failures': stats['check_failures'],
                                   'last_sweep': stats['last_sweep'], 'sweep_ms': stats['sweep_ms']})
                    except Exception as error:
                        report('Housekeeping', error)
                    next_heartbeat = now + HEARTBEAT_INTERVAL
                job = claim_job()
                if job:
                    process_job(job, config)
                    stats['jobs'] += 1
                    continue
                if now >= next_checks:
                    started, started_at = time.monotonic(), utcnow().isoformat() + 'Z'
                    failures, checked = sweep_checks(config)
                    stats['checks'] += checked
                    stats['check_failures'] += failures
                    stats['last_sweep'], stats['sweep_ms'] = started_at, round((time.monotonic() - started) * 1000)
                    if not STOP:
                        try:
                            sync_anomalies(active_devices(), config)
                        except Exception as error:
                            report('Metric baseline', error)
                    next_checks = started + CHECK_INTERVAL
                time.sleep(1)
            except Exception as error:
                report('Worker cycle', error)
                print('Worker cycle failed; retrying without discarding queued jobs.', flush=True)
                time.sleep(5)


if __name__ == '__main__':
    main()

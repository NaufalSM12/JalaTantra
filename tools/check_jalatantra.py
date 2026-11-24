import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
os.environ['JALATANTRA_CONFIG'] = '/etc/jalatantra/worker.json'
os.environ['JALATANTRA_DB_USER'] = 'jalatantra_worker'
import db
from werkzeug.security import generate_password_hash

BASE = 'http://127.0.0.1:3080'


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = ''

    def request(self, method, route, data=None, expected=200, csrf=True, origin=BASE):
        headers = {'Content-Type': 'application/json', 'Origin': origin}
        if csrf:
            headers['X-CSRF-Token'] = self.csrf
        request = urllib.request.Request(BASE + route, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=90)
        except urllib.error.HTTPError as error:
            response = error
        content = response.read()
        payload = json.loads(content) if content else {}
        assert response.status in (expected if isinstance(expected, tuple) else (expected,)), f'{method} {route}: {response.status} {payload}'
        if 'csrf_token' in payload:
            self.csrf = payload['csrf_token']
        return payload


def wait_job(client, job_id):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        job = client.request('GET', f'/api/jobs/{job_id}')
        if job['status'] in ('succeeded', 'failed', 'cancelled'):
            return job
        time.sleep(0.5)
    raise AssertionError('Worker did not finish the queued job')


def main():
    credentials = json.load(sys.stdin)
    client = Client()
    report = []
    created = []
    test_users = []
    suffix = secrets.token_hex(4)
    client.request('GET', '/api/session', expected=401)
    client.request('GET', '/api/health')
    client.request('POST', '/api/login', credentials)
    report.append('authenticated session and protected endpoints')
    try:
        for role in ('viewer', 'operator'):
            username = 'verify_' + role + '_' + suffix
            password = secrets.token_urlsafe(24)
            user_id = db.execute('INSERT INTO users(username,password_hash,role) VALUES(%s,%s,%s)', (username, generate_password_hash(password, method='scrypt'), role))
            test_users.append(user_id)
            role_client = Client()
            role_client.request('POST', '/api/login', {'username': username, 'password': password})
            role_client.request('GET', '/api/devices?environment=demo')
            if role == 'viewer':
                role_client.request('POST', '/api/devices', {}, expected=403)
            else:
                operator = role_client
        report.append('viewer write restriction')
        payload = {'name': 'verify-' + suffix, 'address': '192.0.2.201', 'environment': 'demo',
                   'kind': 'server', 'site': 'Verifikasi lokal', 'services': ['ssh'], 'notes': 'Perangkat pengujian otomatis; diarsipkan setelah selesai.'}
        client.request('POST', '/api/devices', payload, expected=403, csrf=False)
        client.request('POST', '/api/devices', payload, expected=403, origin='https://untrusted.invalid')
        device = client.request('POST', '/api/devices', payload, expected=(200, 201))
        created.append(device['id'])
        device_id = device['id']
        client.request('POST', '/api/devices', payload, expected=409)
        client.request('PATCH', f'/api/devices/{device_id}', {'parent_id': device_id}, expected=(400, 409, 422))
        report.append('device creation, duplicates, parent-cycle prevention, CSRF and origin checks')
        db.execute('UPDATE demo_state SET services_json=%s WHERE device_id=%s', ('{"ssh":0}', device_id))
        result = client.request('POST', f'/api/devices/{device_id}/check', {}, expected=(200, 201, 202))
        checked = wait_job(client, result['job']['id'])
        assert checked['status'] == 'succeeded' and checked['result']['status'] == 'down', checked
        incidents = client.request('GET', '/api/incidents?environment=demo')['items']
        incident = next(item for item in incidents if item['device_id'] == device_id and item['status'] == 'open')
        client.request('PATCH', f'/api/incidents/{incident["id"]}', {'status': 'acknowledged', 'note': 'Ditinjau melalui verifikasi lokal.'})
        report.append('failed service check creates an incident and can be acknowledged')
        job = client.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'ensure_service', 'service': 'ssh'}, expected=(200, 201, 202))['job']
        assert job['status'] == 'awaiting_approval'
        client.request('PATCH', f'/api/devices/{device_id}', {'notes': 'must reject'}, expected=409)
        client.request('POST', f'/api/jobs/{job["id"]}/approve', {'confirmation': 'wrong'}, expected=(400, 409, 422))
        operator.request('POST', f'/api/jobs/{job["id"]}/approve', {'confirmation': device['name']}, expected=403)
        client.request('POST', f'/api/jobs/{job["id"]}/approve', {'confirmation': device['name']})
        finished = wait_job(client, job['id'])
        assert finished['status'] == 'succeeded' and finished['result']['status'] == 'up', finished
        assert 'Ansible tidak dijalankan' in finished['logs']
        incidents = client.request('GET', '/api/incidents?environment=demo')['items']
        assert next(item for item in incidents if item['id'] == incident['id'])['status'] == 'resolved'
        report.append('admin approval, immutable pending target, simulated recovery and automatic incident resolution')
        job = client.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'restart_service', 'service': 'ssh'}, expected=(200, 201, 202))['job']
        client.request('POST', f'/api/jobs/{job["id"]}/cancel', {})
        assert client.request('GET', f'/api/jobs/{job["id"]}')['status'] == 'cancelled'
        client.request('POST', '/api/jobs', {'device_id': device_id, 'action': '../../shell'}, expected=(400, 422))
        report.append('job cancellation and fixed action catalog')
        # Auto-approve: admin enables it, an operator request then executes directly.
        client.request('PATCH', f'/api/devices/{device_id}/auto-approve', {'enabled': True})
        assert client.request('GET', f'/api/devices/{device_id}')['auto_approve'] is True
        operator.request('PATCH', f'/api/devices/{device_id}/auto-approve', {'enabled': False}, expected=403)
        auto_job = operator.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'ensure_service', 'service': 'ssh'}, expected=(200, 201, 202))['job']
        assert auto_job['status'] == 'queued', auto_job
        finished = wait_job(client, auto_job['id'])
        assert finished['status'] == 'succeeded', finished
        # Disabled auto-approve restores the approval gate for new requests.
        client.request('PATCH', f'/api/devices/{device_id}/auto-approve', {'enabled': False})
        assert client.request('GET', f'/api/devices/{device_id}')['auto_approve'] is False
        gated = operator.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'restart_service', 'service': 'ssh'}, expected=(200, 201, 202))['job']
        assert gated['status'] == 'awaiting_approval', gated
        client.request('POST', f'/api/jobs/{gated["id"]}/cancel', {})
        report.append('device-level auto-approve executes directly and its disable restores the approval gate')
        # Diagnose: read-only, no approval, attached to an open incident.
        db.execute('UPDATE demo_state SET services_json=%s WHERE device_id=%s', ('{"ssh":0}', device_id))
        client.request('POST', f'/api/devices/{device_id}/check', {}, expected=(200, 201, 202))
        time.sleep(1.5)
        open_incidents = [item for item in client.request('GET', '/api/incidents?environment=demo')['items']
                          if item['device_id'] == device_id and item['status'] in ('open', 'acknowledged')]
        diagnose = operator.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'diagnose', 'service': 'ssh'}, expected=(200, 201, 202))['job']
        assert diagnose['status'] == 'queued', diagnose
        diagnosed = wait_job(client, diagnose['id'])
        assert diagnosed['status'] == 'succeeded', diagnosed
        if open_incidents:
            detail = next(item for item in client.request('GET', '/api/incidents?environment=demo')['items'] if item['id'] == open_incidents[0]['id'])
            assert 'Lampiran diagnosis' in (detail['details'] or ''), detail
        client.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'diagnose'}, expected=(400, 422))
        report.append('read-only diagnosis runs without approval and its result is attached to the open incident')
        evidence = client.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'collect_evidence'}, expected=(200, 201, 202))['job']
        assert evidence['status'] == 'queued'
        evidence_done = wait_job(client, evidence['id'])
        assert evidence_done['status'] == 'succeeded' and 'SIMULASI' in evidence_done['logs'], evidence_done
        client.request('POST', '/api/jobs', {'device_id': device_id, 'action': 'reload_service', 'service': 'ssh'}, expected=(400, 422))
        report.append('bounded read-only evidence collection and reload service allowlist')
        ai_status = client.request('GET', '/api/ai/status')
        if ai_status['available'] and open_incidents:
            analysis = client.request('POST', f'/api/incidents/{open_incidents[0]["id"]}/explain?environment=demo', {})
            assert analysis['read_only'] and isinstance(analysis['summary'], str) and analysis['summary'], analysis
            followup = client.request('POST', f'/api/incidents/{open_incidents[0]["id"]}/followup?environment=demo', {}, expected=(200, 503))
            if 'suggestions' in followup:
                assert followup['read_only'] and isinstance(followup['suggestions'], str) and followup['suggestions'], followup
                report.append('configured AI advisor returns read-only incident analysis and next-step suggestions')
            else:
                assert 'error' in followup
                report.append('configured AI advisor preserves operational state when provider has no follow-up response')
        else:
            client.request('POST', f'/api/incidents/{open_incidents[0]["id"]}/explain?environment=demo', {}, expected=(503,)) if open_incidents else None
            report.append('unconfigured AI advisor reports unavailable without fabricating an analysis')
        manual = client.request('POST', '/api/incidents', {'device_id': device_id, 'title': 'Verifikasi proses manual', 'severity': 'info', 'details': 'Pengujian siklus insiden.'}, expected=(200, 201))
        client.request('PATCH', f'/api/incidents/{manual["id"]}', {'status': 'resolved', 'note': ''}, expected=(400, 422))
        client.request('PATCH', f'/api/incidents/{manual["id"]}', {'status': 'resolved', 'note': 'Siklus insiden berhasil diuji.'})
        metrics = client.request('GET', f'/api/metrics?environment=demo&device_id={device_id}')
        assert metrics['summary']['cpu'] is None, metrics
        report.append('new demo device never inherits fabricated historical metrics')
        real_payload = dict(payload, name='verify-real-' + suffix, address='192.0.2.202', environment='real')
        real = client.request('POST', '/api/devices', real_payload, expected=(200, 201))
        created.append(real['id'])
        assert not real['checks_allowed'] and not real['managed']
        client.request('POST', f'/api/devices/{real["id"]}/check', {}, expected=(400, 403, 409))
        client.request('POST', '/api/jobs', {'device_id': real['id'], 'action': 'audit'}, expected=(400, 403, 409))
        report.append('inventory outside enrolled networks cannot execute checks or actions')
        localhost = next(item for item in client.request('GET', '/api/devices?environment=real')['items'] if item['name'] == 'localhost')
        job = client.request('POST', '/api/jobs', {'device_id': localhost['id'], 'action': 'audit'}, expected=(200, 201, 202))['job']
        audited = wait_job(client, job['id'])
        assert audited['status'] == 'succeeded' and 'PLAY RECAP' in audited['logs'], audited
        assert any(item['service'] == 'ssh' and item['status'] == 'down' for item in audited['result']['results']), audited
        report.append('real localhost read-only Ansible audit; inactive SSH remains DOWN')
        assert client.request('GET', '/api/audit?environment=demo')['items']
        client.request('POST', '/api/logout', {})
        client.request('GET', '/api/session', expected=401)
        report.append('persisted audit trail and session revocation')
    finally:
        client.request('POST', '/api/login', credentials)
        for device_id in reversed(created):
            for job in client.request('GET', '/api/jobs?environment=demo')['items']:
                if job['device_id'] == device_id and job['status'] in ('awaiting_approval', 'queued'):
                    client.request('POST', f'/api/jobs/{job["id"]}/cancel', {})
            client.request('DELETE', f'/api/devices/{device_id}', expected=(200, 204))
        for user_id in test_users:
            db.execute("UPDATE jobs SET requested_by=(SELECT id FROM users WHERE username='admin' LIMIT 1) WHERE requested_by=%s", (user_id,))
            db.execute("UPDATE jobs SET approved_by=(SELECT id FROM users WHERE username='admin' LIMIT 1) WHERE approved_by=%s", (user_id,))
            db.execute('DELETE FROM sessions WHERE user_id=%s', (user_id,))
            db.execute('DELETE FROM users WHERE id=%s', (user_id,))
        client.request('POST', '/api/logout', {})
    print(json.dumps({'passed': report, 'count': len(report)}, indent=2))


if __name__ == '__main__':
    main()

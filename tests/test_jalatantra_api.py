"""API contract tests use Flask's client and mocked MariaDB transactions only."""
import copy
import importlib.util
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP_DIR))
import metrics

HAS_FLASK = importlib.util.find_spec('flask') is not None
MOCK_DRIVER = False
if HAS_FLASK:
    # The database transport is never exercised by these unit tests. Permit the
    # Flask suite on machines without PyMySQL, without pretending to test MariaDB.
    if importlib.util.find_spec('pymysql') is None:
        MOCK_DRIVER = True
        driver = types.ModuleType('pymysql')
        driver.MySQLError = type('MySQLError', (Exception,), {})
        driver.IntegrityError = type('IntegrityError', (driver.MySQLError,), {})
        driver.OperationalError = type('OperationalError', (driver.MySQLError,), {})
        driver.connect = Mock(side_effect=AssertionError('Database transport must be mocked'))
        driver.cursors = types.SimpleNamespace(DictCursor=object)
        sys.modules['pymysql'] = driver
    try:
        import server
        import security
        import db
    finally:
        if MOCK_DRIVER:
            del sys.modules['pymysql']

CONFIG = {'allowed_networks': ['127.0.0.0/8'], 'managed_hosts': {'127.0.0.1': 'local'},
          'prometheus_url': 'http://127.0.0.1:9090', 'cookie_secure': False, 'port': 3080}


def target(**updates):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    value = {'id': 1, 'name': 'edge-gw01', 'address': '127.0.0.1', 'environment': 'demo',
             'kind': 'router', 'site': 'Jakarta', 'services_json': '["ssh"]', 'notes': '',
             'parent_id': None, 'exporter_port': 9100, 'metric_key': 'edge-gw01', 'status': 'up',
             'last_checked_at': now, 'latency_ms': 1.0, 'created_at': now, 'updated_at': now, 'archived_at': None}
    value.update(updates)
    return value


def job_for(device, **updates):
    value = {'id': 12, 'device_id': device['id'], 'environment': device['environment'], 'action': 'restart_service',
             'service': 'ssh', 'status': 'awaiting_approval', 'requested_by': 7, 'approved_by': None,
             'approved_at': None, 'device_updated_at': device['updated_at'], 'logs': '', 'result_json': None,
             'created_at': device['updated_at'], 'started_at': None, 'finished_at': None}
    value.update(updates)
    return value


class ScriptedCursor:
    """Verify statement ordering, parameters and locking without a SQL emulator."""
    def __init__(self, test, steps):
        self.test, self.steps, self.calls = test, list(steps), []
        self.result, self.lastrowid, self.rowcount = None, 0, 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        self.test.assertIsInstance(params, tuple)
        if params:
            self.test.assertEqual(sql.count('%s'), len(params), sql)
        self.test.assertTrue(self.steps, 'Unexpected SQL: ' + sql)
        step = self.steps.pop(0)
        self.test.assertIn(step[0], sql)
        self.calls.append((sql, params))
        self.result = step[1]
        self.lastrowid = step[2] if len(step) > 2 else 0
        self.rowcount = step[3] if len(step) > 3 else 1

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result or []


@unittest.skipUnless(HAS_FLASK, 'Flask is not installed')
class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'correct-password-123'
        cls.password_hash = security.generate_password_hash(cls.password, method='scrypt')

    def setUp(self):
        server.app.config.update(TESTING=True)
        self.client = server.app.test_client()
        self.client.set_cookie(security.COOKIE, 'session-token')
        self.role = 'operator'
        self.extra_one = {}
        self.transactions = []
        self.cursor = None
        self.config = copy.deepcopy(CONFIG)
        self.one = self.start(patch.object(db, 'one', side_effect=self.lookup))
        self.rows = self.start(patch.object(db, 'rows', return_value=[]))
        self.connection = self.start(patch.object(db, 'connection', side_effect=self.transaction))
        self.start(patch.object(db, 'settings', side_effect=lambda: self.config))

    def start(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def lookup(self, sql, params=()):
        if 'FROM sessions s JOIN users' in sql:
            self.assertEqual(params, (security.token_hash('session-token'),))
            return {'id': 7, 'username': 'operator1', 'role': self.role, 'csrf_token': 'csrf-value'}
        for fragment, result in self.extra_one.items():
            if fragment in sql:
                return result
        self.fail('Unexpected standalone SQL: ' + sql)

    @contextmanager
    def transaction(self):
        self.assertIsNotNone(self.cursor, 'A transaction must have an explicit SQL script')
        client = Mock()
        client.cursor.return_value = self.cursor
        try:
            yield client
        except Exception:
            self.transactions.append('rollback')
            raise
        else:
            self.transactions.append('commit')

    def script(self, steps):
        self.cursor = ScriptedCursor(self, steps)
        self.addCleanup(lambda: self.assertEqual(self.cursor.steps, []))
        return self.cursor

    def write(self, path, data=None, method='POST', csrf=True, **kwargs):
        headers = {'X-CSRF-Token': 'csrf-value'} if csrf else {}
        headers.update(kwargs.pop('headers', {}))
        return self.client.open(path, method=method, json={} if data is None else data, headers=headers, **kwargs)

    def assert_error(self, response, code):
        self.assertEqual(response.status_code, code, response.get_data(as_text=True))
        self.assertEqual(set(response.json), {'error'})
        self.assertNotIn('Traceback', response.json['error'])

    def approval_script(self, device, job):
        self.extra_one['SELECT device_id FROM jobs'] = {'device_id': device['id']}
        return [('SELECT * FROM devices', device), ('SELECT * FROM jobs', job)]

    def test_authentication_required_for_reads_and_writes(self):
        self.client.delete_cookie(security.COOKIE)
        for path in ('/api/session', '/api/devices', '/api/catalog', '/api/metrics', '/api/audit'):
            self.assert_error(self.client.get(path), 401)
        self.assert_error(self.write('/api/jobs'), 401)
        self.one.assert_not_called()

    def test_expired_session_is_rejected(self):
        self.one.side_effect = None
        self.one.return_value = None
        self.assert_error(self.client.get('/api/session'), 401)
        self.assertIn('expires_at>UTC_TIMESTAMP(6)', self.one.call_args.args[0])

    def test_session_returns_only_public_identity_and_csrf(self):
        response = self.client.get('/api/session')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'user': {'id': 7, 'username': 'operator1', 'role': 'operator'}, 'csrf_token': 'csrf-value'})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'same-origin')
        self.assertNotIn('unsafe-inline', response.headers['Content-Security-Policy'])
        self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])

    def test_health_is_public_and_database_errors_are_private(self):
        self.client.delete_cookie(security.COOKIE)
        self.one.side_effect = None
        self.one.return_value = {'healthy': 1}
        self.assertEqual(self.client.get('/api/health').json, {'ok': True})
        self.one.side_effect = RuntimeError('/private/config password=secret SELECT sensitive')
        response = self.client.get('/api/health')
        self.assert_error(response, 503)
        self.assertNotIn('secret', response.get_data(as_text=True))

    def test_csrf_required_for_writes_including_logout(self):
        for path in ('/api/jobs', '/api/logout', '/api/devices/1/check'):
            self.assert_error(self.write(path, csrf=False), 403)
        self.connection.assert_not_called()

    def test_login_and_authenticated_writes_reject_cross_origin(self):
        for path in ('/api/login', '/api/jobs'):
            for headers in ({'Origin': 'https://other.example'}, {'Origin': 'null'},
                            {'Origin': 'http://localhost.evil'}, {'Sec-Fetch-Site': 'cross-site'},
                            {'Origin': 'http://sibling.localhost', 'Sec-Fetch-Site': 'same-site'}):
                self.assert_error(self.write(path, headers=headers), 403)
        self.connection.assert_not_called()

    def test_json_is_required_and_oversized_bodies_rejected(self):
        self.assert_error(self.client.post('/api/login', data='username=x'), 415)
        self.assert_error(self.client.post('/api/login', data='{', content_type='application/json'), 400)
        self.assert_error(self.client.post('/api/login', json=['not', 'an', 'object']), 400)
        self.assert_error(self.client.post('/api/login', json={'password': 'x' * 66000}), 413)

    def test_viewer_cannot_mutate_inventory_checks_jobs_or_incidents(self):
        self.role = 'viewer'
        for path, method in (('/api/devices', 'POST'), ('/api/devices/1', 'PATCH'), ('/api/devices/1', 'DELETE'),
                             ('/api/devices/1/check', 'POST'), ('/api/jobs', 'POST'), ('/api/jobs/1/cancel', 'POST'),
                             ('/api/incidents', 'POST'), ('/api/incidents/1', 'PATCH')):
            self.assert_error(self.write(path, method=method), 403)
        self.connection.assert_not_called()

    def test_operator_cannot_approve(self):
        self.assert_error(self.write('/api/jobs/12/approve', {'confirmation': 'edge-gw01'}), 403)
        self.connection.assert_not_called()

    def test_input_validation_and_immutable_fields(self):
        valid = {'name': 'node01', 'address': '127.0.0.1', 'environment': 'demo'}
        for change in ({'name': 'bad name'}, {'name': 'a' * 81}, {'address': 'localhost'}, {'address': '224.0.0.1'},
                       {'address': '0.0.0.0'}, {'address': '169.254.0.1'}, {'address': 'fe80::1'},
                       {'address': '::'}, {'address': 'fe80::1%eth0'}, {'kind': 'desktop'}, {'environment': 'other'},
                       {'services': ['not-a-service']}, {'services': ['ssh', 'ssh']}, {'services': [{}]},
                       {'exporter_port': True}, {'exporter_port': 65536}, {'site': 's' * 101},
                       {'parent_id': True}, {'metric_key': 'edge-gw01'}, {'unexpected': True}):
            with self.subTest(change=change):
                self.assert_error(self.write('/api/devices', dict(valid, **change)), 400)
        for data in ({'environment': 'real'}, {'metric_key': 'monitor01'}, {}):
            self.assert_error(self.write('/api/devices/1', data, method='PATCH'), 400)
        self.connection.assert_not_called()

    def test_device_creation_initializes_demo_without_metric_fabrication(self):
        created = target(name='new-node', metric_key='')
        cursor = self.script([('INSERT INTO devices', None, 1), ('INSERT INTO demo_state', None),
                              ('INSERT INTO audit_events', None), ('SELECT * FROM devices', created)])
        response = self.write('/api/devices', {'name': 'new-node', 'address': '127.0.0.1', 'environment': 'demo', 'services': ['ssh']})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(cursor.calls[0][1][-1], '')
        self.assertEqual(cursor.calls[1][1], (1, 1, '{"ssh": 1}', 30))
        self.assertEqual(cursor.calls[2][1][:3], ('operator1', 'device_created', 'demo'))
        self.assertEqual(response.json['metric_key'], '')
        self.assertNotIn('archived_at', response.json)

    def test_outside_network_can_be_stored_but_capabilities_are_false(self):
        created = target(environment='real', address='192.0.2.9', metric_key='')
        self.script([('INSERT INTO devices', None, 1), ('INSERT INTO audit_events', None), ('SELECT * FROM devices', created)])
        response = self.write('/api/devices', {'name': 'edge-gw01', 'address': '192.0.2.9', 'environment': 'real'})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json['managed'])
        self.assertFalse(response.json['checks_allowed'])

    def test_duplicate_device_error_is_conflict_without_sql(self):
        self.connection.side_effect = db.pymysql.IntegrityError(1062, 'private SQL path and password')
        response = self.write('/api/devices', {'name': 'node01', 'address': '127.0.0.1', 'environment': 'real'})
        self.assert_error(response, 409)
        self.assertNotIn('private', response.get_data(as_text=True))

    def test_parent_environment_and_cycles_are_rejected(self):
        self.script([('SELECT id,parent_id,environment,archived_at', target(id=2, environment='real'))])
        self.assert_error(self.write('/api/devices', {'name': 'node01', 'address': '127.0.0.1', 'environment': 'demo', 'parent_id': 2}), 400)

    def test_indirect_parent_cycle_is_rejected(self):
        self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', None),
                     ('SELECT id,parent_id,environment,archived_at', target(id=2, parent_id=1))])
        self.assert_error(self.write('/api/devices/1', {'parent_id': 2}, method='PATCH'), 409)
        self.assertEqual(self.transactions, ['rollback'])

    def test_edit_is_blocked_while_jobs_are_active(self):
        self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', {'id': 12})])
        self.assert_error(self.write('/api/devices/1', {'address': '127.0.0.2'}, method='PATCH'), 409)

    def test_edit_services_preserves_only_declared_demo_state(self):
        updated = target(services_json='["ssh", "dns"]')
        cursor = self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', None),
                              ('UPDATE devices', None), ('SELECT services_json FROM demo_state', {'services_json': '{"ssh":0,"mariadb":1}'}),
                              ('INSERT INTO demo_state', None), ('INSERT INTO audit_events', None), ('SELECT * FROM devices', updated)])
        response = self.write('/api/devices/1', {'services': ['ssh', 'dns']}, method='PATCH')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(json.loads(cursor.calls[4][1][2]), {'ssh': 0, 'dns': 1})
        self.assertIn('updated_at=UTC_TIMESTAMP(6)', cursor.calls[2][0])

    def test_delete_rejects_children(self):
        self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', None), ('SELECT id FROM devices', {'id': 2})])
        self.assert_error(self.write('/api/devices/1', method='DELETE'), 409)

    def test_delete_soft_archives_and_audits(self):
        cursor = self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', None),
                              ('SELECT id FROM devices', None), ('UPDATE devices SET archived_at', None), ('INSERT INTO audit_events', None)])
        self.assertEqual(self.write('/api/devices/1', method='DELETE').status_code, 200)
        self.assertFalse(any('DELETE FROM devices' in sql for sql, _ in cursor.calls))

    def test_search_is_parameterized_and_environment_is_scoped(self):
        needle = "' OR 1=1 --"
        response = self.client.get('/api/devices', query_string={'environment': 'real', 'search': needle})
        self.assertEqual(response.status_code, 200)
        sql, params = self.rows.call_args.args
        self.assertNotIn(needle, sql)
        self.assertEqual(params, ('real', needle, needle, needle))

    def test_invalid_environment_and_query_limits(self):
        for path in ('/api/devices?environment=x', '/api/checks?limit=101', '/api/checks?limit=19',
                     '/api/checks?device_id=-1', '/api/metrics?device_id=1%20OR%201=1', '/api/incidents?status=invalid'):
            self.assert_error(self.client.get(path), 400)

    def test_real_check_requires_network_enrollment(self):
        self.script([('SELECT * FROM devices', target(environment='real', address='192.0.2.1'))])
        response = self.write('/api/devices/1/check')
        self.assert_error(response, 403)
        self.assertIn('jaringan', response.json['error'])

    def test_real_check_does_not_require_managed_host(self):
        device = target(environment='real', address='127.0.0.2')
        queued = job_for(device, action='check', service=None, status='queued')
        cursor = self.script([('SELECT * FROM devices', device), ('SELECT id FROM jobs', None),
                              ('INSERT INTO jobs', None, 12), ('INSERT INTO audit_events', None), ('SELECT j.*', queued)])
        response = self.write('/api/devices/1/check')
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(cursor.calls[2][1][:6], (1, 'real', 'check', None, 'queued', 7))
        self.assertIsNone(cursor.calls[2][1][6])
        self.assertIsNone(cursor.calls[2][1][7])
        self.assertEqual(cursor.calls[2][1][-2:], (device['updated_at'], ''))
        self.assertIn('FOR UPDATE', cursor.calls[0][0])

    def test_real_automation_requires_managed_host(self):
        self.script([('SELECT * FROM devices', target(environment='real', address='127.0.0.2'))])
        self.assert_error(self.write('/api/jobs', {'device_id': 1, 'action': 'audit'}), 403)

    def test_action_and_service_allowlists(self):
        cases = ({'action': 'shell'}, {'action': []}, {'action': 'check'}, {'action': 'restart_service'},
                 {'action': 'restart_service', 'service': 'mariadb'}, {'action': 'audit', 'service': 'ssh'})
        for data in cases:
            cursor = ScriptedCursor(self, [('SELECT * FROM devices', target())])
            self.cursor = cursor
            self.assert_error(self.write('/api/jobs', {'device_id': 1, **data}), 400)
            self.assertEqual(cursor.steps, [])

    def test_duplicate_active_action_is_conflict(self):
        self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', {'id': 9})])
        self.assert_error(self.write('/api/jobs', {'device_id': 1, 'action': 'audit'}), 409)

    def test_restart_is_awaiting_approval_and_has_no_execution_logs(self):
        device = target()
        cursor = self.script([('SELECT * FROM devices', device), ('SELECT id FROM jobs', None), ('INSERT INTO jobs', None, 12),
                              ('INSERT INTO audit_events', None), ('SELECT j.*', job_for(device))])
        response = self.write('/api/jobs', {'device_id': 1, 'action': 'restart_service', 'service': 'ssh'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['job']['status'], 'awaiting_approval')
        self.assertEqual(response.json['job']['logs'], '')
        self.assertEqual(cursor.calls[2][1][-2:], (device['updated_at'], ''))
        self.assertEqual(cursor.calls[2][1][5], 7)
        self.assertIsNone(cursor.calls[2][1][6])

    def test_approval_is_atomic_and_records_actor(self):
        self.role = 'admin'
        device = target()
        job = job_for(device)
        approved = dict(job, status='queued', approved_by=7)
        cursor = self.script(self.approval_script(device, job) + [('UPDATE jobs SET status', None),
                             ('INSERT INTO audit_events', None), ('SELECT j.*', approved)])
        response = self.write('/api/jobs/12/approve', {'confirmation': device['name']})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIn('FOR UPDATE', cursor.calls[1][0])
        self.assertEqual(cursor.calls[2][1], ('queued', 7, 12, 'awaiting_approval'))
        self.assertEqual(self.transactions, ['commit'])

    def test_approval_conflicts_for_changed_archived_or_nonpending_targets(self):
        self.role = 'admin'
        original = target()
        original_job = job_for(original)
        for device, job in ((target(updated_at=original['updated_at'] + timedelta(seconds=1)), original_job),
                            (dict(original, archived_at=original['updated_at']), original_job),
                            (original, dict(original_job, status='running')),
                            (original, dict(original_job, environment='real'))):
            self.cursor = ScriptedCursor(self, self.approval_script(device, job))
            self.assert_error(self.write('/api/jobs/12/approve', {'confirmation': device['name']}), 409)
            self.assertEqual(self.cursor.steps, [])

    def test_approval_rechecks_confirmation_policy_and_service(self):
        self.role = 'admin'
        for device, action, service, confirmation, expected in (
                (target(), 'restart_service', 'ssh', 'EDGE-GW01', 400),
                (target(), 'shell', 'ssh', 'edge-gw01', 400),
                (target(), 'restart_service', 'mariadb', 'edge-gw01', 400),
                (target(environment='real', address='127.0.0.2'), 'restart_service', 'ssh', 'edge-gw01', 403),
                (target(environment='real', address='192.0.2.1'), 'restart_service', 'ssh', 'edge-gw01', 403)):
            job = job_for(device, action=action, service=service)
            self.cursor = ScriptedCursor(self, self.approval_script(device, job))
            self.assert_error(self.write('/api/jobs/12/approve', {'confirmation': confirmation}), expected)
            self.assertEqual(self.cursor.steps, [])

    def test_cancel_running_job_and_other_operators_job_are_forbidden(self):
        device = target()
        for job, expected in ((job_for(device, status='running'), 409), (job_for(device, requested_by=8), 403)):
            self.cursor = ScriptedCursor(self, self.approval_script(device, job))
            self.assert_error(self.write('/api/jobs/12/cancel'), expected)
            self.assertEqual(self.cursor.steps, [])

    def test_operator_can_cancel_own_queued_job(self):
        device = target()
        job = job_for(device, status='queued')
        cursor = self.script(self.approval_script(device, job) + [('UPDATE jobs SET status', None),
                             ('INSERT INTO audit_events', None), ('SELECT j.*', dict(job, status='cancelled'))])
        response = self.write('/api/jobs/12/cancel')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(cursor.calls[2][1], ('cancelled', 12, 'awaiting_approval', 'queued'))

    def test_manual_incident_has_no_automatic_fingerprint(self):
        cursor = self.script([('SELECT * FROM devices', target()), ('INSERT INTO incidents', None, 20),
                              ('INSERT INTO audit_events', None), ('INSERT INTO incident_events', None),
                              ('SELECT i.*', {'id': 20, 'status': 'open', 'fingerprint': None})])
        response = self.write('/api/incidents', {'device_id': 1, 'title': 'Koneksi terputus', 'severity': 'critical', 'details': 'Periksa sambungan.'})
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(cursor.calls[1][1][-1])

    def test_resolution_requires_meaningful_note(self):
        for note in ('', 'ok', '...............', '________'):
            self.assert_error(self.write('/api/incidents/20', {'status': 'resolved', 'note': note}, method='PATCH'), 400)
        self.connection.assert_not_called()

    def test_acknowledgment_assigns_current_user_and_audits_note(self):
        incident = {'id': 20, 'device_id': 1, 'environment': 'real', 'assigned_to': None}
        cursor = self.script([('SELECT * FROM incidents', incident), ('UPDATE incidents', None),
                              ('INSERT INTO audit_events', None), ('INSERT INTO incident_events', None),
                              ('SELECT i.*', dict(incident, status='acknowledged', assigned_to=7))])
        response = self.write('/api/incidents/20', {'status': 'acknowledged', 'note': 'Sedang diperiksa.'}, method='PATCH')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(cursor.calls[1][1][:3], ('acknowledged', 7, 'Sedang diperiksa.'))
        self.assertEqual(cursor.calls[2][1][:3], ('operator1', 'incident_updated', 'real'))

    def test_overview_marks_stale_or_unchecked_devices_unknown(self):
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=181)
        rows = [target(last_checked_at=old), target(id=2, last_checked_at=None), target(id=3, status='warning')]
        self.rows.side_effect = [rows, [], [], []]
        self.extra_one['SELECT COUNT(*) AS total FROM incidents'] = {'total': 2}
        self.extra_one['SELECT COUNT(*) AS total FROM jobs'] = {'total': 1}
        self.extra_one['FROM service_state WHERE name=\'worker\''] = None
        response = self.client.get('/api/overview?environment=demo')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['counts'], {'devices': 3, 'up': 0, 'warning': 1, 'down': 0, 'unknown': 2,
                                                   'open_incidents': 2, 'pending_jobs': 1})
        for call in self.rows.call_args_list:
            self.assertIn('archived_at IS NULL', call.args[0])
            self.assertEqual(call.args[1][0], 'demo')

    def login_script(self, user, attempts=0):
        return [('SELECT id,username,role,password_hash', user), ('INSERT IGNORE INTO login_attempts', None),
                ('SELECT attempts,window_start', {'attempts': attempts, 'window_start': datetime.now(timezone.utc).replace(tzinfo=None)})]

    def test_successful_login_hashes_cookie_and_returns_csrf(self):
        self.client.delete_cookie(security.COOKIE)
        user = {'id': 7, 'username': 'operator1', 'role': 'operator', 'password_hash': self.password_hash}
        cursor = self.script(self.login_script(user) + [('DELETE FROM login_attempts', None), ('DELETE FROM sessions', None),
                             ('INSERT INTO sessions', None), ('INSERT INTO audit_events', None)])
        response = self.write('/api/login', {'username': 'operator1', 'password': self.password}, headers={'Origin': 'http://localhost'})
        self.assertEqual(response.status_code, 200, response.json)
        cookie = response.headers['Set-Cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        self.assertIn('Max-Age=28800', cookie)
        token = cookie.split(';')[0].split('=', 1)[1]
        params = cursor.calls[5][1]
        self.assertEqual(params[0], security.token_hash(token))
        self.assertNotEqual(params[0], token)
        self.assertEqual(params[2], response.json['csrf_token'])
        self.assertNotIn('password_hash', response.get_data(as_text=True))

    def test_failed_absent_user_uses_dummy_hash_and_commits_limiter(self):
        cursor = self.script(self.login_script(None) + [('UPDATE login_attempts', None)])
        with patch.object(security, 'check_password_hash', return_value=False) as verify:
            response = self.write('/api/login', {'username': 'missing-user', 'password': 'wrong'})
        self.assert_error(response, 401)
        verify.assert_called_once_with(security.DUMMY_HASH, 'wrong')
        self.assertEqual(cursor.calls[-1][1][0], 1)
        self.assertEqual(len(cursor.calls[1][1][0]), 64)
        self.assertEqual(self.transactions, ['commit'])

    def test_fifth_failure_blocks_subsequent_login_attempt(self):
        self.script(self.login_script(None, attempts=5))
        with patch.object(security, 'check_password_hash') as verify:
            response = self.write('/api/login', {'username': 'missing-user', 'password': 'wrong'})
        self.assert_error(response, 429)
        verify.assert_not_called()
        self.assertEqual(response.headers['Retry-After'], '900')

    def test_expired_login_window_starts_new_counter(self):
        steps = self.login_script(None, attempts=5)
        steps[-1] = (steps[-1][0], {'attempts': 5, 'window_start': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=16)})
        cursor = self.script(steps + [('UPDATE login_attempts', None)])
        response = self.write('/api/login', {'username': 'missing-user', 'password': 'wrong'})
        self.assert_error(response, 401)
        self.assertEqual(cursor.calls[-1][1][0], 1)

    def test_logout_revokes_cookie_and_session(self):
        cursor = self.script([('DELETE FROM sessions', None), ('INSERT INTO audit_events', None)])
        response = self.write('/api/logout')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Max-Age=0', response.headers['Set-Cookie'])
        self.assertEqual(cursor.calls[0][1], (security.token_hash('session-token'),))

    def test_empty_json_body_is_allowed_for_bodyless_logout(self):
        self.script([('DELETE FROM sessions', None), ('INSERT INTO audit_events', None)])
        response = self.client.post('/api/logout', content_type='application/json', headers={'X-CSRF-Token': 'csrf-value'})
        self.assertEqual(response.status_code, 200)

    def test_secure_cookie_is_configurable(self):
        self.config['cookie_secure'] = True
        self.client.delete_cookie(security.COOKIE)
        user = {'id': 7, 'username': 'operator1', 'role': 'operator', 'password_hash': self.password_hash}
        self.script(self.login_script(user) + [('DELETE FROM login_attempts', None), ('DELETE FROM sessions', None),
                    ('INSERT INTO sessions', None), ('INSERT INTO audit_events', None)])
        response = self.write('/api/login', {'username': 'operator1', 'password': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Secure;', response.headers['Set-Cookie'])

    def test_password_change_rehashes_and_revokes_other_sessions(self):
        self.role = 'viewer'
        cursor = self.script([('SELECT password_hash', {'password_hash': self.password_hash}), ('UPDATE users', None),
                              ('DELETE FROM sessions', None), ('INSERT INTO audit_events', None)])
        response = self.write('/api/password', {'current_password': self.password, 'new_password': 'new-password-4567'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(cursor.calls[1][1][0].startswith('scrypt:'))
        self.assertTrue(security.check_password_hash(cursor.calls[1][1][0], 'new-password-4567'))
        self.assertEqual(cursor.calls[2][1], (7, security.token_hash('session-token')))
        self.assertNotIn('new-password-4567', str(cursor.calls[3]))

    def test_password_minimum_and_wrong_current_password(self):
        self.assert_error(self.write('/api/password', {'current_password': self.password, 'new_password': 'short'}), 400)
        self.script([('SELECT password_hash', {'password_hash': self.password_hash})])
        self.assert_error(self.write('/api/password', {'current_password': 'wrong', 'new_password': 'new-password-4567'}), 403)

    def test_metrics_selected_device_is_environment_scoped(self):
        self.rows.return_value = [target()]
        with patch.object(metrics, 'collect', return_value={'available': False}) as collect:
            self.assertEqual(self.client.get('/api/metrics?environment=demo&device_id=1').status_code, 200)
        self.assertEqual(self.rows.call_args.args[1], ('demo', 1))
        self.assertEqual(collect.call_args.args[0], 'demo')
        self.rows.return_value = []
        self.assert_error(self.client.get('/api/metrics?environment=real&device_id=1'), 404)

    def test_spa_index_and_api_not_found_are_separate(self):
        with patch.object(server.app, 'send_static_file', return_value='index-content') as static:
            self.assertEqual(self.client.get('/').get_data(as_text=True), 'index-content')
            self.assertEqual(self.client.get('/devices/1').status_code, 200)
            self.assertEqual(static.call_args.args, ('index.html',))
            self.assert_error(self.client.get('/api/does-not-exist'), 404)
        self.assertTrue(server.app.static_folder.endswith('static'))


    def test_auto_approve_toggle_requires_admin_and_bool(self):
        self.role = 'operator'
        self.assert_error(self.write('/api/devices/1/auto-approve', {'enabled': True}, method='PATCH'), 403)
        self.connection.assert_not_called()
        self.role = 'admin'
        for value in ('yes', 1, None):
            self.assert_error(self.write('/api/devices/1/auto-approve', {'enabled': value}, method='PATCH'), 400)
        self.connection.assert_not_called()

    def test_auto_approve_toggle_updates_and_audits(self):
        self.role = 'admin'
        cursor = self.script([('SELECT * FROM devices', target()), ('SELECT id FROM jobs', None),
                              ('UPDATE devices SET auto_approve', None), ('INSERT INTO audit_events', None),
                              ('SELECT * FROM devices', target(auto_approve=1))])
        response = self.write('/api/devices/1/auto-approve', {'enabled': True}, method='PATCH')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['auto_approve'])
        self.assertEqual(cursor.calls[2][1], (1, 1))
        self.assertEqual(cursor.calls[3][1][1], 'auto_approve_changed')

    def test_auto_approve_enqueues_change_without_separate_approval(self):
        self.role = 'admin'
        device = target(auto_approve=1)
        queued = job_for(device, status='queued', approved_by=7, approved_at=device['updated_at'])
        cursor = self.script([('SELECT * FROM devices', device), ('SELECT id FROM jobs', None),
                              ('INSERT INTO jobs', None, 12), ('INSERT INTO audit_events', None), ('SELECT j.*', queued)])
        response = self.write('/api/jobs', {'device_id': 1, 'action': 'restart_service', 'service': 'ssh'})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['job']['status'], 'queued')
        insert = cursor.calls[2][1]
        self.assertEqual(insert[4], 'queued')
        self.assertEqual(insert[6], 7)  # approved_by set at enqueue time
        self.assertIn('auto-approve', cursor.calls[3][1][3])

    def test_diagnose_requires_service_and_is_queued_without_approval(self):
        device = target()
        queued = job_for(device, action='diagnose', service='ssh', status='queued')
        cursor = self.script([('SELECT * FROM devices', device), ('SELECT id FROM jobs', None),
                              ('INSERT INTO jobs', None, 12), ('INSERT INTO audit_events', None), ('SELECT j.*', queued)])
        response = self.write('/api/jobs', {'device_id': 1, 'action': 'diagnose', 'service': 'ssh'})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['job']['status'], 'queued')
        self.assertEqual(cursor.calls[2][1][2], 'diagnose')
        self.assertEqual(cursor.calls[2][1][3], 'ssh')
        self.assertEqual(cursor.calls[2][1][4], 'queued')
        for data in ({'device_id': 1, 'action': 'diagnose'}, {'device_id': 1, 'action': 'diagnose', 'service': 'mariadb'}):
            self.cursor = ScriptedCursor(self, [('SELECT * FROM devices', device)])
            self.assert_error(self.write('/api/jobs', data), 400)
            self.assertEqual(self.cursor.steps, [])

    def test_ai_endpoints_require_session_and_operator(self):
        self.client.delete_cookie(security.COOKIE)
        self.assert_error(self.client.get('/api/ai/status'), 401)
        self.assert_error(self.write('/api/incidents/20/explain'), 401)
        self.client.set_cookie(security.COOKIE, 'session-token')
        self.role = 'viewer'
        self.assert_error(self.write('/api/incidents/20/explain'), 403)

    def test_explain_rejects_environment_mismatch_without_ai_call(self):
        self.role = 'operator'
        self.extra_one['SELECT i.*,d.name AS device_name'] = dict(target(environment='real'), device_name='edge-gw01', assignee=None)
        with patch.object(server.ai, 'summarise_incident') as summarise:
            self.assert_error(self.write('/api/incidents/20/explain?environment=demo', method='POST'), 404)
        summarise.assert_not_called()


    def test_ai_requests_require_an_explicit_environment(self):
        self.assert_error(self.write('/api/ai/ask', {'question': 'Apa kondisi saat ini?'}), 400)
        self.assert_error(self.write('/api/incidents/20/explain', method='POST'), 400)

    @patch.object(server.db, 'audit')
    @patch.object(server.ai, 'ask', return_value={'answer': 'Hanya data real.', 'read_only': True})
    def test_ai_ask_forwards_explicit_environment(self, ask, audit):
        response = self.write('/api/ai/ask?environment=real', {'question': 'Bagaimana kondisi real?'})
        self.assertEqual(response.status_code, 200, response.json)
        ask.assert_called_once_with('real', 'Bagaimana kondisi real?')
        audit.assert_called_once()

    def test_ai_settings_require_admin_and_validate_input(self):
        self.role = 'operator'
        self.assert_error(self.client.get('/api/ai/settings'), 403)
        self.assert_error(self.write('/api/ai/settings', {'enabled': False}), 403)
        self.role = 'admin'
        for data in ({'enabled': 'yes', 'base_url': '', 'model': '', 'timeout': 20, 'max_tokens': 600},
                     {'enabled': False, 'base_url': 'ftp://x', 'model': '', 'timeout': 20, 'max_tokens': 600},
                     {'enabled': False, 'base_url': '', 'model': '', 'timeout': 1, 'max_tokens': 600},
                     {'enabled': False, 'base_url': '', 'model': '', 'timeout': 20, 'max_tokens': 32},
                     {'enabled': False, 'base_url': 'https://user:pw@x/v1', 'model': '', 'timeout': 20, 'max_tokens': 600},
                     {'enabled': False, 'base_url': 'https://x/v1?trace=1', 'model': '', 'timeout': 20, 'max_tokens': 600},
                     {'enabled': False, 'base_url': '', 'model': 'm', 'api_key': 5, 'timeout': 20, 'max_tokens': 600},
                     {'enabled': True, 'base_url': '', 'model': '', 'timeout': 20, 'max_tokens': 600}):
            self.assert_error(self.write('/api/ai/settings', data), 400)
        self.connection.assert_not_called()

    def test_ai_settings_can_be_saved_disabled_without_key(self):
        self.role = 'admin'
        cursor = self.script([('SELECT settings_json', None), ('INSERT INTO ai_settings', None),
                              ('INSERT INTO audit_events', None)])
        response = self.write('/api/ai/settings', {'enabled': False, 'base_url': '', 'model': '',
                                                   'timeout': 20, 'max_tokens': 600})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse(response.json['enabled'])
        self.assertEqual(cursor.calls[2][1][1], 'ai_settings_changed')

    def test_ai_settings_stored_without_echoing_key(self):
        self.role = 'admin'
        stored = {'settings_json': json.dumps({'api_key': 'existing-key', 'enabled': False, 'base_url': 'https://x/v1', 'model': 'm', 'timeout': 20, 'max_tokens': 600})}
        saved = dict(json.loads(stored['settings_json']), enabled=True)
        cursor = self.script([('SELECT settings_json', stored), ('INSERT INTO ai_settings', None),
                              ('INSERT INTO audit_events', None)])
        response = self.write('/api/ai/settings', {'enabled': True, 'base_url': 'https://x/v1', 'model': 'm',
                                                   'api_key': '', 'timeout': 20, 'max_tokens': 600})
        self.assertEqual(response.status_code, 200, response.json)
        params = cursor.calls[1][1]
        self.assertNotIn('existing-key', response.get_data(as_text=True))
        self.assertIn('existing-key', params[0])
        self.assertEqual(cursor.calls[2][1][1], 'ai_settings_changed')

    def test_ai_settings_enable_requires_key_when_none_stored(self):
        self.role = 'admin'
        self.script([('SELECT settings_json', None)])
        self.assert_error(self.write('/api/ai/settings', {'enabled': True, 'base_url': 'https://x/v1',
                                                          'model': 'm', 'api_key': '', 'timeout': 20, 'max_tokens': 600}), 400)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        with metrics._cache_lock:
            metrics._cache.clear()
        self.now = 1800000000.0

    def sample(self, value, key='edge-gw01', stamp=None, environment='demo'):
        labels = {'source': 'demo', 'device': key, 'instance': '127.0.0.1:9100'} if environment == 'demo' else {'instance': key}
        return {'metric': labels, 'value': [self.now if stamp is None else stamp, str(value)]}

    def test_demo_queries_have_freshness_and_matching_instance_gates(self):
        queries = metrics.queries('demo', [target()])
        self.assertEqual(set(queries), set(metrics.FIELDS))
        for expression in queries.values():
            self.assertIn('source="demo"', expression)
            self.assertIn('device="edge-gw01"', expression)
            self.assertIn('k8_sample_timestamp_seconds', expression)
            self.assertIn('< 60', expression)
            self.assertIn('>= 0', expression)
            self.assertIn('and on(instance)', expression)
            self.assertIn('up{job="node_exporter"} == 1', expression)
            self.assertNotIn('source="real"', expression)
        self.assertIn('and on(instance,device)', queries['cpu'])
        self.assertNotIn('and on(instance,device)', queries['up'])

    def test_missing_new_demo_keys_never_reuse_all_source_metrics(self):
        for key in ('', 'new-node', '.*'):
            self.assertEqual(metrics.queries('demo', [target(metric_key=key)]), {})
        with patch.object(metrics, 'fetch') as fetch:
            result = metrics.collect('demo', [target(metric_key='')], CONFIG)
        fetch.assert_not_called()
        self.assertFalse(result['available'])
        self.assertTrue(all(value is None for value in result['summary'].values()))
        self.assertIsNone(result['per_device'][0]['cpu'])

    def test_real_queries_use_exact_instance_and_root_disk(self):
        expressions = metrics.queries('real', [target(environment='real', address='192.0.2.10', exporter_port=9101)])
        for expression in expressions.values():
            self.assertIn('instance="192.0.2.10:9101"', expression)
            self.assertNotIn('k8_demo', expression)
            self.assertNotIn('source="demo"', expression)
        self.assertIn('mode="idle"', expressions['cpu'])
        self.assertIn('mountpoint="/"', expressions['disk'])
        self.assertIn('MemAvailable', expressions['memory'])
        ipv6 = metrics.queries('real', [target(environment='real', address='::1')])
        self.assertIn('instance="[::1]:9100"', ipv6['up'])

    def test_multi_instance_selection_escapes_regex_and_json(self):
        selector = metrics.label_selection('instance', ['127.0.0.1:9100', '[::1]:9100'])
        pattern = json.loads(selector.split('=~', 1)[1])
        import re
        self.assertTrue(re.fullmatch(pattern, '127.0.0.1:9100'))
        self.assertTrue(re.fullmatch(pattern, '[::1]:9100'))
        self.assertFalse(re.fullmatch(pattern, '127x0x0x1:9100'))
        self.assertFalse(re.fullmatch(pattern, 'evil127.0.0.1:9100'))

    def test_down_is_explicit_without_fake_zero_usage(self):
        device = target(environment='real')
        data = {('up', False): [self.sample(0, '127.0.0.1:9100', environment='real')],
                ('cpu', False): [self.sample(80, '127.0.0.1:9100', environment='real')]}
        result = metrics.assemble('real', [device], self.now, data)
        self.assertTrue(result['available'])
        self.assertEqual(result['per_device'][0]['up'], 0)
        self.assertIsNone(result['summary']['cpu'])
        self.assertIsNone(result['summary']['rx'])

    def test_current_metrics_never_leak_other_devices_or_nonfinite_values(self):
        data = {('up', False): [self.sample(1), self.sample(1, key='db01')],
                ('cpu', False): [self.sample(35), self.sample(99, key='db01')],
                ('memory', False): [self.sample('NaN')], ('rx', False): [self.sample(-5)]}
        result = metrics.assemble('demo', [target(), target(id=2, name='new', metric_key='')], self.now, data)
        self.assertEqual(result['summary']['cpu'], 35)
        self.assertIsNone(result['summary']['memory'])
        self.assertIsNone(result['summary']['rx'])
        self.assertIsNone(result['per_device'][1]['cpu'])
        self.assertIsNone(result['per_device'][1]['up'])

    def test_stale_future_or_wrong_source_samples_are_not_available(self):
        for sample in (self.sample(1, stamp=self.now - 60), self.sample(1, stamp=self.now + 1),
                       {'metric': {'source': 'real', 'device': 'edge-gw01'}, 'value': [self.now, '1']}):
            result = metrics.assemble('demo', [target()], self.now, {('up', False): [sample]})
            self.assertFalse(result['available'])
            self.assertTrue(all(value is None for value in result['summary'].values()))

    def test_history_has_30_second_gaps_as_null_and_no_cross_device_data(self):
        data = {('cpu', True): [{'metric': {'source': 'demo', 'device': 'edge-gw01'},
                                'values': [[self.now - 30, '25'], [self.now, '30']]}],
                ('rx', True): [{'metric': {'source': 'demo', 'device': 'db01'}, 'values': [[self.now, '999']]}]}
        result = metrics.assemble('demo', [target()], self.now, data)
        self.assertEqual(len(result['history']), 61)
        self.assertIsNone(result['history'][0]['cpu'])
        self.assertEqual(result['history'][-1]['cpu'], 30)
        self.assertIsNone(result['history'][-1]['rx'])
        self.assertFalse(result['available'])

    def test_aggregate_averages_percentages_and_sums_network(self):
        data = {}
        for field, first, second in (('up', 1, 1), ('cpu', 20, 40), ('rx', 100, 200), ('tx', 50, 60)):
            data[(field, False)] = [self.sample(first), self.sample(second, 'db01')]
        result = metrics.assemble('demo', [target(), target(id=2, name='db01', metric_key='db01')], self.now, data)
        self.assertEqual(result['summary']['cpu'], 30)
        self.assertEqual(result['summary']['rx'], 300)
        self.assertEqual(result['summary']['tx'], 110)

    def test_duplicate_up_and_overflow_cannot_fabricate_healthy_values(self):
        self.assertEqual(metrics.aggregate([0, 1], 'up'), 0)
        self.assertIsNone(metrics.aggregate([1e308, 1e308], 'rx'))

    def test_cache_is_scoped_and_returns_independent_copies(self):
        device = target()
        with patch.object(metrics, 'fetch', return_value=[]) as fetch:
            first = metrics.collect('demo', [device], CONFIG)
            first['per_device'][0]['name'] = 'tampered'
            second = metrics.collect('demo', [device], CONFIG)
            self.assertEqual(second['per_device'][0]['name'], device['name'])
            self.assertEqual(fetch.call_count, 10)
            metrics.collect('demo', [dict(device, id=2)], CONFIG)
            self.assertEqual(fetch.call_count, 20)
            metrics.collect('real', [dict(device, environment='real')], CONFIG)
            self.assertEqual(fetch.call_count, 30)
            metrics.collect('demo', [dict(device, name='renamed')], CONFIG)
            self.assertEqual(fetch.call_count, 40)

    def test_prometheus_failure_has_no_transport_details(self):
        with patch.object(metrics, 'fetch', side_effect=RuntimeError('http://private/path?password=secret')):
            result = metrics.collect('demo', [target()], CONFIG)
        self.assertFalse(result['available'])
        self.assertNotIn('secret', json.dumps(result))
        self.assertIsNone(result['summary']['cpu'])

    def test_fetch_is_readonly_times_out_and_limits_history(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({'status': 'success', 'data': {'resultType': 'matrix', 'result': []}}).encode()
        opener = Mock()
        opener.open.return_value = response
        with patch.object(metrics, 'build_opener', return_value=opener):
            self.assertEqual(metrics.fetch('http://127.0.0.1:9090', 'fixed_query', self.now, history=True), [])
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), 'GET')
        self.assertTrue(req.full_url.startswith('http://127.0.0.1:9090/api/v1/query_range?'))
        self.assertIn('step=30', req.full_url)
        self.assertIn('start=' + str(int(self.now) - 1800), req.full_url)
        self.assertEqual(opener.open.call_args.kwargs, {'timeout': 3})
        self.assertIsNone(req.get_header('Authorization'))

    def test_credentials_and_redirects_are_not_sent(self):
        with patch.object(metrics, 'build_opener') as opener:
            with self.assertRaises(metrics.MetricsUnavailable):
                metrics.fetch('http://user:password@127.0.0.1:9090', 'fixed', self.now)
        opener.assert_not_called()
        with self.assertRaises(metrics.MetricsUnavailable):
            metrics.NoRedirect().redirect_request(None, None, 302, None, None, 'http://other')


if __name__ == '__main__':
    unittest.main()

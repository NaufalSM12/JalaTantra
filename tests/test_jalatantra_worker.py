import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import worker
from policy import allowed_address, managed_host


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.config = {'allowed_networks': ['127.0.0.0/8'], 'managed_hosts': {'127.0.0.1': 'local'}}
        self.device = {'id': 1, 'name': 'edge01', 'address': '127.0.0.1', 'environment': 'real',
                       'archived_at': None, 'services_json': '["ssh"]', 'updated_at': datetime(2026, 11, 20)}
        self.job = {'id': 1, 'environment': 'real', 'action': 'audit', 'service': None,
                    'approved_by': None, 'approved_at': None, 'device_updated_at': self.device['updated_at']}

    def test_only_enrolled_networks(self):
        self.assertTrue(allowed_address('127.0.0.1', self.config))
        for address in ['192.0.2.1', '169.254.169.254', '224.0.0.1', '0.0.0.0', 'localhost', '127.0.0.1;id']:
            self.assertFalse(allowed_address(address, self.config))
        self.assertIsNone(managed_host('127.0.0.2', self.config))

    def test_rejects_arbitrary_action(self):
        self.job['action'] = '../../shell'
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    def test_rejects_unapproved_service_action(self):
        self.job.update(action='restart_service', service='ssh')
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    @patch('worker.db.one', return_value={'role': 'operator'})
    def test_approver_must_still_be_admin(self, read):
        self.job.update(action='restart_service', service='ssh', approved_by=2, approved_at=datetime.now())
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    def test_auto_approve_device_executes_without_admin_approval(self):
        self.job.update(action='restart_service', service='ssh')
        self.device['auto_approve'] = 1
        worker.validate_job(self.job, self.device, self.config)  # no approval required, no exception

    def test_auto_approve_does_not_bypass_anything_else(self):
        self.device['auto_approve'] = 1
        self.job.update(action='restart_service', service='ssh;id')
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)
        self.device['address'] = '127.0.0.2'
        self.job.update(service='ssh')
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    def test_diagnose_is_read_only_and_needs_no_approval(self):
        self.job.update(action='diagnose', service='ssh')
        worker.validate_job(self.job, self.device, self.config)

    def test_reload_is_limited_to_safe_service_subset(self):
        self.device['services_json'] = '["ssh", "dns"]'
        self.job.update(action='reload_service', service='dns', approved_by=2, approved_at=datetime.now())
        with patch('worker.db.one', return_value={'role': 'admin'}):
            worker.validate_job(self.job, self.device, self.config)
        self.job['service'] = 'ssh'
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    def test_collect_evidence_is_read_only_and_needs_no_service(self):
        self.job.update(action='collect_evidence', service=None)
        worker.validate_job(self.job, self.device, self.config)

    def test_diagnose_requires_registered_service(self):
        self.job.update(action='diagnose', service='mariadb')
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    @patch('worker.db.one', return_value={'role': 'admin'})
    def test_rejects_unregistered_service(self, read):
        self.job.update(action='restart_service', service='ssh;id', approved_by=2, approved_at=datetime.now())
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    def test_rejects_changed_device(self):
        self.device['updated_at'] = datetime(2026, 11, 21)
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)

    def test_real_automation_requires_managed_host(self):
        self.device['address'] = '127.0.0.2'
        with self.assertRaises(ValueError):
            worker.validate_job(self.job, self.device, self.config)
        self.job['action'] = 'check'
        worker.validate_job(self.job, self.device, self.config)

    @patch('worker.probe', side_effect=AssertionError('Demo must not probe real addresses'))
    @patch('worker.subprocess.Popen', side_effect=AssertionError('Demo must not execute commands'))
    @patch('worker.db.one', return_value={'online': 0, 'services_json': '{"ssh":0}', 'disk_percent': 30})
    def test_offline_demo_never_contacts_network(self, read, run, probe):
        self.device['environment'] = 'demo'
        status, results, latency = worker.evaluate_device(self.device, self.config)
        self.assertEqual(status, 'down')
        self.assertIsNone(latency)
        self.assertEqual(results[0]['status'], 'down')
        run.assert_not_called()
        probe.assert_not_called()

    @patch('worker.socket.create_connection', side_effect=OSError('offline'))
    def test_connection_failure_not_healthy(self, connect):
        self.assertEqual(worker.probe('127.0.0.1', 'ssh', self.config)['status'], 'down')

    @patch('worker.db.audit')
    @patch('worker.db.execute')
    @patch('worker.run_check', side_effect=ValueError('Verification failed'))
    @patch('worker.run_ansible', return_value=(True, 'Ansible completed'))
    @patch('worker.db.one')
    def test_verification_failure_cannot_report_success(self, read, run, check, execute, audit):
        read.return_value = self.device
        self.job['device_id'] = 1
        worker.process_job(self.job, self.config)
        self.assertEqual(execute.call_args.args[1][0], 'failed')

    @patch('worker.db.audit')
    @patch('worker.db.execute')
    @patch('worker.run_check', return_value={'status': 'down', 'results': []})
    @patch('worker.db.one')
    def test_completed_check_distinct_from_healthy_device(self, read, check, execute, audit):
        read.return_value = self.device
        self.job.update(action='check', device_id=1)
        worker.process_job(self.job, self.config)
        values = execute.call_args.args[1]
        self.assertEqual(values[0], 'succeeded')
        self.assertEqual(json.loads(values[2])['status'], 'down')

    @patch('worker.subprocess.Popen')
    def test_ansible_uses_fixed_argv_and_private_parameters(self, popen):
        import tempfile
        process = popen.return_value
        process.communicate.return_value = ('PLAY RECAP', '')
        process.returncode = 0
        with tempfile.TemporaryDirectory() as temporary:
            self.config.update(automation_dir='/opt/jalatantra/automation',
                               automation_inventory='/etc/jalatantra/automation-inventory.yml',
                               ansible_config='/etc/jalatantra/ansible.cfg', runner_temp=temporary)
            success, output = worker.run_ansible(self.job, self.device, self.config)
            self.assertTrue(success)
            self.assertIn('PLAY RECAP', output)
            command = popen.call_args.args[0]
            self.assertEqual(command[0], '/usr/bin/ansible-playbook')
            self.assertEqual(command[3], '/opt/jalatantra/automation/audit.yml')
            self.assertEqual(command[4:6], ['--limit', 'local'])
            self.assertNotIn('shell', popen.call_args.kwargs)
            self.assertTrue(popen.call_args.kwargs['start_new_session'])
            self.assertFalse(Path(command[-1][1:]).exists())

    def test_metric_anomaly_requires_baseline_and_large_deviation(self):
        now = worker.time.time()
        history = {1: {'cpu': [(now - 900 + step * 30, 35) for step in range(20)] + [(now - 10, 82)]}}
        found = worker.metrics.anomalies(history, now)
        self.assertEqual([(item['device_id'], item['field']) for item in found], [(1, 'cpu')])
        self.assertFalse(worker.metrics.anomalies({1: {'cpu': [(now - 10, 82)]}}, now))

    def test_expired_queued_job_is_not_executed(self):
        self.job.update(created_at=worker.utcnow() - worker.QUEUE_TTL - worker.timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, 'kedaluwarsa'):
            worker.validate_job(self.job, self.device, self.config)

    @patch('worker.os.killpg')
    @patch('worker.subprocess.Popen')
    def test_timeout_terminates_own_execution_group(self, popen, killpg):
        import tempfile
        import subprocess
        process = popen.return_value
        process.pid = 12345
        process.communicate.side_effect = [subprocess.TimeoutExpired('ansible', 120), ('', '')]
        with tempfile.TemporaryDirectory() as temporary:
            self.config.update(automation_dir='/opt/jalatantra/automation',
                               automation_inventory='/etc/jalatantra/automation-inventory.yml',
                               ansible_config='/etc/jalatantra/ansible.cfg', runner_temp=temporary)
            with self.assertRaises(ValueError):
                worker.run_ansible(self.job, self.device, self.config)
        killpg.assert_called_once_with(12345, worker.signal.SIGTERM)


if __name__ == '__main__':
    unittest.main()

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("collector", ROOT / "roles/node_exporter/files/collect.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.devices = json.loads((ROOT / "roles/node_exporter/files/demo-devices.json").read_text())
        self.config = {"device": "localhost", "address": "127.0.0.1", "role": "monitoring", "services": {"OpenSSH": "ssh"}, "dns": None, "database": False}

    def test_eight_persistent_scenarios_with_offline_and_warning(self):
        metrics = collector.Metrics()
        state = collector.collect_demo(self.devices, {}, metrics, 1000)
        output = metrics.render()
        self.assertEqual(output.count('k8_demo_inventory_info{'), 8)
        self.assertEqual(output.count('k8_demo_cpu_percent{'), 7)
        self.assertIn('k8_demo_device_up{device="lab-offline01",source="demo"} 0', output)
        self.assertNotIn('k8_demo_cpu_percent{device="lab-offline01"', output)
        self.assertIn('severity="WARNING"', output)
        self.assertIn('severity="CRITICAL"', output)
        self.assertNotIn('source="real"', output)
        self.assertEqual(state["updated"], 1000)

    def test_counters_survive_reload_and_increase(self):
        state = collector.collect_demo(self.devices, {}, collector.Metrics(), 1000)
        state = json.loads(json.dumps(state))
        collector.collect_demo(self.devices, state, collector.Metrics(), 1015)
        first = state["devices"]["db01"]["queries"]
        self.assertGreater(first, 0)
        state = json.loads(json.dumps(state))
        collector.collect_demo(self.devices, state, collector.Metrics(), 1030)
        self.assertGreater(state["devices"]["db01"]["queries"], first)
        self.assertEqual(state["started"], 1000)

    def test_backward_clock_does_not_decrease_counters(self):
        state = collector.collect_demo(self.devices, {}, collector.Metrics(), 1000)
        collector.collect_demo(self.devices, state, collector.Metrics(), 1015)
        before = state["devices"]["db01"]["queries"]
        collector.collect_demo(self.devices, state, collector.Metrics(), 1001)
        self.assertEqual(state["devices"]["db01"]["queries"], before)

    def test_demo_never_executes_network_or_service_commands(self):
        with patch.object(collector, "command") as command, patch.object(collector.dns.resolver, "Resolver") as resolver:
            collector.collect_demo(self.devices, {}, collector.Metrics(), 1000)
        command.assert_not_called()
        resolver.assert_not_called()

    def test_invalid_duplicate_devices_are_rejected(self):
        with self.assertRaises(ValueError):
            collector.validate_devices(self.devices + [self.devices[0]])
        self.devices[0]["disk"] = 101
        with self.assertRaises(ValueError):
            collector.validate_devices(self.devices)

    def test_metrics_escape_prometheus_labels(self):
        metrics = collector.Metrics()
        metrics.add("test_metric", 1, {"label": 'a"b\\c\nd'})
        self.assertIn('label="a\\"b\\\\c\\nd"', metrics.render())
        with self.assertRaises(ValueError):
            metrics.add("test_metric", float("nan"), {})

    def test_inactive_service_is_down_not_missing(self):
        metrics = collector.Metrics()
        with patch.object(collector, "command", return_value=subprocess.CompletedProcess([], 3, "inactive\n", "")):
            collector.collect_real(self.config, metrics, 1000)
        self.assertIn('k8_service_up{device="localhost",service="OpenSSH",source="real"} 0', metrics.render())
        self.assertNotIn('source="demo"', metrics.render())

    def test_failed_database_has_no_fabricated_performance_metrics(self):
        self.config["database"] = True
        metrics = collector.Metrics()
        with patch.object(collector, "command", return_value=None):
            collector.collect_real(self.config, metrics, 1000)
        self.assertIn('k8_mariadb_success{device="localhost",source="real"} 0', metrics.render())
        self.assertNotIn('k8_mariadb_questions_total', metrics.render())

    def test_database_status_parsing(self):
        self.config.update(database=True, services={})
        metrics = collector.Metrics()
        result = subprocess.CompletedProcess([], 0, "1\nQuestions\t123\nThreads_connected\t2\nUptime\t600\nSlow_queries\t0\n", "")
        with patch.object(collector, "command", return_value=result):
            collector.collect_real(self.config, metrics, 1000)
        self.assertIn('k8_mariadb_questions_total{device="localhost",source="real"} 123', metrics.render())
        self.assertIn('# TYPE k8_mariadb_questions_total counter', metrics.render())

    def test_dns_wrong_address_is_failure(self):
        self.config["dns"] = {"server": "127.0.0.1", "query": "ns1.kelompok8.test", "expected": "127.0.0.1"}
        metrics = collector.Metrics()
        resolver = Mock()
        resolver.resolve.return_value = [Mock(address="192.0.2.200")]
        with patch.object(collector.dns.resolver, "Resolver", return_value=resolver), patch.object(collector, "command", return_value=None):
            collector.collect_real(self.config, metrics, 1000)
        self.assertIn('k8_dns_success{device="localhost",query="ns1.kelompok8.test",source="real"} 0', metrics.render())

    def test_dns_timeout_is_failure_without_latency(self):
        self.config["dns"] = {"server": "127.0.0.1", "query": "ns1.kelompok8.test", "expected": "127.0.0.1"}
        metrics = collector.Metrics()
        resolver = Mock()
        resolver.resolve.side_effect = collector.dns.exception.Timeout()
        with patch.object(collector.dns.resolver, "Resolver", return_value=resolver), patch.object(collector, "command", return_value=None):
            collector.collect_real(self.config, metrics, 1000)
        self.assertNotIn('k8_dns_duration_seconds', metrics.render())
        self.assertIn('source="real"} 0', metrics.render())

    def test_atomic_write_replaces_only_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.prom"
            collector.atomic_write(path, "first")
            collector.atomic_write(path, "second")
            self.assertEqual(path.read_text(), "second")
            self.assertFalse(path.with_suffix(".prom.tmp").exists())

    def test_command_timeout_returns_unavailable(self):
        with patch.object(collector.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 4)):
            self.assertIsNone(collector.command(["systemctl", "is-active", "ssh"]))

    def test_disabling_demo_preserves_dataset_and_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            devices = root / "devices.json"
            state = root / "state.json"
            devices.write_text(json.dumps(self.devices))
            state.write_text('{"started": 1234}')
            config = {**self.config, "demo_enabled": False, "demo_devices": str(devices), "demo_state": str(state), "output": str(root / "metrics.prom")}
            path = root / "config.json"
            path.write_text(json.dumps(config))
            with patch("sys.argv", ["collect.py", "--config", str(path)]), patch.object(collector, "command", return_value=None):
                collector.main()
            self.assertEqual(state.read_text(), '{"started": 1234}')
            self.assertEqual(json.loads(devices.read_text()), self.devices)
            output = (root / "metrics.prom").read_text()
            self.assertNotIn("k8_demo_", output)
            self.assertIn('source="real"', output)


if __name__ == "__main__":
    unittest.main()

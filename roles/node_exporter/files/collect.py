#!/usr/bin/python3
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import time

import dns.exception
import dns.resolver


class Metrics:
    def __init__(self):
        self.lines = []
        self.types = set()

    def add(self, name, value, labels, kind="gauge"):
        if not math.isfinite(float(value)):
            raise ValueError(f"Non-finite metric: {name}")
        if name not in self.types:
            source = "Simulated" if name.startswith("k8_demo_") else "Measured"
            description = name.removeprefix("k8_demo_").removeprefix("k8_").replace("_", " ")
            self.lines.append(f"# HELP {name} {source} {description}.")
            self.lines.append(f"# TYPE {name} {kind}")
            self.types.add(name)
        def escape(value):
            return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        tags = ",".join(f'{key}="{escape(value)}"' for key, value in sorted(labels.items()))
        self.lines.append(f"{name}{{{tags}}} {value}")

    def render(self):
        return "\n".join(self.lines) + "\n"


def atomic_write(path, content):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def command(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect_real(config, metrics, now):
    labels = {"device": config["device"], "source": "real"}
    metrics.add("k8_inventory_info", 1, {**labels, "address": config["address"], "role": config["role"]})
    for service, unit in config["services"].items():
        result = command(["systemctl", "is-active", unit])
        active = result is not None and result.returncode == 0 and result.stdout.strip() == "active"
        metrics.add("k8_service_up", int(active), {**labels, "service": service})
    if config["dns"]:
        probe = config["dns"]
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [probe["server"]]
        start = time.monotonic()
        success = False
        try:
            answer = resolver.resolve(probe["query"], "A", lifetime=2)
            success = probe["expected"] in {record.address for record in answer}
            metrics.add("k8_dns_duration_seconds", time.monotonic() - start, {**labels, "query": probe["query"]})
        except (dns.exception.DNSException, OSError):
            pass
        metrics.add("k8_dns_success", int(success), {**labels, "query": probe["query"]})
    if config["database"]:
        result = command([
            "mariadb", "--no-defaults", "--protocol=SOCKET", "--user=k8-monitor",
            "--batch", "--skip-column-names", "--connect-timeout=2",
            "-e", "SELECT 1; SHOW GLOBAL STATUS WHERE Variable_name IN "
            "('Threads_connected','Questions','Uptime','Slow_queries');",
        ])
        success = result is not None and result.returncode == 0 and result.stdout.splitlines()[:1] == ["1"]
        metrics.add("k8_mariadb_success", int(success), labels)
        if success:
            names = {
                "Threads_connected": ("threads_connected", "gauge"),
                "Questions": ("questions_total", "counter"),
                "Uptime": ("uptime_seconds", "gauge"),
                "Slow_queries": ("slow_queries_total", "counter"),
            }
            for line in result.stdout.splitlines()[1:]:
                name, value = line.split("\t", 1)
                if name in names:
                    suffix, kind = names[name]
                    metrics.add("k8_mariadb_" + suffix, int(value), labels, kind)
    metrics.add("k8_sample_timestamp_seconds", now, {"source": "real"})


def validate_devices(devices):
    if not isinstance(devices, list) or not devices:
        raise ValueError("Demo requires a non-empty device list")
    identifiers = set()
    for device in devices:
        for key in ("device", "role", "address", "site", "scenario"):
            if not isinstance(device[key], str) or not device[key].strip():
                raise ValueError(f"Invalid demo label: {key}")
        if device["device"] in identifiers:
            raise ValueError("Duplicate demo device")
        identifiers.add(device["device"])
        if device["up"] not in (0, 1):
            raise ValueError("Demo up must be 0 or 1")
        for key in ("cpu", "memory", "disk"):
            if not 0 <= device[key] <= 100:
                raise ValueError(f"Demo {key} must be 0..100")
        if device["rx_bps"] < 0 or device["tx_bps"] < 0 or device["uptime_days"] < 0:
            raise ValueError("Demo rates and uptime cannot be negative")
        if any(value not in (0, 1) for value in device["services"].values()):
            raise ValueError("Demo service state must be 0 or 1")


def collect_demo(devices, state, metrics, now):
    validate_devices(devices)
    started = state.setdefault("started", now)
    elapsed = max(0, min(now - state.get("updated", now), 60))
    counters = state.setdefault("devices", {})
    for index, device in enumerate(devices):
        labels = {"device": device["device"], "source": "demo"}
        metrics.add("k8_demo_inventory_info", 1, {**labels, **{key: device[key] for key in ("role", "address", "site", "scenario")}})
        metrics.add("k8_demo_device_up", device["up"], labels)
        for service, status in device["services"].items():
            metrics.add("k8_demo_service_up", status * device["up"], {**labels, "service": service})
        for issue in device.get("issues", []):
            metrics.add("k8_demo_issue_info", 1, {**labels, **issue})
        if not device["up"]:
            continue
        wave = math.sin((now - started) / 67 + index * 0.8)
        for name, base, scale in (("cpu", "cpu", 8), ("memory", "memory", 2), ("disk", "disk", 0.2)):
            value = round(max(0, min(100, device[base] + wave * scale)), 2)
            metrics.add(f"k8_demo_{name}_percent", value, labels)
        metrics.add("k8_demo_uptime_seconds", device["uptime_days"] * 86400 + max(0, now - started), labels)
        counts = counters.setdefault(device["device"], {"rx": 0, "tx": 0, "queries": 0})
        for short, direction in (("rx", "receive"), ("tx", "transmit")):
            counts[short] += device[f"{short}_bps"] * (1 + wave * 0.2) * elapsed
            metrics.add(f"k8_demo_network_{direction}_bytes_total", round(counts[short], 2), labels, "counter")
        if "Bind9" in device["services"]:
            metrics.add("k8_demo_dns_duration_seconds", round(0.003 + (wave + 1) * 0.002, 5), labels)
        if "MariaDB" in device["services"]:
            counts["queries"] += (160 + wave * 45) * elapsed
            metrics.add("k8_demo_mariadb_queries_total", round(counts["queries"], 2), labels, "counter")
            metrics.add("k8_demo_mariadb_connections", round(16 + wave * 5), labels)
    state["updated"] = now
    metrics.add("k8_sample_timestamp_seconds", now, {"source": "demo"})
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/kelompok8/collector.json")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    metrics = Metrics()
    now = time.time()
    collect_real(config, metrics, now)
    if config["demo_enabled"]:
        devices = json.loads(Path(config["demo_devices"]).read_text(encoding="utf-8"))
        path = Path(config["demo_state"])
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        collect_demo(devices, state, metrics, now)
        atomic_write(path, json.dumps(state, indent=2) + "\n")
    atomic_write(config["output"], metrics.render())


if __name__ == "__main__":
    main()

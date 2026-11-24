#!/usr/bin/env python3
import json
import subprocess
import urllib.parse
import urllib.request


def get_json(url):
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.load(response)


def query(expression):
    payload = get_json("http://127.0.0.1:9090/api/v1/query?" + urllib.parse.urlencode({"query": expression}))
    if payload["status"] != "success":
        raise RuntimeError(payload)
    return payload["data"]["result"]


def main():
    health = get_json("http://127.0.0.1:3000/api/health")
    assert health["database"] == "ok", health
    print("Grafana database: OK")
    targets = get_json("http://127.0.0.1:9090/api/v1/targets")["data"]["activeTargets"]
    assert targets and all(target["health"] == "up" for target in targets), targets
    print("Prometheus targets:", ", ".join(target["labels"]["job"] + "=UP" for target in targets))
    samples = query('time() - k8_sample_timestamp_seconds')
    assert samples and all(0 <= float(sample["value"][1]) < 60 for sample in samples), samples
    print("Collector freshness: <60 seconds")
    services = query('k8_service_up{source="real"}')
    for sample in services:
        print("Real service:", sample["metric"]["service"], "UP" if sample["value"][1] == "1" else "DOWN")
    for name in ("k8_dns_success", "k8_mariadb_success"):
        result = query(name + '{source="real"}')
        assert result and all(sample["value"][1] == "1" for sample in result), result
        print(name + ": OK")
    devices = query('k8_demo_inventory_info{source="demo"}')
    print("Persistent demo devices:", len(devices))
    if devices:
        down = query('k8_demo_device_up{source="demo"} == 0')
        print("Demo offline scenarios:", len(down))
    subprocess.run(["systemctl", "is-active", "kelompok8-collector.timer"], check=True)
    print("Monitoring checks passed. DOWN services above remain genuine conditions, not hidden.")


if __name__ == "__main__":
    main()

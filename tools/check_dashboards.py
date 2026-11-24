#!/usr/bin/env python3
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request

from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]


def load_dashboard(path, template=False):
    content = path.read_text(encoding="utf-8")
    if template:
        content = Environment(undefined=StrictUndefined).from_string(content).render()
    return json.loads(content)


def query(expression, selection):
    for name in ("device", "node"):
        for variable in ("${" + name + ":regex}", "${" + name + "}", "$" + name):
            expression = expression.replace(variable, selection)
    expression = expression.replace("$__rate_interval", "1m").replace("$__interval", "15s")
    url = "http://127.0.0.1:9090/api/v1/query?" + urllib.parse.urlencode({"query": expression})
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise AssertionError(f"Invalid query {expression}: {error.read().decode()}") from error
    assert result["status"] == "success", result
    return result["data"]["result"]


def main():
    paths = [
        (ROOT / "roles/grafana/templates/kelompok8-dashboard.json", True),
        (ROOT / "roles/grafana/files/kelompok8-demo.json", False),
    ]
    for path, template in paths:
        dashboard = load_dashboard(path, template)
        panels = dashboard["panels"]
        ids = [panel["id"] for panel in panels]
        assert len(ids) == len(set(ids)), "Duplicate panel IDs"
        assert len(panels) >= 16, "Dashboard incomplete"
        for panel in panels:
            grid = panel["gridPos"]
            assert grid["x"] >= 0 and grid["x"] + grid["w"] <= 24, panel["title"]
            if panel.get("targets"):
                assert panel["datasource"]["uid"] == "PBFA97CFB590B2093", panel["title"]
            for other in panels:
                if other["id"] <= panel["id"]:
                    continue
                b = other["gridPos"]
                overlaps = grid["x"] < b["x"] + b["w"] and b["x"] < grid["x"] + grid["w"] and grid["y"] < b["y"] + b["h"] and b["y"] < grid["y"] + grid["h"]
                assert not overlaps, (panel["title"], other["title"])
        for selection in ([".*", "lab-offline01", "nonexistent-device"] if not template else [".*", "nonexistent-node"]):
            populated = 0
            total = 0
            for panel in panels:
                for target in panel.get("targets", []):
                    if "expr" not in target:
                        continue
                    result = query(target["expr"], selection)
                    populated += any(math.isfinite(float(sample["value"][1])) for sample in result)
                    total += 1
            print(f'{dashboard["uid"]}: {len(panels)} panels, filter={selection}, valid={total}, populated={populated}')
            if selection == ".*":
                assert populated == total, "Default dashboard has missing measurements"
            if selection.startswith("nonexistent"):
                assert populated == (1 if template else 0), "Unmatched filter leaked selected metrics"
    print("Dashboard JSON, layout bounds, UID references and live PromQL: OK")


if __name__ == "__main__":
    main()

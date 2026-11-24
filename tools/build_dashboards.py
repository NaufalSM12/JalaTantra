#!/usr/bin/env python3
"""Build or validate native Grafana dashboards using the Python standard library."""

import argparse
import copy
import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL_PATH = ROOT / "roles/grafana/templates/kelompok8-dashboard.json"
DEMO_PATH = ROOT / "roles/grafana/files/kelompok8-demo.json"
DS = {"type": "prometheus", "uid": "PBFA97CFB590B2093"}
VERSION = "13.3.1"
NO_DATA = "Tidak ada data"
TEAL, CYAN, PURPLE, AMBER, RED = "#2DD4BF", "#38BDF8", "#A78BFA", "#FBBF24", "#F87171"
MUTED = "#94A3B8"
RAW_START, RAW_END = "{% raw %}\n", "{% endraw %}\n"
EMPTY = " or on() vector(0 / 0)"
EMPTY_INSTANCE = ' or on() label_replace(vector(0 / 0), "instance", "Tidak ada data", "instance", ".*")'
NO_DATA_MAPPING = {
    "type": "special",
    "options": {"match": "nan", "result": {"text": NO_DATA, "color": MUTED}},
}
NULL_MAPPING = {
    "type": "special",
    "options": {"match": "null", "result": {"text": NO_DATA, "color": MUTED}},
}
EMPTY_HELP = (
    "Tidak ada data berarti sampel tidak tersedia, pilihan tidak cocok, atau validasi "
    "kesegaran gagal; bukan kondisi sehat. NaN hanya menjadi penanda kosong, bukan nilai nol."
)


def thresholds(base=TEAL, warning=None, critical=None):
    steps = [{"color": base, "value": None}]
    if warning is not None:
        steps.append({"color": AMBER, "value": warning})
    if critical is not None:
        steps.append({"color": RED, "value": critical})
    return {"mode": "absolute", "steps": steps}


def status_mapping(zero="OFFLINE", one="AKTIF"):
    return {
        "type": "value",
        "options": {
            "0": {"text": zero, "color": RED, "index": 0},
            "1": {"text": one, "color": TEAL, "index": 1},
        },
    }


def defaults(unit="short", color=TEAL, warning=None, critical=None, status=None):
    mappings = [copy.deepcopy(NO_DATA_MAPPING), copy.deepcopy(NULL_MAPPING)]
    if status:
        mappings.append(status_mapping(*status))
    value = {
        "unit": unit,
        "noValue": NO_DATA,
        "color": {"mode": "fixed", "fixedColor": color},
        "mappings": mappings,
        "thresholds": thresholds(color, warning, critical),
        "decimals": 1 if unit in ("percent", "ms", "Bps", "reqps") else 0,
    }
    if unit == "percent":
        value.update({"min": 0, "max": 100})
    if status:
        value["color"] = {"mode": "thresholds"}
        value["thresholds"] = {
            "mode": "absolute",
            "steps": [{"color": RED, "value": None}, {"color": TEAL, "value": 1}],
        }
    return value


def target(expr, legend="", ref="A", instant=False, table=False, join_placeholder=False):
    # NaN preserves unknown states; empty joins also require a shared instance key.
    empty = EMPTY_INSTANCE if join_placeholder else EMPTY
    return {
        "datasource": dict(DS),
        "editorMode": "code",
        "expr": f"({expr}){empty}" if instant else expr,
        "format": "table" if table else "time_series",
        "valueWithRefId": table,
        "instant": instant,
        "range": not instant,
        "legendFormat": legend,
        "refId": ref,
    }


class Metrics:
    def __init__(self, demo):
        self.demo = demo
        self.source = "demo" if demo else "real"
        self.variable = "$device" if demo else "$node"
        self.timestamp = self.metric("k8_sample_timestamp_seconds", selected=not demo)
        self.exporter = 'up{job="node_exporter"' + ("}" if demo else ',instance=~"$node"}')
        self.age = f"(time() - {self.timestamp})"
        self.fresh = f"({self.age} < 60) and ({self.age} >= 0)"
        self.inventory = self.metric("k8_demo_inventory_info" if demo else "k8_inventory_info")

    def metric(self, name, extra="", selected=True):
        labels = [f'source="{self.source}"', 'job="node_exporter"']
        if selected:
            labels.append('device=~"$device"' if self.demo else 'instance=~"$node"')
        if extra:
            labels.append(extra)
        return name + "{" + ",".join(labels) + "}"

    def node(self, name, extra=""):
        labels = 'job="node_exporter",instance=~"$node"'
        return name + "{" + labels + ("," + extra if extra else "") + "}"

    def gate(self, expr):
        return f"({expr}) and on(instance) ({self.fresh}) and on(instance) ({self.exporter} == 1)"

    def node_gate(self, expr):
        return f"({expr}) and on(instance) ({self.exporter} == 1)"

    def online(self, expr):
        return self.gate(expr) + (
            " and on(instance,device) "
            f'({self.metric("k8_demo_device_up")} == 1)'
        )

    def maria(self, name, rate=False):
        expr = self.metric(name)
        if rate:
            expr = f"rate({expr}[$__rate_interval])"
        if self.demo:
            return self.online(expr)
        success = self.metric("k8_mariadb_success")
        return self.gate(expr) + f" and on(instance,device) ({success} == 1)"

    def freshness(self):
        if self.demo:
            # The timestamp has no device label. Match against selected inventory.
            return self.gate(self.age) + f" and on(instance) ({self.gate(self.inventory)})"
        # Diagnostic exception: show OLD ages rather than concealing a stalled collector.
        # This is not a success/health value, and remains gated on exporter availability.
        return self.node_gate(self.age)


class Dashboard:
    def __init__(self, demo):
        self.demo = demo
        self.m = Metrics(demo)
        self.panels = []

    def add(self, kind, title, grid, description="", unit="short", color=TEAL,
            warning=None, critical=None, status=None):
        x, y, w, h = grid
        panel = {
            "id": len(self.panels) + 1,
            "type": kind,
            "title": title,
            "description": description + ("\n\n" + EMPTY_HELP if kind != "text" else ""),
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "pluginVersion": VERSION,
            "transparent": False,
        }
        if kind != "text":
            panel.update({
                "datasource": dict(DS),
                "fieldConfig": {
                    "defaults": defaults(unit, color, warning, critical, status),
                    "overrides": [],
                },
            })
        self.panels.append(panel)
        return panel

    def text(self, title, grid, html, description=""):
        panel = self.add("text", title, grid, description)
        panel["options"] = {"mode": "html", "content": html, "code": {"language": "html"}}
        return panel

    def stat(self, title, grid, expr, description, unit="short", color=TEAL,
             warning=None, critical=None, status=None):
        panel = self.add("stat", title, grid, description, unit, color, warning, critical, status)
        if warning is not None or critical is not None:
            panel["fieldConfig"]["defaults"]["color"] = {"mode": "thresholds"}
        panel["targets"] = [target(expr, instant=True)]
        panel["options"] = {
            "reduceOptions": {"calcs": ["last"], "fields": "", "values": False},
            "orientation": "horizontal", "colorMode": "value", "graphMode": "none",
            "justifyMode": "center", "textMode": "value", "wideLayout": True,
            "showPercentChange": False,
        }
        return panel

    def chart(self, title, grid, queries, description, unit="percent", color=TEAL):
        panel = self.add("timeseries", title, grid, description, unit, color)
        if self.demo:
            panel["fieldConfig"]["defaults"]["color"] = {"mode": "palette-classic"}
        panel["fieldConfig"]["defaults"]["custom"] = {
            "drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 2,
            "fillOpacity": 12, "gradientMode": "opacity", "showPoints": "never",
            "spanNulls": False, "insertNulls": False, "axisPlacement": "auto",
            "axisColorMode": "text", "axisBorderShow": False,
            "scaleDistribution": {"type": "linear"},
            "stacking": {"mode": "none", "group": "A"},
            "thresholdsStyle": {"mode": "off"},
            "hideFrom": {"legend": False, "tooltip": False, "viz": False},
        }
        panel["targets"] = [target(expr, legend, chr(65 + i)) for i, (expr, legend) in enumerate(queries)]
        panel["options"] = {
            "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom", "calcs": []},
            "tooltip": {"mode": "multi", "sort": "desc", "hideZeros": False},
        }
        if len(queries) == 2 and not self.demo:
            panel["fieldConfig"]["overrides"].append({
                "matcher": {"id": "byFrameRefID", "options": "B"},
                "properties": [
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": CYAN}},
                    {"id": "custom.fillOpacity", "value": 3},
                ],
            })
        return panel

    def bars(self, title, grid, expr, description, unit="percent", color=TEAL):
        panel = self.add("bargauge", title, grid, description, unit, color,
                         warning=80 if unit == "percent" else None,
                         critical=95 if unit == "percent" else None)
        panel["targets"] = [target(expr, "{{device}}" if self.demo else "{{instance}}", instant=True)]
        if unit == "percent":
            panel["fieldConfig"]["defaults"]["color"] = {"mode": "thresholds"}
        panel["options"] = {
            "reduceOptions": {"calcs": ["last"], "fields": "", "values": False},
            "orientation": "horizontal", "displayMode": "gradient", "valueMode": "color",
            "namePlacement": "left", "showUnfilled": True, "sizing": "auto",
            "minVizHeight": 18, "maxVizHeight": 34,
        }
        return panel

    def table(self, title, grid, expr, columns, description, value="Status", status=None,
              unit="short", color=TEAL, sort=None):
        panel = self.add("table", title, grid, description, unit, color, status=status)
        panel["targets"] = [target(expr, instant=True, table=True)]
        names = [name for name, _ in columns] + ["Value", "Value #A"]
        renames = dict(columns)
        renames.update({"Value": value, "Value #A": value})
        panel["transformations"] = [
            {"id": "filterFieldsByName", "options": {"include": {"names": names}}},
            {"id": "organize", "options": {
                "excludeByName": {}, "indexByName": {name: i for i, name in enumerate(names)},
                "renameByName": renames,
            }},
        ]
        panel["options"] = {
            "showHeader": True, "cellHeight": "sm", "enablePagination": False,
            "footer": {"show": False},
            "sortBy": [{"displayName": sort or (columns[0][1] if columns else value), "desc": False}],
        }
        panel["fieldConfig"]["defaults"]["custom"] = {
            "align": "auto", "cellOptions": {"type": "auto"}, "filterable": True,
            "inspect": False,
        }
        # After organize, match the visible column name. Text columns keep neutral colors.
        panel["fieldConfig"]["overrides"].append({
            "matcher": {"id": "byName", "options": value},
            "properties": [
                {"id": "custom.cellOptions", "value": {"type": "color-text"}},
                {"id": "custom.width", "value": 150},
            ],
        })
        return panel

    def hero(self):
        badge = "SIMULASI" if self.demo else "REAL"
        accent = AMBER if self.demo else TEAL
        title = "K8 / Demo Lab" if self.demo else "K8 / Operasional"
        subtitle = (
            "Data dummy tersimpan. Bukan kondisi perangkat nyata."
            if self.demo else
            "Pengukuran nyata. DNS, database, dan layanan server."
        )
        self.text("", (0, 0, 24, 4), f'''
<div style="background:#101B2D;border-left:5px solid {accent};padding:12px 20px;color:#E2E8F0;">
  <p style="margin:0 0 5px;font-size:12px;letter-spacing:2px;color:{accent};"><strong>{badge}</strong> &nbsp; / &nbsp; KELOMPOK 8</p>
  <h2 style="margin:0 0 6px;font-size:25px;color:#F8FAFC;">{title}</h2>
  <p style="margin:0;font-size:13px;">{subtitle}</p>
</div>'''.strip())

    def summary(self):
        m = self.m
        if self.demo:
            device_up = m.gate(m.metric("k8_demo_device_up"))
            cpu = m.online(m.metric("k8_demo_cpu_percent"))
            memory = m.online(m.metric("k8_demo_memory_percent"))
            cards = [
                ("Total node", f"count({m.gate(m.inventory)})", "Jumlah inventaris demo terpilih dengan sampel valid.", "short", CYAN, None, None),
                ("Online", f"sum(({device_up}) == bool 1)", "Perangkat demo aktif; nilai nol hanya dari pengamatan valid.", "short", TEAL, None, None),
                ("Offline", f"sum(({device_up}) == bool 0)", "Skenario offline tetap tampil di inventaris dan status, tidak diubah menjadi nol CPU.", "short", TEAL, None, 1),
                ("CPU rata-rata", f"avg({cpu})", "Rerata CPU perangkat demo aktif dalam pilihan; bukan data host nyata.", "percent", CYAN, 80, 95),
                ("Memori", f"avg({memory})", "Rerata penggunaan memori perangkat demo aktif dalam pilihan.", "percent", PURPLE, 80, 95),
                ("Usia data", f"max({m.freshness()})", "Usia sampel terlama untuk perangkat terpilih. Sampel ≥60 detik, timestamp masa depan, atau exporter down menjadi Tidak ada data.", "s", TEAL, 30, 50),
            ]
        else:
            idle_cpu = m.node("node_cpu_seconds_total", 'mode="idle"')
            cpu = m.node_gate(f'100 * (1 - avg by(instance) (rate({idle_cpu}[$__rate_interval])))')
            memory = m.node_gate(f'100 * (1 - {m.node("node_memory_MemAvailable_bytes")} / {m.node("node_memory_MemTotal_bytes")})')
            service = m.gate(m.metric("k8_service_up"))
            cards = [
                ("Node UP", f"sum({m.exporter} == bool 1)", "Target Node Exporter terpilih yang merespons scrape; bukan jumlah semua host inventaris.", "short", TEAL, None, None),
                ("Scrape gagal", f"sum({m.exporter} == bool 0)", "Scrape gagal untuk target terpilih. Ini tidak membuktikan host mati; periksa jaringan dan exporter.", "short", TEAL, None, 1),
                ("CPU rata-rata", f"avg({cpu})", "Rerata CPU node terpilih yang exporter-nya masih terjangkau. Rate memerlukan ≥2 sampel.", "percent", CYAN, 80, 95),
                ("Memori", f"avg({memory})", "Rerata memori node terpilih; data node dengan exporter down tidak dianggap sehat.", "percent", PURPLE, 80, 95),
                ("Service DOWN", f"sum(({service}) == bool 0)", "Jumlah layanan systemd terkonfigurasi yang berhenti. OpenSSH dapat berstatus berhenti; metrik yang hilang bukan sukses.", "short", TEAL, None, 1),
                ("Usia probe", f"max({m.freshness()})", "Diagnostik kesegaran: usia tetap ditampilkan saat ≥60 detik agar collector macet terlihat. Tetap mengikuti node dan up=1. Nilai negatif menandakan jam tidak sinkron; semua status custom menolak timestamp masa depan.", "s", TEAL, 60, 120),
            ]
        for i, (title, expr, desc, unit, color, warning, critical) in enumerate(cards):
            panel = self.stat(title, (i * 4, 4, 4, 4), expr, desc, unit, color, warning, critical)
            if not self.demo and i == 5:
                panel["fieldConfig"]["defaults"]["mappings"].append({
                    "type": "range", "options": {"from": -1e20, "to": -0.001,
                    "result": {"text": "Jam tidak sinkron", "color": RED}},
                })
        label = "{{device}}" if self.demo else "{{instance}}"
        self.chart("CPU / tren per perangkat", (0, 8, 12, 7), [(cpu, label)],
                   "Pilihan perangkat berlaku pada seluruh deret. Celah data tidak disambung atau diisi nol.", color=CYAN)
        self.chart("Memori / tren per perangkat", (12, 8, 12, 7), [(memory, label)],
                   "Memori terpakai dalam persen. Tidak ada interpolasi melintasi sampel yang hilang.", color=PURPLE)

    def services_and_network(self):
        m = self.m
        service = m.gate(m.metric("k8_demo_service_up" if self.demo else "k8_service_up"))
        columns = [("device", "Perangkat"), ("service", "Layanan")]
        self.table("Layanan / status terkonfigurasi", (0, 15, 12, 7), service, columns,
                   "SIMULASI: status layanan skenario, bukan proses nyata." if self.demo else
                   "Status aktual systemd dari collector: hanya layanan yang dikonfigurasi. Aktif bukan jaminan endpoint/API sehat; OpenSSH tidak diasumsikan selalu aktif.",
                   status=("BERHENTI", "AKTIF"))
        if self.demo:
            queries = [
                (m.online(f'rate({m.metric("k8_demo_network_receive_bytes_total")}[$__rate_interval])'), "{{device}} · masuk"),
                (m.online(f'rate({m.metric("k8_demo_network_transmit_bytes_total")}[$__rate_interval])'), "{{device}} · keluar"),
            ]
        else:
            net_filter = 'device!~"lo|veth.*|docker.*|br-.*"'
            queries = [
                (m.node_gate(f'sum by(instance) (rate({m.node("node_network_receive_bytes_total", net_filter)}[$__rate_interval]))'), "{{instance}} · masuk"),
                (m.node_gate(f'sum by(instance) (rate({m.node("node_network_transmit_bytes_total", net_filter)}[$__rate_interval]))'), "{{instance}} · keluar"),
            ]
        self.chart("Jaringan / masuk & keluar", (12, 15, 12, 7), queries,
                   "Laju byte/detik menggunakan $__rate_interval; perlu ≥2 sampel counter. Tidak ada laju palsu sebelum cukup sampel atau saat perangkat tidak tersedia.", "Bps", TEAL)

    def inventory_and_issues(self):
        m = self.m
        if self.demo:
            inventory = m.gate(f'{m.inventory} * on(instance,device) group_left() {m.metric("k8_demo_device_up")}')
            self.table("Inventaris / perangkat dummy persisten", (0, 22, 14, 8), inventory,
                       [("device", "Perangkat"), ("role", "Peran"), ("address", "Alamat skenario"), ("site", "Lokasi")],
                       "Inventaris SIMULASI. Perangkat offline tetap tercatat selama collector demo segar. Alamat bukan tujuan koneksi atau tombol kontrol.",
                       status=("OFFLINE", "AKTIF"))
            issues = self.table("Isu / skenario yang sedang terlihat", (14, 22, 10, 8),
                                m.gate(m.metric("k8_demo_issue_info")),
                                [("device", "Perangkat"), ("severity", "Prioritas"), ("issue", "Isu")],
                                "Isu dummy mengikuti pilihan perangkat. backup01 memiliki peringatan disk; lab-offline01 offline. Tabel kosong tidak menyimpulkan semua layanan sehat.",
                                value="Sumber", color=AMBER)
            issues["fieldConfig"]["defaults"]["mappings"].append({
                "type": "value", "options": {"1": {"text": "SIMULASI", "color": AMBER}},
            })
            issues["fieldConfig"]["overrides"].append({
                "matcher": {"id": "byName", "options": "Prioritas"},
                "properties": [
                    {"id": "custom.cellOptions", "value": {"type": "color-text"}},
                    {"id": "mappings", "value": [{"type": "value", "options": {
                        "WARNING": {"text": "PERINGATAN", "color": AMBER},
                        "CRITICAL": {"text": "KRITIS", "color": RED},
                        "INFO": {"text": "INFO", "color": CYAN},
                    }}]},
                ],
            })
        else:
            self.table("Inventaris / identitas terverifikasi", (0, 22, 14, 8), m.gate(m.inventory),
                       [("device", "Perangkat"), ("role", "Peran"), ("address", "Alamat"), ("instance", "Target scrape")],
                       "Hanya identitas dengan collector segar dan exporter terjangkau. Target down tetap terlihat pada tabel Node Exporter di sebelah, bukan dinyatakan hilang dari konfigurasi.",
                       value="Sampel", status=("TIDAK VALID", "TERVERIFIKASI"))
            self.table("Node Exporter / akses target", (14, 22, 10, 8), m.exporter,
                       [("instance", "Target scrape")],
                       "Nilai up dari Prometheus sengaja tidak disaring up=1: kegagalan scrape harus tetap terlihat. Mengikuti pilihan node; target yang tidak ada menampilkan Tidak ada data.",
                       status=("TAK TERJANGKAU", "TERJANGKAU"))

    def resources(self):
        m = self.m
        if self.demo:
            disk = m.online(m.metric("k8_demo_disk_percent"))
            uptime = m.online(m.metric("k8_demo_uptime_seconds"))
        else:
            fs = 'mountpoint="/",fstype!~"tmpfs|overlay|squashfs|ramfs"'
            disk = m.node_gate(f'100 * (1 - {m.node("node_filesystem_avail_bytes", fs)} / {m.node("node_filesystem_size_bytes", fs)})')
            uptime = m.node_gate(f'time() - {m.node("node_boot_time_seconds")}')
        self.bars("Disk / kapasitas terpakai", (0, 30, 8, 7), disk,
                  "Amber ≥80%, merah ≥95%. " + ("Nilai disk dummy; backup01 adalah skenario peringatan." if self.demo else "Filesystem root (/), ruang tersedia untuk pengguna non-root."))
        self.bars("Uptime / perangkat aktif", (8, 30, 8, 7), uptime,
                  "Durasi sejak boot; hanya perangkat terpilih yang aktif. " + ("SIMULASI, bukan usia host nyata." if self.demo else "Dihitung dari node_boot_time_seconds."), "s", CYAN)
        if self.demo:
            self.chart("DNS / latensi skenario", (16, 30, 8, 7),
                       [(m.online(f'1000 * {m.metric("k8_demo_dns_duration_seconds")}'), "{{device}}")],
                       "Latensi DNS dummy dalam milidetik; bukan hasil resolusi nyata.", "ms", CYAN)
        else:
            self.table("DNS / hasil resolusi", (16, 30, 8, 7), m.gate(m.metric("k8_dns_success")),
                       [("device", "Perangkat"), ("query", "Nama DNS")],
                       "Keberhasilan probe resolusi aktual. Bind9 aktif di systemd belum tentu berarti resolusi berhasil. Sampel ≥60 detik tidak ditampilkan sebagai berhasil.",
                       status=("GAGAL", "BERHASIL"))

    def database_and_history(self):
        m = self.m
        if self.demo:
            queries = m.maria("k8_demo_mariadb_queries_total", rate=True)
            connections = m.maria("k8_demo_mariadb_connections")
        else:
            queries = m.maria("k8_mariadb_questions_total", rate=True)
            connections = m.maria("k8_mariadb_threads_connected")
        label = "{{device}}"
        self.chart("MariaDB / kueri per detik", (0, 37, 8, 7), [(queries, label)],
                   "Counter Questions menjadi rate menggunakan $__rate_interval; perlu ≥2 sampel. " +
                   ("Beban database adalah skenario dummy." if self.demo else "Hanya probe MariaDB yang berhasil dan collector segar."), "reqps", TEAL)
        self.chart("MariaDB / koneksi aktif", (8, 37, 8, 7), [(connections, label)],
                   "Jumlah koneksi, bukan persentase. " + ("SIMULASI." if self.demo else "Threads_connected hanya ditampilkan saat probe MariaDB berhasil."), "short", PURPLE)
        if self.demo:
            panel = self.add("status-history", "Perangkat / riwayat status sampel", (16, 37, 8, 7),
                             "Riwayat k8_demo_device_up, bukan riwayat pekerjaan Ansible. Merah = offline; celah = sampel tidak valid/tidak tersedia.",
                             status=("OFFLINE", "AKTIF"))
            panel["targets"] = [target(m.gate(m.metric("k8_demo_device_up")), "{{device}}")]
            panel["fieldConfig"]["defaults"]["custom"] = {
                "lineWidth": 0, "fillOpacity": 85, "hideFrom": {"legend": False, "tooltip": False, "viz": False},
            }
            panel["options"] = {
                "showValue": "never", "rowHeight": 0.75, "colWidth": 0.85,
                "legend": {"showLegend": False}, "tooltip": {"mode": "single", "sort": "none"},
            }
        else:
            duration = m.gate(f'1000 * {m.metric("k8_dns_duration_seconds")}')
            duration += f' and on(instance,device,query) ({m.metric("k8_dns_success")} == 1)'
            self.chart("DNS / latensi resolusi berhasil", (16, 37, 8, 7),
                       [(duration, "{{device}} · {{query}}")],
                       "Latensi aktual dalam milidetik. Kegagalan ditampilkan pada tabel DNS, bukan disamarkan sebagai latensi nol.", "ms", CYAN)

    def context(self):
        m = self.m
        if self.demo:
            self.text("Topologi konseptual / SIMULASI", (0, 44, 12, 7), f'''
<div style="padding:8px 12px;color:#CBD5E1;">
  <p style="color:{AMBER};margin:0 0 14px;"><strong>SIMULASI PERMANEN — bukan peta jaringan hasil discovery</strong></p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <tbody>
      <tr><th style="text-align:left;padding:8px;color:{CYAN};">Lapisan layanan</th><td>Bind9 / DNS &nbsp; · &nbsp; MariaDB / data</td></tr>
      <tr><th style="text-align:left;padding:8px;color:{TEAL};">Observabilitas</th><td>Collector demo → Node Exporter → Prometheus → Grafana</td></tr>
      <tr><th style="text-align:left;padding:8px;color:{AMBER};">Skenario disk</th><td>backup01 · peringatan kapasitas</td></tr>
      <tr><th style="text-align:left;padding:8px;color:{RED};">Skenario offline</th><td>lab-offline01 · CPU, memori, trafik tidak tersedia</td></tr>
    </tbody>
  </table>
  <p style="font-size:12px;color:#94A3B8;">Konteks statis untuk delapan perangkat persisten; tabel inventaris dan layanan mengikuti filter. Tidak ada kontrol eksekusi di dashboard.</p>
</div>'''.strip())
            age_per_device = m.gate(f"{m.inventory} * on(instance) group_left() {m.age}")
            self.table("Skenario / cakupan & kesegaran", (12, 44, 12, 7), age_per_device,
                       [("device", "Perangkat"), ("site", "Lokasi"), ("scenario", "Skenario")],
                       "Usia sampel collector diproyeksikan ke inventaris terpilih; bukan timestamp pengukuran independen per perangkat. Hanya sampel 0–59 detik dan exporter up yang tampil.",
                       value="Usia sampel", unit="s")
        else:
            self.maria_context()
            self.stat("GLOBAL / scrape Prometheus", (12, 44, 12, 7), 'min(up{job="prometheus"})',
                      "GLOBAL: tidak mengikuti pilihan node. Status scrape target job=prometheus, bukan health API Grafana dan bukan status semua layanan. Tidak ada fallback sukses saat target hilang.",
                      status=("SCRAPE GAGAL", "SCRAPE BERHASIL"))

    def maria_context(self):
        m = self.m
        panel = self.add("table", "MariaDB / validasi & konteks server", (0, 44, 12, 7),
                         "Probe aktual per target terpilih. Uptime dan slow queries hanya ditampilkan bila probe berhasil. Slow queries adalah counter kumulatif sejak server mulai, bukan rate atau riwayat otomasi.")
        probe = f'max by(instance) ({m.gate(m.metric("k8_mariadb_success"))})'
        # Preserve each failed probe's join key while leaving its measurements unknown.
        # Otherwise missing B/C series could introduce a misleading extra summary row.
        unknown_by_instance = f"(({probe}) * (0 / 0))"
        expressions = [
            probe,
            f'(max by(instance) ({m.maria("k8_mariadb_uptime_seconds")})) or on(instance) {unknown_by_instance}',
            f'(max by(instance) ({m.maria("k8_mariadb_slow_queries_total")})) or on(instance) {unknown_by_instance}',
        ]
        panel["targets"] = [
            target(expr, ref=chr(65 + i), instant=True, table=True, join_placeholder=True)
            for i, expr in enumerate(expressions)
        ]
        panel["transformations"] = [
            {"id": "joinByField", "options": {"byField": "instance", "mode": "outerTabular"}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["instance", "Value #A", "Value #B", "Value #C"]}}},
            {"id": "organize", "options": {
                "excludeByName": {},
                "indexByName": {"instance": 0, "Value #A": 1, "Value #B": 2, "Value #C": 3},
                "renameByName": {"instance": "Target scrape", "Value #A": "Probe", "Value #B": "Uptime DB", "Value #C": "Kueri lambat total"},
            }},
        ]
        panel["options"] = {"showHeader": True, "cellHeight": "sm", "enablePagination": False, "footer": {"show": False}}
        panel["fieldConfig"]["defaults"]["custom"] = {"align": "auto", "cellOptions": {"type": "auto"}, "filterable": True}
        panel["fieldConfig"]["overrides"] = [
            {"matcher": {"id": "byName", "options": "Probe"}, "properties": [
                {"id": "mappings", "value": [copy.deepcopy(NO_DATA_MAPPING), copy.deepcopy(NULL_MAPPING), status_mapping("GAGAL", "BERHASIL")]},
                {"id": "custom.cellOptions", "value": {"type": "color-text"}},
            ]},
            {"matcher": {"id": "byName", "options": "Uptime DB"}, "properties": [{"id": "unit", "value": "s"}]},
        ]

    def footer(self):
        mode = "SIMULASI: semua nilai berasal dari source=demo." if self.demo else "REAL: metrik custom source=real; metrik host dari node_exporter."
        extra = (
            "Dropdown label_values dapat menyimpan label lama; panel tetap menolak sampel kedaluwarsa."
            if self.demo else
            "Status custom memerlukan sampel &lt;60 detik dan exporter up; kartu usia collector sengaja tetap memperlihatkan usia kedaluwarsa."
        )
        self.text("Tentang konsol / observasi, bukan eksekusi", (0, 51, 24, 4), f'''
<div style="padding:6px 12px;color:#94A3B8;font-size:13px;">
  <p style="margin:0 0 8px;color:#CBD5E1;"><strong>{escape(mode)}</strong> &nbsp; Bind9 / MariaDB → collector / Node Exporter → Prometheus → Grafana.</p>
  <p style="margin:0 0 8px;">SSH dan Ansible melakukan provisioning melalui terminal. Dashboard ini tidak menjalankan perintah, deployment, atau menyajikan riwayat eksekusi otomasi. Status systemd Grafana bukan pemeriksaan API Grafana.</p>
  <p style="margin:0;">{extra} Rate perlu ≥2 sampel. <strong>Tidak ada data ≠ sehat.</strong></p>
</div>'''.strip())

    def build(self):
        self.hero()
        self.summary()
        self.services_and_network()
        self.inventory_and_issues()
        self.resources()
        self.database_and_history()
        self.context()
        self.footer()
        variable_name = "device" if self.demo else "node"
        variable_query = (
            "label_values(k8_demo_inventory_info, device)" if self.demo else
            'label_values(up{job="node_exporter"}, instance)'
        )
        return {
            "id": None, "uid": "kelompok8-demo" if self.demo else "kelompok8-overview",
            "title": "Kelompok 8 / Demo Lab [SIMULASI]" if self.demo else "Kelompok 8 / Operasional [REAL]",
            "description": "Konsol native Grafana. " + ("Dummy persisten, terpisah dari metrik nyata." if self.demo else "Monitoring nyata dengan validasi kesegaran collector."),
            "schemaVersion": 41, "version": 1, "editable": True,
            "style": "dark", "timezone": "browser", "fiscalYearStartMonth": 0,
            "graphTooltip": 1, "refresh": "15s",
            "time": {"from": "now-15m" if self.demo else "now-1h", "to": "now"},
            "timepicker": {"refresh_intervals": ["15s", "30s", "1m", "5m"], "hidden": False},
            "tags": ["kelompok8", "native-grafana", "simulasi" if self.demo else "operasional"],
            "annotations": {"list": []},
            "links": [
                {"title": "Demo Lab", "type": "link", "icon": "dashboard", "url": "/d/kelompok8-demo", "targetBlank": False, "includeVars": False, "keepTime": False},
                {"title": "Operasional", "type": "link", "icon": "dashboard", "url": "/d/kelompok8-overview", "targetBlank": False, "includeVars": False, "keepTime": False},
            ],
            "templating": {"list": [{
                "name": variable_name, "label": "Perangkat demo" if self.demo else "Node / target scrape",
                "type": "query", "datasource": dict(DS),
                "query": {"query": variable_query, "refId": "StandardVariableQuery"},
                "definition": variable_query, "refresh": 2, "sort": 1,
                "multi": True, "includeAll": True, "allValue": ".*",
                "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
                "options": [], "regex": "", "hide": 0, "skipUrlSync": False,
                "description": (
                    "Inventaris dummy via label_values; label lama mungkin tetap muncul, tetapi seluruh panel memvalidasi timestamp dan exporter."
                    if self.demo else "Target node_exporter, termasuk target scrape yang gagal."
                ),
            }]},
            "panels": self.panels,
        }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_expression(expr):
    """Check delimiters outside quoted strings, without claiming to parse PromQL."""
    pairs, stack = {")": "(", "]": "[", "}": "{"}, []
    quoted = escaped = False
    for char in expr:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            require(bool(stack) and stack.pop() == pairs[char], f"Unbalanced expression: {expr}")
    require(not quoted and not stack, f"Unclosed expression: {expr}")
    require("or vector(0)" not in expr and "or vector(1)" not in expr, "Unsafe health fallback")
    if "rate(" in expr:
        require("[$__rate_interval]" in expr, "Rates must use the Grafana rate interval")


def validate(dashboard, demo):
    expected_uid = "kelompok8-demo" if demo else "kelompok8-overview"
    require(dashboard["uid"] == expected_uid, "Dashboard UID changed")
    require(dashboard["schemaVersion"] == 41, "Wrong Grafana schemaVersion")
    panels = dashboard["panels"]
    require(len(panels) == 22, "Expected exactly 22 panels")
    require([p["id"] for p in panels] == list(range(1, 23)), "Panel IDs must be unique")
    for link in dashboard["links"]:
        require(link["url"] in ("/d/kelompok8-demo", "/d/kelompok8-overview"), "External/filter-leaking navigation")
        require(not link["targetBlank"] and not link["includeVars"] and not link["keepTime"], "Navigation must start clean in the same tab")
    variable = dashboard["templating"]["list"][0]
    require(variable["datasource"] == DS, "Wrong variable datasource UID")
    require(variable["multi"] and variable["includeAll"] and variable["current"]["value"] == ["$__all"], "Variable must default to all")
    occupied = set()
    allowed_types = {"text", "stat", "timeseries", "bargauge", "table", "status-history"}
    for panel in panels:
        require(panel["type"] in allowed_types, "Non-native panel type")
        grid = panel["gridPos"]
        require(0 <= grid["x"] < 24 and grid["x"] + grid["w"] <= 24, "Invalid grid width")
        for x in range(grid["x"], grid["x"] + grid["w"]):
            for y in range(grid["y"], grid["y"] + grid["h"]):
                require((x, y) not in occupied, "Overlapping panels")
                occupied.add((x, y))
        if panel["type"] == "text":
            content = panel["options"]["content"]
            require(not re.search(r"<(script|iframe|img|style|form|button)\b|\bon\w+\s*=|https?://|javascript:", content, re.I), "Unsafe/external HTML")
            continue
        require(panel["datasource"] == DS, "Wrong panel datasource UID")
        require(panel["fieldConfig"]["defaults"]["noValue"] == NO_DATA, "Missing empty-state message")
        for query in panel["targets"]:
            require(query["datasource"] == DS, "Wrong target datasource UID")
            expr = query["expr"]
            validate_expression(expr)
            if query["instant"]:
                require(expr.endswith((EMPTY, EMPTY_INSTANCE)), "Instant queries must preserve unknown states")
            fresh = bool(re.search(r"\)\s*<\s*60\s*\)", expr) and re.search(r"\)\s*>=\s*0\s*\)", expr))
            require("$device" in expr if demo else ("$node" in expr or panel["title"].startswith("GLOBAL /")), "Unscoped data panel")
            if demo:
                require('source="real"' not in expr and not re.search(r"\bnode_\w+\{", expr), "Real metrics leaked into demo")
                require('source="demo"' in expr and "k8_sample_timestamp_seconds" in expr and fresh, "Demo freshness gate missing")
                require('up{job="node_exporter"} == 1)' in expr, "Demo exporter gate missing")
            else:
                require("k8_demo_" not in expr and 'source="demo"' not in expr, "Demo metrics leaked into real dashboard")
                if re.search(r"\bk8_\w+\{", expr):
                    require('source="real"' in expr and 'up{job="node_exporter",instance=~"$node"} == 1)' in expr, "Real custom metric gate missing")
                    if panel["title"] != "Usia probe":
                        require(fresh, "Real freshness gate missing")
                if re.search(r"\bnode_\w+\{", expr):
                    require('up{job="node_exporter",instance=~"$node"} == 1)' in expr, "Standard node health gate missing")
            if panel["type"] == "table":
                require(query["format"] == "table" and query["instant"] and not query["range"], "Tables must use instant Prometheus queries")
                require(any(t["id"] == "organize" for t in panel["transformations"]), "Missing table organization")
            if panel["type"] in ("stat", "bargauge"):
                require(query["instant"] and panel["options"]["reduceOptions"]["calcs"] == ["last"], "Instant KPIs must not revive an older healthy value")
    hero = panels[0]["options"]["content"]
    require(("SIMULASI" if demo else "REAL") in hero, "Missing permanent source badge")
    if demo:
        require(AMBER in hero and "Data dummy" in hero, "Demo needs an amber warning")
    require(max(p["gridPos"]["y"] + p["gridPos"]["h"] for p in panels) == 55, "Unexpected dashboard height")
    # A stdlib JSON round trip also catches non-JSON objects and invalid NaN literals.
    require(json.loads(json.dumps(dashboard, allow_nan=False)) == dashboard, "JSON round-trip failed")


def serialized(dashboard, template=False):
    body = json.dumps(dashboard, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    return RAW_START + body + RAW_END if template else body


def parse_artifact(content, template=False):
    if template:
        require(content.startswith(RAW_START) and content.endswith(RAW_END), "Missing full Jinja raw wrapper")
        content = content[len(RAW_START):-len(RAW_END)]
        require("{%" not in content, "Nested Jinja statement inside raw block")
    return json.loads(content, parse_constant=reject_non_json_constant)


def reject_non_json_constant(value):
    raise ValueError(f"Non-JSON constant: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate existing artifacts and generator parity without writing")
    args = parser.parse_args()
    artifacts = [(REAL_PATH, Dashboard(False).build(), True), (DEMO_PATH, Dashboard(True).build(), False)]
    for path, dashboard, template in artifacts:
        validate(dashboard, demo=not template)
        expected = serialized(dashboard, template)
        require(parse_artifact(expected, template) == dashboard, "Serialization mismatch")
        if args.check:
            actual = path.read_text(encoding="utf-8")
            validate(parse_artifact(actual, template), demo=not template)
            require(actual == expected, f"Artifact differs from generator: {path}")
        else:
            path.write_text(expected, encoding="utf-8", newline="\n")
            validate(parse_artifact(path.read_text(encoding="utf-8"), template), demo=not template)
        action = "Validated" if args.check else "Built and validated"
        print(f"{action}: {path} | uid={dashboard['uid']} | panels={len(dashboard['panels'])} | schema=41")
    print("Checks: JSON, artifact parity, IDs/layout, datasource, selection, source isolation, freshness, native panels, navigation, unknown states.")
    print("Offline validation only: Grafana rendering and PromQL execution require the provisioned stack; label_values may retain stale labels, never stale panel success.")


if __name__ == "__main__":
    main()

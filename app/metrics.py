"""Read-only, inventory-scoped Prometheus queries; no synthetic measurements."""
import copy
import ipaddress
import json
import math
import re
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEMO_KEYS = frozenset(('edge-gw01', 'core-sw01', 'dns01', 'db01', 'monitor01', 'app01', 'backup01', 'lab-offline01'))
FIELDS = ('cpu', 'memory', 'disk', 'rx', 'tx', 'up')
HISTORY_FIELDS = ('cpu', 'memory', 'rx', 'tx')
_cache = {}
_cache_lock = threading.Lock()


class MetricsUnavailable(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MetricsUnavailable()


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def measurement(value, field):
    result = number(value)
    if result is None or result < 0:
        return None
    if field in ('cpu', 'memory', 'disk') and result > 100:
        return None
    if field == 'up' and result not in (0, 1):
        return None
    return result


def instance(device):
    address = ipaddress.ip_address(device['address'])
    host = '[' + str(address) + ']' if address.version == 6 else str(address)
    return host + ':' + str(device.get('exporter_port', 9100))


def label_selection(label, values):
    values = sorted(set(values))
    if len(values) == 1:
        return label + '=' + json.dumps(values[0])
    # Escape only RE2 metacharacters; JSON quoting supplies PromQL string escaping.
    escaped = [re.sub(r'([.\\+*?\[\](){}|^$])', r'\\\1', value) for value in values]
    return label + '=~' + json.dumps('^(' + '|'.join(escaped) + ')$')


def queries(environment, devices):
    if environment == 'demo':
        keys = [row.get('metric_key') for row in devices if row.get('metric_key') in DEMO_KEYS]
        if not keys:
            return {}
        selector = 'source="demo",job="node_exporter",' + label_selection('device', keys)
        def metric(name):
            return name + '{' + selector + '}'
        stamp = 'k8_sample_timestamp_seconds{source="demo",job="node_exporter"}'
        age = '(time() - ' + stamp + ')'
        exporter = 'up{job="node_exporter"}'
        exporter_age = '(time() - timestamp(' + exporter + '))'
        gate = (f' and on(instance) (({age} < 60) and ({age} >= 0))'
                f' and on(instance) (({exporter} == 1) and ({exporter_age} < 60) and ({exporter_age} >= 0))')
        online = ' and on(instance,device) (' + metric('k8_demo_device_up') + ' == 1)'
        expressions = {
            'cpu': metric('k8_demo_cpu_percent'),
            'memory': metric('k8_demo_memory_percent'),
            'disk': metric('k8_demo_disk_percent'),
            'rx': 'rate(' + metric('k8_demo_network_receive_bytes_total') + '[2m])',
            'tx': 'rate(' + metric('k8_demo_network_transmit_bytes_total') + '[2m])',
            'up': metric('k8_demo_device_up'),
        }
        return {field: '(' + expr + ')' + gate + (online if field != 'up' else '')
                for field, expr in expressions.items()}

    selector = 'job="node_exporter",' + label_selection('instance', [instance(row) for row in devices])
    def node(name, extra=''):
        return name + '{' + selector + (',' + extra if extra else '') + '}'
    exporter = node('up')
    age = '(time() - timestamp(' + exporter + '))'
    fresh = f' and on(instance) (({age} < 60) and ({age} >= 0))'
    online = f' and on(instance) ({exporter} == 1)'
    root = 'mountpoint="/",fstype!~"tmpfs|overlay|squashfs"'
    expressions = {
        'cpu': '100 * (1 - avg by(instance) (rate(' + node('node_cpu_seconds_total', 'mode="idle"') + '[2m])))',
        'memory': '100 * (1 - ' + node('node_memory_MemAvailable_bytes') + ' / ' + node('node_memory_MemTotal_bytes') + ')',
        'disk': 'avg by(instance) (100 * (1 - ' + node('node_filesystem_avail_bytes', root) + ' / '
                + node('node_filesystem_size_bytes', root) + '))',
        'rx': 'sum by(instance) (rate(' + node('node_network_receive_bytes_total', 'device!="lo"') + '[2m]))',
        'tx': 'sum by(instance) (rate(' + node('node_network_transmit_bytes_total', 'device!="lo"') + '[2m]))',
        'up': exporter,
    }
    return {field: '(' + expr + ')' + fresh + (online if field != 'up' else '')
            for field, expr in expressions.items()}


def fetch(base_url, expression, now, history=False):
    url = urlsplit(base_url)
    if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise MetricsUnavailable()
    params = {'query': expression}
    if history:
        end = int(now // 30) * 30
        params.update(start=end - 1800, end=end, step=30)
    else:
        params['time'] = now
    path = '/api/v1/query_range' if history else '/api/v1/query'
    req = Request(base_url.rstrip('/') + path + '?' + urlencode(params), headers={'Accept': 'application/json'}, method='GET')
    with build_opener(NoRedirect()).open(req, timeout=3) as response:
        body = response.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise MetricsUnavailable()
    data = json.loads(body)
    expected = 'matrix' if history else 'vector'
    if (not isinstance(data, dict) or data.get('status') != 'success' or not isinstance(data.get('data'), dict)
            or data['data'].get('resultType') != expected or not isinstance(data['data'].get('result'), list)):
        raise MetricsUnavailable()
    return data['data']['result']


def aggregate(values, field):
    known = [value for value in values if value is not None]
    if not known:
        return None
    if field == 'up':
        return min(known)
    total = sum(known)
    if not math.isfinite(total):
        return None
    return total if field in ('rx', 'tx') else total / len(known)


def empty(environment, devices, now):
    return {'available': False, 'source': environment, 'error': 'Metrik belum tersedia untuk perangkat terpilih.',
            'summary': {field: None for field in FIELDS if field != 'up'}, 'history': [],
            'per_device': [{'device_id': row['id'], 'name': row['name'], 'cpu': None, 'memory': None,
                            'disk': None, 'up': None} for row in devices], 'updated_at': iso(now)}


def series_key(series, environment):
    labels = series.get('metric', {})
    if not isinstance(labels, dict):
        return None
    if environment == 'demo':
        if labels.get('source') != 'demo':
            return None
        return labels.get('device')
    return labels.get('instance')


def source_keys(environment, devices):
    return {row['id']: (row.get('metric_key') if row.get('metric_key') in DEMO_KEYS else None)
            if environment == 'demo' else instance(row) for row in devices}


ANOMALY_LABELS = {'cpu': 'CPU', 'memory': 'memori', 'disk': 'disk', 'rx': 'lalu lintas masuk', 'tx': 'lalu lintas keluar'}
ANOMALY_FIELDS = tuple(ANOMALY_LABELS)


def device_history(environment, devices, config):
    """Per-device 30-minute series keyed by device id; missing samples stay missing."""
    history = {row['id']: {} for row in devices}
    expressions = queries(environment, devices) if devices else {}
    if not expressions:
        return history
    keys = source_keys(environment, devices)
    selected = {key for key in keys.values() if key is not None}
    if not selected:
        return history
    base = config.get('prometheus_url', 'http://127.0.0.1:9090')
    now = time.time()
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {field: pool.submit(fetch, base, expressions[field], now, True) for field in ANOMALY_FIELDS}
        results = {field: future.result() for field, future in futures.items()}
    owners = {}
    for device_id, key in keys.items():
        if key is not None:
            owners.setdefault(key, []).append(device_id)
    for field in ANOMALY_FIELDS:
        for series in results[field]:
            key = series_key(series, environment)
            if not isinstance(key, str) or key not in selected:
                continue
            samples = series.get('values', [])
            if not isinstance(samples, list):
                continue
            points = []
            for sample in samples:
                if not isinstance(sample, (tuple, list)) or len(sample) != 2:
                    continue
                stamp, value = number(sample[0]), measurement(sample[1], field)
                if stamp is not None and value is not None:
                    points.append((stamp, value))
            for device_id in owners[key]:
                history[device_id][field] = points
    return history


def anomalies(history, now):
    """Rule-based deviations from each device's own recent baseline.

    A reading only counts when a current sample and enough older samples exist;
    devices without data are never judged either way.
    """
    found = []
    for device_id, fields in history.items():
        for field in ANOMALY_FIELDS:
            points = sorted(fields.get(field, []))
            recent = [value for stamp, value in points if now - stamp <= 120]
            baseline = [value for stamp, value in points if now - stamp >= 300]
            if not recent or len(baseline) < 8:
                continue
            current, middle = recent[-1], statistics.median(baseline)
            if field in ('cpu', 'memory'):
                hit = current >= 70 and current - middle >= 25
            elif field == 'disk':
                hit = current >= 80 and current - min(baseline) >= 3
            else:
                hit = middle > 0 and current >= 5 * middle and current >= 1_000_000
            if hit:
                found.append({'device_id': device_id, 'field': field, 'label': ANOMALY_LABELS[field],
                              'current': round(current, 2), 'baseline': round(middle, 2)})
    return found


def has_recent_sample(history, device_id, field, now):
    return any(now - stamp <= 120 for stamp, _ in history.get(device_id, {}).get(field, []))


def assemble(environment, devices, now, results):
    result = empty(environment, devices, now)
    keys = source_keys(environment, devices)
    selected = {key for key in keys.values() if key is not None}
    current = {key: {field: [] for field in FIELDS} for key in selected}
    for field in FIELDS:
        for series in results.get((field, False), []):
            if not isinstance(series, dict):
                continue
            key = series_key(series, environment)
            if not isinstance(key, str) or key not in selected:
                continue
            sample = series.get('value')
            if not isinstance(sample, (tuple, list)) or len(sample) != 2:
                continue
            stamp = number(sample[0])
            value = measurement(sample[1], field)
            if stamp is not None and 0 <= now - stamp < 60 and value is not None:
                current[key][field].append(value)
    readings = {key: {field: aggregate(samples, field) for field, samples in fields.items()}
                for key, fields in current.items()}
    for reading in readings.values():
        # Keep an explicit exporter/device down value, never treat it as healthy usage.
        if reading['up'] != 1:
            for field in FIELDS:
                if field != 'up':
                    reading[field] = None
    for row in result['per_device']:
        reading = readings.get(keys[row['device_id']], {})
        for field in ('cpu', 'memory', 'disk', 'up'):
            row[field] = reading.get(field)
    result['available'] = any(any(value is not None for value in reading.values()) for reading in readings.values())
    if result['available']:
        result['error'] = None
        for field in result['summary']:
            result['summary'][field] = aggregate([reading[field] for reading in readings.values()], field)

    end = int(now // 30) * 30
    buckets = {stamp: {field: {} for field in HISTORY_FIELDS} for stamp in range(end - 1800, end + 1, 30)}
    has_history = False
    for field in HISTORY_FIELDS:
        for series in results.get((field, True), []):
            if not isinstance(series, dict):
                continue
            key = series_key(series, environment)
            if not isinstance(key, str) or key not in selected:
                continue
            samples = series.get('values', [])
            if not isinstance(samples, list):
                continue
            for sample in samples:
                if not isinstance(sample, (tuple, list)) or len(sample) != 2:
                    continue
                stamp = number(sample[0])
                value = measurement(sample[1], field)
                if stamp in buckets and value is not None:
                    buckets[stamp][field].setdefault(key, []).append(value)
                    has_history = True
    if has_history:
        for stamp, fields in buckets.items():
            entry = {'time': iso(stamp)}
            for field, per_key in fields.items():
                entry[field] = aggregate([aggregate(values, field) for values in per_key.values()], field)
            result['history'].append(entry)
    return result


def collect(environment, devices, config):
    now = time.time()
    base = config.get('prometheus_url', 'http://127.0.0.1:9090')
    signature = tuple(sorted((row['id'], row['name'], row['address'], row.get('exporter_port', 9100),
                              row.get('metric_key', ''), str(row.get('updated_at', ''))) for row in devices))
    cache_key = (base, environment, signature)
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return copy.deepcopy(cached[1])
    response = empty(environment, devices, now)
    try:
        expressions = queries(environment, devices) if devices else {}
        if expressions:
            tasks = [(field, False) for field in FIELDS] + [(field, True) for field in HISTORY_FIELDS]
            # Bounded fan-out; a single response does not wait for ten sequential timeouts.
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {key: pool.submit(fetch, base, expressions[key[0]], now, key[1]) for key in tasks}
                results = {key: future.result() for key, future in futures.items()}
            response = assemble(environment, devices, now, results)
    except Exception:
        # Prometheus addresses, queries, response bodies and transport errors stay server-side.
        response['error'] = 'Layanan metrik belum tersedia. Coba lagi nanti.'
    with _cache_lock:
        expired = [key for key, item in _cache.items() if item[0] <= time.monotonic()]
        for key in expired:
            del _cache[key]
        if len(_cache) >= 128:
            del _cache[next(iter(_cache))]
        _cache[cache_key] = (time.monotonic() + 10, copy.deepcopy(response))
    return response

import ipaddress

from db import settings

SERVICES = {
    'dns': {'id': 'dns', 'label': 'DNS', 'port': 53, 'unit': 'named', 'protocol': 'dns'},
    'mariadb': {'id': 'mariadb', 'label': 'MariaDB', 'port': 3306, 'unit': 'mariadb', 'protocol': 'tcp'},
    'ssh': {'id': 'ssh', 'label': 'SSH', 'port': 22, 'unit': 'ssh', 'protocol': 'tcp'},
    'prometheus': {'id': 'prometheus', 'label': 'Prometheus', 'port': 9090, 'unit': 'prometheus', 'protocol': 'tcp'},
    'grafana': {'id': 'grafana', 'label': 'Grafana', 'port': 3000, 'unit': 'grafana-server', 'protocol': 'tcp'},
    'node_exporter': {'id': 'node_exporter', 'label': 'Node Exporter', 'port': 9100, 'unit': 'prometheus-node-exporter', 'protocol': 'tcp'},
}
ACTIONS = {
    'audit': {'id': 'audit', 'label': 'Audit perangkat', 'description': 'Baca identitas sistem melalui Ansible tanpa perubahan konfigurasi.', 'requires_approval': False, 'requires_service': False},
    'collect_evidence': {'id': 'collect_evidence', 'label': 'Kumpulkan bukti sistem', 'description': 'Baca unit gagal, kapasitas, memori, uptime, dan listener. Tidak mengubah apa pun.', 'requires_approval': False, 'requires_service': False},
    'diagnose': {'id': 'diagnose', 'label': 'Diagnosis layanan', 'description': 'Baca status unit, log terakhir, disk, dan memori. Tidak mengubah apa pun; hasil dilampirkan ke insiden.', 'requires_approval': False, 'requires_service': True},
    'ensure_service': {'id': 'ensure_service', 'label': 'Pastikan layanan aktif', 'description': 'Aktifkan layanan terpilih dan verifikasi hasilnya.', 'requires_approval': True, 'requires_service': True},
    'restart_service': {'id': 'restart_service', 'label': 'Restart layanan', 'description': 'Restart satu layanan terpilih; koneksi layanan dapat terputus sementara.', 'requires_approval': True, 'requires_service': True},
    'reload_service': {'id': 'reload_service', 'label': 'Muat ulang layanan', 'description': 'Muat ulang konfigurasi layanan yang mendukung reload tanpa restart penuh, lalu verifikasi.', 'requires_approval': True, 'requires_service': True},
}
# Actions that may bypass the approval gate on devices the administrator has
# explicitly marked auto-approve. New or disruptive actions are excluded by default.
AUTO_APPROVABLE = ('ensure_service', 'restart_service')
SERVICE_ACTIONS = tuple(action for action, definition in ACTIONS.items() if definition['requires_service'])
RELOADABLE_SERVICES = ('dns', 'prometheus')


def allowed_address(address, config=None):
    config = settings() if config is None else config
    try:
        target = ipaddress.ip_address(address)
        if target.is_multicast or target.is_unspecified or target.is_link_local:
            return False
        return any(target in ipaddress.ip_network(network) for network in config['allowed_networks'])
    except ValueError:
        return False


def managed_host(address, config=None):
    config = settings() if config is None else config
    if not allowed_address(address, config):
        return None
    return config['managed_hosts'].get(address)

import json
from pathlib import Path
import sys

import pymysql
from werkzeug.security import generate_password_hash


DEMO_DEVICES = [
    ('edge-gw01', '192.0.2.1', 'router', 'Jakarta', ['ssh'], None, 1, 22),
    ('core-sw01', '192.0.2.2', 'switch', 'Jakarta', ['ssh'], 'edge-gw01', 1, 18),
    ('dns01', '192.0.2.10', 'server', 'Jakarta', ['dns', 'ssh'], 'core-sw01', 1, 31),
    ('db01', '192.0.2.30', 'server', 'Jakarta', ['mariadb', 'ssh'], 'core-sw01', 1, 56),
    ('monitor01', '192.0.2.20', 'server', 'Jakarta', ['prometheus', 'grafana', 'node_exporter'], 'core-sw01', 1, 42),
    ('app01', '192.0.2.40', 'server', 'Jakarta', ['ssh', 'node_exporter'], 'core-sw01', 1, 48),
    ('backup01', '192.0.2.50', 'storage', 'Surabaya', ['ssh'], 'edge-gw01', 1, 87),
    ('branch-offline01', '192.0.2.60', 'router', 'Surabaya', ['ssh'], 'edge-gw01', 0, 25),
]


def seed(cursor, initial_password):
    changes = 0
    cursor.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
    if not cursor.fetchone():
        if len(initial_password) < 12:
            raise ValueError('Password awal administrator minimal 12 karakter.')
        cursor.execute("INSERT INTO users(username,password_hash,role) VALUES('admin',%s,'admin')", (generate_password_hash(initial_password, method='scrypt'),))
        changes += 1
    cursor.execute("SELECT id FROM devices WHERE environment='demo' LIMIT 1")
    initial_demo = [] if cursor.fetchone() else DEMO_DEVICES
    for name, address, kind, site, services, parent_name, online, disk in initial_demo:
        parent_id = None
        if parent_name:
            cursor.execute("SELECT id FROM devices WHERE environment='demo' AND name=%s", (parent_name,))
            parent_id = cursor.fetchone()['id']
        metric_key = 'lab-offline01' if name == 'branch-offline01' else name
        cursor.execute("INSERT INTO devices(name,address,environment,kind,site,services_json,notes,parent_id,metric_key) VALUES(%s,%s,'demo',%s,%s,%s,%s,%s,%s)",
                       (name, address, kind, site, json.dumps(services), 'Perangkat simulasi persisten. Alamat tidak digunakan untuk koneksi nyata.', parent_id, metric_key))
        device_id = cursor.lastrowid
        service_state = {service: online for service in services}
        if name == 'app01':
            service_state['ssh'] = 0
        cursor.execute('INSERT INTO demo_state(device_id,online,services_json,disk_percent) VALUES(%s,%s,%s,%s)', (device_id, online, json.dumps(service_state), disk))
        changes += 1
    cursor.execute("SELECT id FROM devices WHERE environment='real' AND name='localhost'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO devices(name,address,environment,kind,site,services_json,notes) VALUES('localhost','127.0.0.1','real','server','Lokal',%s,%s)",
                       (json.dumps(['dns', 'mariadb', 'ssh', 'prometheus', 'grafana', 'node_exporter']), 'Host lokal. Pemeriksaan menampilkan kondisi layanan sebenarnya.'))
        changes += 1
    return changes


def main():
    import db
    config = db.settings()
    secrets = json.load(sys.stdin)
    client = pymysql.connect(unix_socket=config['db_socket'], user='root', password=secrets.get('mariadb_login_password', ''),
                             database=config['db_name'], charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    try:
        with client.cursor() as cursor:
            for statement in (Path(__file__).parent / 'schema.sql').read_text().split(';'):
                if statement.strip():
                    cursor.execute(statement)
            migrations = [
                ('devices', 'auto_approve',
                 'ALTER TABLE devices ADD COLUMN auto_approve TINYINT(1) NOT NULL DEFAULT 0 AFTER status'),
                ('users', 'disabled', 'ALTER TABLE users ADD COLUMN disabled TINYINT(1) NOT NULL DEFAULT 0'),
            ]
            for table, column, statement in migrations:
                cursor.execute("SELECT COUNT(*) AS total FROM information_schema.columns "
                               "WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s", (table, column))
                if cursor.fetchone()['total'] == 0:
                    cursor.execute(statement)
            # Time-ordered retention deletes need a created_at index on every growing table.
            for table in ('checks', 'jobs', 'audit_events'):
                index = table + '_created'
                cursor.execute("SELECT COUNT(*) AS total FROM information_schema.statistics "
                               "WHERE table_schema=DATABASE() AND table_name=%s AND index_name=%s", (table, index))
                if cursor.fetchone()['total'] == 0:
                    cursor.execute(f'CREATE INDEX {index} ON {table}(created_at)')
            cursor.execute("SELECT COUNT(*) AS total FROM information_schema.tables "
                           "WHERE table_schema=DATABASE() AND table_name='ai_settings'")
            if cursor.fetchone()['total'] == 0:
                cursor.execute('CREATE TABLE ai_settings (id TINYINT PRIMARY KEY, settings_json LONGTEXT NOT NULL, '
                               'updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), '
                               'updated_by BIGINT NULL, FOREIGN KEY (updated_by) REFERENCES users(id))')
            changes = seed(cursor, secrets.get('jalatantra_admin_password', ''))
        client.commit()
        print(json.dumps({'seeded': changes}))
    except Exception:
        client.rollback()
        raise
    finally:
        client.close()


if __name__ == '__main__':
    main()

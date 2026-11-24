import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pymysql


def settings():
    return json.loads(Path(os.environ.get('JALATANTRA_CONFIG', '/etc/jalatantra/config.json')).read_text())


@contextmanager
def connection():
    config = settings()
    client = pymysql.connect(
        unix_socket=config.get('db_socket', '/run/mysqld/mysqld.sock'),
        user=os.environ.get('JALATANTRA_DB_USER', 'jalatantra'),
        password=config.get('db_password', ''),
        database=config.get('db_name', 'jalatantra'), charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor, autocommit=False,
        connect_timeout=5, read_timeout=10, write_timeout=10,
        init_command="SET time_zone = '+00:00'",
    )
    try:
        yield client
        client.commit()
    except Exception:
        client.rollback()
        raise
    finally:
        client.close()


def rows(sql, params=()):
    with connection() as client, client.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def one(sql, params=()):
    result = rows(sql, params)
    return result[0] if result else None


def execute(sql, params=()):
    with connection() as client, client.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.lastrowid


def audit(actor, action, environment, detail, device_id=None):
    execute('INSERT INTO audit_events(actor,action,environment,detail,device_id) VALUES(%s,%s,%s,%s,%s)',
            (actor, action, environment, detail[:1000], device_id))


def note_incident(cursor, incident_id, actor, action, status, note=None):
    """Append to an incident's handling timeline; earlier notes are never overwritten."""
    cursor.execute('INSERT INTO incident_events(incident_id,actor,action,status,note) VALUES(%s,%s,%s,%s,%s)',
                   (incident_id, actor, action, status, note[:4000] if note else None))


def public(row):
    if row is None:
        return None
    result = {}
    for key, value in row.items():
        if key in ('password_hash', 'token_hash', 'archived_at'):
            continue
        if key.endswith('_json'):
            result[key[:-5]] = json.loads(value) if value else None
        elif isinstance(value, datetime):
            result[key] = value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
        else:
            result[key] = value
    return result

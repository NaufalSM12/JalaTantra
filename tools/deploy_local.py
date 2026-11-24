#!/usr/bin/env python3
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    if sys.platform != "linux" or os.geteuid() != 0:
        raise SystemExit("Jalankan di Ubuntu sebagai root: sudo python3 tools/deploy_local.py")
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets-stdin", action="store_true")
    parser.add_argument("--tags")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print("Provisioning localhost saja. Secret sementara di /run (0600), dihapus otomatis.", flush=True)
    if args.secrets_stdin:
        secrets = json.load(sys.stdin)
    else:
        current = getpass.getpass("Password root MariaDB saat ini (kosong untuk fresh install): ")
        app = getpass.getpass("Password akun aplikasi MariaDB: ")
        grafana = getpass.getpass("Password admin Grafana (hanya dipakai pada instalasi pertama): ")
        portal = getpass.getpass("Password awal admin JalaTantra (minimal 12 karakter; kosong jika sudah dibuat): ")
        if not app or not grafana:
            raise SystemExit("Password aplikasi dan Grafana tidak boleh kosong.")
        secrets = {
            "mariadb_login_password": current,
            "mariadb_app_password": app,
            "grafana_admin_password": grafana,
            "jalatantra_admin_password": portal,
        }
    environment = {**os.environ, "ANSIBLE_ROLES_PATH": str(root / "roles")}
    with tempfile.NamedTemporaryFile(mode="w+", dir="/run", prefix="k8-ansible-", suffix=".json") as credentials:
        json.dump(secrets, credentials)
        credentials.flush()
        command = [
            "ansible-playbook", "-i", str(root / "inventory/hosts.yml"),
            str(root / "playbooks/site.yml"), "--limit", "localhost", "-e", "@" + credentials.name,
        ]
        if args.tags:
            command.extend(["--tags", args.tags])
        result = subprocess.run(command, env=environment, cwd=root, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

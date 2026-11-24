#!/bin/bash
# Deployment lokal JalaTantra (Ubuntu WSL, root).
# Baca JSON secret dari stdin: mariadb_login_password, mariadb_app_password,
# grafana_admin_password, dan opsional jalatantra_admin_password (digenerate bila kosong).
# Secret sementara 0600 di /run, dihapus setelah selesai.
set -u
cd "/mnt/e/AMJ-Network infrastruktur automation" || exit 1
python3 -c '
import json, os, secrets, sys
data = json.load(sys.stdin)
for key in ("mariadb_login_password", "mariadb_app_password", "grafana_admin_password"):
    if not isinstance(data.get(key), str):
        raise SystemExit("Secret stdin tidak lengkap: " + key)
if not data.get("jalatantra_admin_password"):
    data["jalatantra_admin_password"] = "JtLocal-" + secrets.token_urlsafe(9)
    print("JALATANTRA_ADMIN_INITIAL_PASSWORD=" + data["jalatantra_admin_password"], flush=True)
fd = os.open("/run/jt-deploy-secrets.json", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as handle:
    json.dump(data, handle)
' || exit 1
python3 tools/deploy_local.py --tags jalatantra --secrets-stdin < /run/jt-deploy-secrets.json
rc=$?
rm -f /run/jt-deploy-secrets.json
exit $rc
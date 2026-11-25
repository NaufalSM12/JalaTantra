# Panduan Deployment JalaTantra dari GitHub ke Ubuntu

Panduan ini memasang JalaTantra pada satu server Ubuntu 24.04 dari repository GitHub:

```text
https://github.com/NaufalSM12/JalaTantra.git
```

Semua kode diambil dari branch `main`. Konfigurasi lokal, vault, kata sandi, kunci API,
dan backup **tidak** disimpan di repository.

> **Prinsip aman:** jalankan pemeriksaan baca-saja lebih dahulu. Portal hanya mengikat
> `127.0.0.1`; akses jarak jauh dilakukan melalui SSH tunnel. Jangan membuka port
> aplikasi langsung ke internet.

---

## 1. Prasyarat server

Masuk ke Ubuntu menggunakan akun yang memiliki `sudo`, lalu verifikasi kondisi dasar:

```bash
sudo -v
sudo dpkg --audit
sudo apt-get update
```

Jika `dpkg --audit` melaporkan konfigurasi yang terinterupsi, selesaikan dulu:

```bash
sudo dpkg --configure -a
sudo apt-get -f install
sudo apt-get update
```

Pasang alat untuk mengambil repository dan menjalankan playbook:

```bash
sudo apt-get install -y git ansible python3-pymysql
```

Buat direktori kerja dan konfigurasi deployment yang hanya dapat diakses root:

```bash
sudo install -d -o root -g root -m 0750 /opt/jalatantra-src
sudo install -d -o root -g root -m 0700 /etc/jalatantra-deploy
```

---

## 2. Ambil kode dari GitHub

Clone repository untuk pertama kali:

```bash
sudo git clone --branch main --depth 1 \
  https://github.com/NaufalSM12/JalaTantra.git \
  /opt/jalatantra-src
```

Periksa commit yang sedang dipakai:

```bash
sudo git -C /opt/jalatantra-src status --short
sudo git -C /opt/jalatantra-src log -1 --oneline
```

Hasil `status --short` harus kosong. Jangan mengedit source di `/opt/jalatantra-src`
untuk menyimpan password atau kunci; semua nilai lokal diletakkan di
`/etc/jalatantra-deploy`.

Pasang collection Ansible yang diperlukan oleh role MariaDB:

```bash
sudo ansible-galaxy collection install \
  -r /opt/jalatantra-src/requirements.yml
```

---

## 3. Buat inventory lokal di luar repository

Salin inventory bawaan sebagai dasar konfigurasi lokal:

```bash
sudo cp -a /opt/jalatantra-src/inventory/. /etc/jalatantra-deploy/
sudo chown -R root:root /etc/jalatantra-deploy
sudo chmod 0700 /etc/jalatantra-deploy
sudo chmod 0600 /etc/jalatantra-deploy/group_vars/all.yml
```

Untuk satu server, gunakan isi berikut pada `/etc/jalatantra-deploy/hosts.yml`:

```yaml
---
all:
  children:
    control:
      hosts:
        localhost:
          ansible_connection: local
    dns:
      hosts:
        localhost:
    database:
      hosts:
        localhost:
    monitoring:
      hosts:
        localhost:
    exporters:
      hosts:
        localhost:
```

Buat direktori host vars dan konfigurasi non-rahasia:

```bash
sudo install -d -o root -g root -m 0700 \
  /etc/jalatantra-deploy/host_vars/localhost
sudo nano /etc/jalatantra-deploy/host_vars/localhost/main.yml
```

Isi file tersebut sebagai berikut. Semua listener tetap loopback; nama domain dan
database dapat diganti sesuai lingkungan server.

```yaml
---
project_domain: jalatantra.test
project_dns_server_ip: 127.0.0.1
project_timezone: Asia/Jakarta

mariadb_bind_address: 127.0.0.1
mariadb_database_name: jalatantra_ops
mariadb_app_user: jalatantra_ops

bind9_listen_ipv4:
  - 127.0.0.1
bind9_allow_query:
  - 127.0.0.1
bind9_zone_records:
  - { name: ns1, address: 127.0.0.1 }
  - { name: monitor, address: 127.0.0.1 }
  - { name: grafana, address: 127.0.0.1 }
  - { name: db, address: 127.0.0.1 }

prometheus_listen_address: 127.0.0.1:9090
prometheus_self_target: 127.0.0.1:9090
prometheus_node_exporter_targets:
  - 127.0.0.1:9100

node_exporter_listen_address: 127.0.0.1:9100
grafana_listen_address: 127.0.0.1
grafana_http_port: 3000

jalatantra_listen_address: 127.0.0.1
jalatantra_http_port: 3080
jalatantra_cookie_secure: false
jalatantra_allowed_networks:
  - 127.0.0.0/8
jalatantra_managed_hosts:
  127.0.0.1: local
jalatantra_automation_hosts:
  local:
    ansible_host: 127.0.0.1
    ansible_connection: local
    ansible_python_interpreter: /usr/bin/python3
jalatantra_dns_probe_name: ns1.jalatantra.test
jalatantra_prometheus_url: http://127.0.0.1:9090
```

Atur izin file:

```bash
sudo chown root:root /etc/jalatantra-deploy/host_vars/localhost/main.yml
sudo chmod 0600 /etc/jalatantra-deploy/host_vars/localhost/main.yml
```

---

## 4. Buat vault untuk semua rahasia

Buat vault lokal. Perintah ini meminta passphrase vault secara interaktif; jangan
menyimpan passphrase tersebut di file plaintext.

```bash
sudo ansible-vault create \
  /etc/jalatantra-deploy/host_vars/localhost/vault.yml
```

Masukkan YAML berikut lalu ganti setiap nilai dengan kata sandi baru yang kuat:

```yaml
---
mariadb_login_password: ""
mariadb_root_password: "GANTI_DENGAN_PASSWORD_ROOT_MARIADB_KUAT"
mariadb_app_password: "GANTI_DENGAN_PASSWORD_APLIKASI_MARIADB_KUAT"
grafana_admin_password: "GANTI_DENGAN_PASSWORD_ADMIN_GRAFANA_KUAT"
jalatantra_admin_password: "GANTI_DENGAN_PASSWORD_ADMIN_JALATANTRA_MINIMAL_12_KARAKTER"
```

Aturan penggunaan:

- Pada instalasi MariaDB baru, `mariadb_login_password` tetap string kosong.
- Setelah instalasi pertama berhasil, buka vault lagi dan isi
  `mariadb_login_password` dengan nilai yang sama seperti `mariadb_root_password`.
  Ini diperlukan pada deployment berikutnya.
- Jangan memakai password dari lingkungan uji lokal.
- Jangan menyalin `vault.yml` ke `/opt/jalatantra-src` dan jangan commit file vault.

Pastikan vault hanya dapat dibaca root:

```bash
sudo chown root:root /etc/jalatantra-deploy/host_vars/localhost/vault.yml
sudo chmod 0600 /etc/jalatantra-deploy/host_vars/localhost/vault.yml
```

---

## 5. Validasi sebelum deploy

Jalankan syntax check. Perintah ini tidak mengubah server.

```bash
cd /opt/jalatantra-src
sudo ANSIBLE_ROLES_PATH=/opt/jalatantra-src/roles \
  ansible-playbook \
  -i /etc/jalatantra-deploy/hosts.yml \
  playbooks/site.yml \
  --limit localhost \
  --ask-vault-pass \
  --syntax-check
```

Harapan:

```text
playbook: playbooks/site.yml
```

---

## 6. Deploy awal

Jalankan stack lengkap:

```bash
cd /opt/jalatantra-src
sudo ANSIBLE_ROLES_PATH=/opt/jalatantra-src/roles \
  ansible-playbook \
  -i /etc/jalatantra-deploy/hosts.yml \
  playbooks/site.yml \
  --limit localhost \
  --ask-vault-pass
```

Deployment memasang dan mengonfigurasi:

- BIND9;
- MariaDB;
- Node Exporter;
- Prometheus;
- Grafana;
- portal JalaTantra dan worker otomasi;
- inventory otomasi root-only;
- skema database, perangkat Demo persisten, dan akun admin awal.

Playbook bersifat idempoten: menjalankan ulang tidak menghapus perangkat, insiden,
pekerjaan, pengaturan AI database, atau password admin yang sudah ada.

---

## 7. Verifikasi setelah deploy

Periksa status layanan:

```bash
sudo systemctl is-active \
  mariadb prometheus prometheus-node-exporter grafana-server named \
  jalatantra jalatantra-worker
```

Harapan: semua layanan menampilkan `active`.

Periksa endpoint aplikasi dan heartbeat worker:

```bash
curl -fsS http://127.0.0.1:3080/api/health
sudo mariadb -u root -p jalatantra -e \
  "SELECT name, heartbeat_at FROM service_state WHERE name='worker';"
```

Harapan endpoint:

```json
{"ok":true}
```

Lihat log bila ada masalah:

```bash
sudo journalctl -u jalatantra -u jalatantra-worker -n 100 --no-pager
```

---

## 8. Akses portal dengan SSH tunnel

JalaTantra tidak membuka port HTTP ke jaringan. Dari komputer operator, buat tunnel:

```bash
ssh -N \
  -L 3080:127.0.0.1:3080 \
  -L 3000:127.0.0.1:3000 \
  -L 9090:127.0.0.1:9090 \
  USER_SERVER@ALAMAT_SERVER
```

Buka pada browser lokal:

- Portal JalaTantra: `http://127.0.0.1:3080`
- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`

Masuk portal memakai pengguna `admin` dan password `jalatantra_admin_password`
yang dibuat di vault. Ganti password portal segera melalui menu profil.

Jangan mengubah `jalatantra_listen_address` menjadi `0.0.0.0` tanpa reverse proxy
HTTPS, cookie secure, firewall, dan penilaian keamanan yang sesuai.

---

## 9. Uji fungsional setelah deploy

Jalankan pemeriksaan monitoring lokal:

```bash
cd /opt/jalatantra-src
sudo python3 tools/build_dashboards.py --check
sudo python3 tools/check_local.py
```

Jalankan uji unit dan collector:

```bash
cd /opt/jalatantra-src
sudo python3 -B -m unittest discover -s tests -p 'test_jalatantra_*.py'
sudo python3 -B -m unittest discover -s tests -p 'test_collector.py'
```

Jalankan integrasi live. Simpan credential hanya sementara di `/run`:

```bash
sudo install -m 0600 /dev/null /run/jalatantra-test-creds.json
sudo nano /run/jalatantra-test-creds.json
```

Isi:

```json
{"username":"admin","password":"PASSWORD_ADMIN_JALATANTRA"}
```

Lalu jalankan dan hapus file sementara:

```bash
cd /opt/jalatantra-src
sudo python3 tools/check_jalatantra.py < /run/jalatantra-test-creds.json
sudo rm -f /run/jalatantra-test-creds.json
```

Harapan: seluruh kelompok integrasi lulus. Uji ini memakai perangkat Demo sementara,
menjalankan audit baca-saja pada localhost, dan tidak mengaktifkan ulang SSH yang mati.

---

## 10. Pembaruan dari GitHub

Selalu periksa source lokal sebelum pembaruan. Jika `git status --short` tidak kosong,
jangan lanjutkan sebelum perubahan lokal dipahami atau dipindahkan keluar dari source.

```bash
cd /opt/jalatantra-src
sudo git status --short
sudo git fetch origin
sudo git log --oneline HEAD..origin/main
sudo git pull --ff-only origin main
sudo git rev-parse --short HEAD
```

Setelah source terbaru diambil, jalankan deploy portal saja:

```bash
cd /opt/jalatantra-src
sudo ANSIBLE_ROLES_PATH=/opt/jalatantra-src/roles \
  ansible-playbook \
  -i /etc/jalatantra-deploy/hosts.yml \
  playbooks/site.yml \
  --limit localhost \
  --tags jalatantra \
  --ask-vault-pass
```

Jika update mengubah monitoring, DNS, MariaDB, atau inventory, jalankan playbook tanpa
`--tags jalatantra` agar seluruh konfigurasi terkait ikut konsisten.

Sesudah pembaruan, ulangi minimal:

```bash
curl -fsS http://127.0.0.1:3080/api/health
sudo systemctl is-active jalatantra jalatantra-worker
```

---

## 11. Menambahkan perangkat Real tambahan

Jangan langsung memasukkan subnet luas. Tambahkan hanya alamat yang memang dikelola
ke `/etc/jalatantra-deploy/host_vars/localhost/main.yml`.

Contoh satu host `10.20.30.40`:

```yaml
jalatantra_allowed_networks:
  - 127.0.0.0/8
  - 10.20.30.40/32

jalatantra_managed_hosts:
  127.0.0.1: local
  10.20.30.40: node40

jalatantra_automation_hosts:
  local:
    ansible_host: 127.0.0.1
    ansible_connection: local
    ansible_python_interpreter: /usr/bin/python3
  node40:
    ansible_host: 10.20.30.40
    ansible_user: ops
    ansible_become: true
    ansible_private_key_file: /etc/jalatantra/automation_key
    ansible_python_interpreter: /usr/bin/python3

prometheus_node_exporter_targets:
  - 127.0.0.1:9100
  - 10.20.30.40:9100
```

Simpan private key otomasi hanya di server:

```bash
sudo ssh-keygen -t ed25519 -f /etc/jalatantra/automation_key -N ""
sudo chmod 0600 /etc/jalatantra/automation_key
sudo ssh-copy-id -i /etc/jalatantra/automation_key.pub ops@10.20.30.40
```

Redeploy konfigurasi:

```bash
cd /opt/jalatantra-src
sudo ANSIBLE_ROLES_PATH=/opt/jalatantra-src/roles \
  ansible-playbook \
  -i /etc/jalatantra-deploy/hosts.yml \
  playbooks/site.yml \
  --limit localhost \
  --ask-vault-pass
```

Kemudian tambahkan perangkat pada UI sebagai lingkungan **Real**. Urutan aman:

1. pemeriksaan layanan;
2. audit perangkat;
3. kumpulkan bukti sistem;
4. diagnosis layanan;
5. baru pertimbangkan `ensure_service`, `reload_service`, atau `restart_service`
   dengan approval admin.

`reload_service` hanya tersedia untuk DNS dan Prometheus. Semua perubahan Real tetap
membutuhkan approval, kecuali perangkat yang secara eksplisit diberi auto-approve
untuk aksi yang memang diizinkan.

---

## 12. Backup dan rollback

Buat backup sebelum pembaruan besar:

```bash
sudo install -d -o root -g root -m 0700 /root/jalatantra-backups
sudo mariadb-dump -u root -p --databases jalatantra jalatantra_ops \
  | gzip -9 > /root/jalatantra-backups/jalatantra-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
sudo tar -czf /root/jalatantra-backups/jalatantra-config-$(date -u +%Y%m%dT%H%M%SZ).tgz \
  /etc/jalatantra /etc/jalatantra-deploy
sudo chmod 0600 /root/jalatantra-backups/*
```

Simpan backup di lokasi terpisah yang aman. Arsip `/etc/jalatantra` dan
`/etc/jalatantra-deploy` dapat memuat credential worker, vault, dan konfigurasi AI.

Rollback source ke commit sebelumnya:

```bash
cd /opt/jalatantra-src
sudo git log --oneline --decorate -10
sudo git checkout COMMIT_YANG_SUDAH_DIVERIFIKASI
```

Lalu deploy ulang menggunakan inventory dan vault yang sama:

```bash
sudo ANSIBLE_ROLES_PATH=/opt/jalatantra-src/roles \
  ansible-playbook \
  -i /etc/jalatantra-deploy/hosts.yml \
  playbooks/site.yml \
  --limit localhost \
  --tags jalatantra \
  --ask-vault-pass
```

Skema database bersifat additif. Jangan melakukan downgrade dengan menghapus tabel
atau menghapus data MariaDB secara manual.

Kembali ke branch terbaru setelah rollback selesai dievaluasi:

```bash
cd /opt/jalatantra-src
sudo git switch main
sudo git pull --ff-only origin main
```

---

## 13. Troubleshooting

| Gejala | Pemeriksaan dan tindakan |
|---|---|
| `git clone` gagal | Pastikan server dapat membuka `https://github.com`; periksa DNS, proxy, dan waktu sistem. |
| Ansible tidak menemukan role | Jalankan dengan `ANSIBLE_ROLES_PATH=/opt/jalatantra-src/roles`. |
| Collection `community.mysql` tidak ada | Jalankan `sudo ansible-galaxy collection install -r /opt/jalatantra-src/requirements.yml`. |
| MariaDB menolak login saat rerun | Perbarui `mariadb_login_password` di vault agar sama dengan password root MariaDB saat ini. |
| `/api/health` menghasilkan 503 | Periksa `sudo systemctl status mariadb jalatantra` dan `sudo journalctl -u jalatantra -n 100 --no-pager`. |
| Worker tidak mengirim heartbeat | Periksa `sudo systemctl status jalatantra-worker` dan `sudo journalctl -u jalatantra-worker -n 100 --no-pager`. |
| AI tidak dapat menjawab | Periksa Pengaturan AI melalui UI; aplikasi inti tetap berjalan tanpa AI. Pastikan lingkungan Demo/Real yang dipilih benar. |
| Perangkat Real tidak dapat diperiksa | Pastikan alamat ada di `jalatantra_allowed_networks`, redeploy, lalu periksa rute dan firewall dari server. |
| Otomasi Real ditolak | Pastikan alamat juga terdaftar di `jalatantra_managed_hosts` dan `jalatantra_automation_hosts`; mulai dengan audit atau diagnosis baca-saja. |
| Tunnel SSH putus | Jalankan ulang perintah tunnel; portal tidak perlu dibuka ke jaringan untuk mengatasi masalah ini. |

---

## 14. Checklist selesai

- [ ] Source berasal dari GitHub branch `main` dan `git status --short` kosong.
- [ ] Inventory serta vault berada di `/etc/jalatantra-deploy`, bukan di repository.
- [ ] Vault dan konfigurasi lokal hanya dapat dibaca root.
- [ ] Syntax check Ansible selesai tanpa error.
- [ ] Deploy selesai dengan `failed=0`.
- [ ] MariaDB, Prometheus, Node Exporter, Grafana, BIND9, portal, dan worker berstatus `active`.
- [ ] `curl http://127.0.0.1:3080/api/health` mengembalikan `{"ok":true}`.
- [ ] Heartbeat `jalatantra-worker` tercatat pada tabel `service_state`.
- [ ] Akses portal dilakukan melalui SSH tunnel.
- [ ] Password admin portal telah diganti setelah login pertama.
- [ ] Uji monitoring, unit, collector, dan integrasi selesai sesuai kebutuhan.
- [ ] Backup database, konfigurasi aplikasi, dan konfigurasi deployment disimpan di luar server.

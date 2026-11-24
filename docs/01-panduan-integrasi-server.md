# Panduan Integrasi JalaTantra ke Server Ubuntu Asli

Panduan ini membawa JalaTantra dari lingkungan uji lokal (WSL) ke server Ubuntu asli
alamat `10.33.109.77` — server yang percobaan SSH-nya sebelumnya gagal. Dokumen ini
menjelaskan penyebab kegagalan tersebut, cara membuka akses yang benar, dua jalur
deployment, cara mengakses aplikasi dengan aman dari jauh, verifikasi pasca-integrasi,
pendaftaran perangkat real, serta backup dan rollback.

> Prinsip keselamatan: jangan mengubah apa pun di server sebelum akses SSH dan hak
> sudo terkonfirmasi. Semua layanan JalaTantra sengaja mengikat loopback; akses dari
> jauh dilakukan melalui tunnel SSH, bukan membuka port ke jaringan publik.

---

## 1. Mengapa SSH sebelumnya gagal

`10.33.109.77` adalah alamat privat (RFC 1918). Alamat seperti ini **tidak dapat
dirutekan dari internet biasa**; hanya reachable dari dalam jaringan yang sama atau
melalui VPN yang menjembatani jaringan tersebut. Percobaan `ssh a1-8@10.33.109.77`
yang gagal hampir pasti terjadi karena tunnel VPN belum aktif saat percobaan,
sehingga paket tidak pernah mencapai server.

Urutan diagnosis (jalankan dari Windows tempat profil VPN berada):

1. **Aktifkan VPN terlebih dahulu.** Impor profil `.ovpn` yang Anda terima ke
   OpenVPN GUI (atau klien OpenVPN lain), lalu connect. Jangan menyalin, mengunggah,
   atau menampilkan isi file profil tersebut ke mana pun — di dalamnya terdapat
   kunci statis TLS yang bersifat rahasia.
2. **Verifikasi rute dari Windows:**
   ```powershell
   ping 10.33.109.77
   Test-NetConnection 10.33.109.77 -Port 22
   ```
   `TcpTestSucceeded : True` berarti jalur ke SSH terbuka.
3. **Verifikasi dari WSL (bila akan memakai Jalur A):**
   ```bash
   ping -c 3 10.33.109.77
   ```
   WSL2 meneruskan trafik melalui Windows; bila Windows reachable tetapi WSL tidak,
   lihat bagian Troubleshooting (mode jaringan mirrored).
4. **Coba SSH dengan verbose:**
   ```bash
   ssh -v a1-8@10.33.109.77
   ```

Tabel gejala → penyebab → tindakan:

| Gejala | Penyebab paling mungkin | Tindakan |
|---|---|---|
| `Connection timed out` | VPN belum aktif / rute tidak ada | Aktifkan VPN, ulangi langkah 2 |
| `Connection refused` | sshd tidak berjalan / firewall server | Minta administrator memeriksa `sshd` dan firewall server |
| `Permission denied (publickey,password)` | Kredensial salah / akun belum diizinkan | Konfirmasi akun dan kata sandi ke administrator; pastikan akun boleh login password |
| `Host key verification failed` | Kunci host berubah / known_hosts lama | Periksa sidik kunci host ke administrator sebelum menghapus entri known_hosts |
| `sudo: a password is required` / `not in sudoers` | Akun tanpa hak sudo | Minta administrator menambahkan akun ke grup sudo |
| Windows reachable, WSL timeout | NAT WSL2 tidak meneruskan rute VPN | Pakai Jalur B, atau aktifkan `networkingMode=mirrored` di `.wslconfig` lalu `wsl --shutdown` |

**Jangan melanjutkan ke deployment bila langkah 2 belum True.** Konfirmasi akses
adalah prasyarat, bukan opsional.

---

## 2. Prasyarat akses dan persiapan server

Setelah SSH berhasil:

1. **Ganti kata sandi awal akun** segera (`passwd`). Kata sandi bawaan yang dibagikan
   bersama alamat server bukan rahasia lagi.
2. **Pastikan hak sudo:** `sudo -v`. Bila gagal, minta administrator menambah akun
   ke grup `sudo`; deployment membutuhkan root.
3. **Pasang kunci SSH** agar kata sandi tidak diketik berulang dan tidak muncul di
   argumen proses:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/jalatantra_deploy -N ""
   ssh-copy-id -i ~/.ssh/jalatantra_deploy.pub a1-8@10.33.109.77
   ```
4. **Periksa kesehatan paket server** (deployment memakai apt):
   ```bash
   sudo dpkg --audit
   sudo apt-get update
   ```
   Bila `dpkg --audit` melaporkan paket terinterupsi: `sudo dpkg --configure -a`
   lalu `sudo apt-get -f install`.
5. **Catat kondisi awal** untuk rollback: `systemctl list-units --type=service --state=running`,
   `df -h`, `free -h`.

Server target adalah Ubuntu dengan systemd dan akses apt yang berfungsi. Seluruh
kebutuhan perangkat lunak (MariaDB, Prometheus, node_exporter, Grafana, BIND9,
Flask/Gunicorn, Ansible) dipasang oleh playbook; tidak ada pemasangan manual.

---

## 3. Jalur A (direkomendasikan): Ansible push dari WSL

Kontrol tetap di mesin Anda; server hanya menerima koneksi SSH. Repository disalin
ke filesystem Linux di WSL terlebih dahulu karena direktori `/mnt/e` bersifat
world-writable dan Ansible mengabaikan `ansible.cfg` di direktori semacam itu.

### 3.1 Salin repository ke WSL

```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash -c \
  'cp -a "/mnt/e/AMJ-Network infrastruktur automation" /root/jalatantra-src'
```

### 3.2 Inventory produksi

Buat `inventory/production.yml` di salinan repository tersebut:

```yaml
all:
  vars:
    ansible_user: a1-8
    ansible_become: true
    ansible_python_interpreter: /usr/bin/python3
  children:
    dns:
      hosts:
        prod01: &prod01
          ansible_host: 10.33.109.77
    database:
      hosts:
        prod01: *prod01
    monitoring:
      hosts:
        prod01: *prod01
    exporters:
      hosts:
        prod01: *prod01
```

Keanggotaan grup menentukan peran yang dipasang: `database` + `monitoring`
memasang MariaDB, Prometheus, node_exporter, Grafana, dan JalaTantra; `dns`
menambah BIND9; `exporters` memasang node_exporter. Untuk satu server serba-guna,
pertahankan keempat grup seperti di atas.

### 3.3 Variabel host non-rahasia

Buat `inventory/host_vars/prod01/main.yml`:

```yaml
project_domain: jalatantra.test
mariadb_database_name: jalatantra_ops
mariadb_app_user: ops_app
bind9_zone_records:
  - { name: ns1, address: 127.0.0.1 }
  - { name: monitor, address: 127.0.0.1 }
  - { name: grafana, address: 127.0.0.1 }
  - { name: db, address: 127.0.0.1 }
prometheus_node_exporter_targets:
  - 127.0.0.1:9100
jalatantra_allowed_networks:
  - 127.0.0.0/8
jalatantra_managed_hosts:
  127.0.0.1: local
```

Semua alamat tetap loopback sesuai default aman. Nama domain dan database di atas
adalah identitas netral untuk lingkungan produksi Anda.

### 3.4 Rahasia dengan Ansible Vault

```bash
cd /root/jalatantra-src
ansible-vault create inventory/host_vars/prod01/vault.yml
```

Isi (ganti setiap `<...>` dengan nilai baru yang kuat; jangan memakai ulang kata
sandi lingkungan uji lokal):

```yaml
ansible_become_pass: <kata sandi sudo akun a1-8>
mariadb_login_password: ""          # instalasi baru; isi kata sandi root saat ini pada run ulang
mariadb_root_password: <baru, kuat>
mariadb_app_password: <baru, kuat>
grafana_admin_password: <baru, kuat>
jalatantra_admin_password: <baru, minimal 12 karakter>
```

`mariadb_login_password` kosong hanya valid pada instalasi pertama (root MariaDB
masih tanpa kata sandi). Setelah run pertama, root MariaDB memakai
`mariadb_root_password`; perbarui nilai `mariadb_login_password` di vault untuk
run berikutnya.

### 3.5 Jalankan playbook

```bash
cd /root/jalatantra-src
ANSIBLE_ROLES_PATH=/root/jalatantra-src/roles \
  ansible-playbook -i inventory/production.yml playbooks/site.yml \
  --limit prod01 --ask-vault-pass
```

Tambahkan `--ask-pass` hanya bila kunci SSH belum dipasang (langkah 2.3).
Untuk memperbarui aplikasi saja tanpa menyentuh layanan lain:

```bash
ANSIBLE_ROLES_PATH=/root/jalatantra-src/roles \
  ansible-playbook -i inventory/production.yml playbooks/site.yml \
  --limit prod01 --tags jalatantra --ask-vault-pass
```

Playbook bersifat idempoten: run ulang hanya mengubah yang berubah, dan data
inventaris serta insiden tidak di-seed ulang.

### 3.6 Verifikasi di server

```bash
ssh -i ~/.ssh/jalatantra_deploy a1-8@10.33.109.77 \
  'systemctl is-active mariadb prometheus grafana-server prometheus-node-exporter named jalatantra jalatantra-worker; curl -s http://127.0.0.1:3080/api/health'
```

Harapan: tujuh layanan `active` dan `{"ok":true}`.

---

## 4. Jalur B (fallback): deployment langsung di server

Bila SSH dari WSL tidak dapat menjangkau server (mis. rute VPN hanya ada di
Windows) tetapi SSH dari Windows berhasil, jalankan deployment di server itu
sendiri. `tools/deploy_local.py` memang dirancang untuk dijalankan sebagai root
di host target.

1. Salin repository ke server (dari Git Bash Windows):
   ```bash
   scp -r "E:/AMJ-Network infrastruktur automation" a1-8@10.33.109.77:~/jalanantra-src
   ```
2. Masuk dan naik ke root:
   ```bash
   ssh a1-8@10.33.109.77
   sudo -i
   cd ~/jalanantra-src
   ```
3. Jalankan deployment interaktif (kata sandi diketik di prompt, tidak pernah
   menjadi argumen proses):
   ```bash
   python3 tools/deploy_local.py
   ```
   Prompt meminta: kata sandi root MariaDB saat ini (kosong bila instalasi baru),
   kata sandi akun aplikasi MariaDB, kata sandi admin Grafana, dan kata sandi awal
   admin JalaTantra (minimal 12 karakter). Untuk run ulang, isi kata sandi root
   MariaDB yang sekarang berlaku.
4. Verifikasi seperti langkah 3.6.

Jalur B memasang stack lengkap karena `site.yml --limit localhost` di server
berarti server itu sendiri.

---

## 5. Mengakses aplikasi dari jauh dengan aman

Portal, Grafana, dan Prometheus mengikat loopback di server. Itu keputusan desain:
tidak ada port aplikasi yang terbuka ke jaringan. Akses dari mesin Anda memakai
tunnel SSH (OpenSSH):

```bash
ssh -N -L 3080:127.0.0.1:3080 -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 a1-8@10.33.109.77
```

Selama tunnel hidup:

- Aplikasi: http://127.0.0.1:3080
- Grafana (internal/opsional): http://127.0.0.1:3000
- Prometheus (internal/opsional): http://127.0.0.1:9090

Login memakai akun `admin` dan kata sandi yang Anda set saat deployment. Segera
ganti lewat menu profil → Ubah kata sandi.

Jangan mengubah `jalatantra_listen_address` ke `0.0.0.0` untuk "mempermudah akses":
role menolak bind non-loopback kecuali cookie secure aktif, dan cookie secure
membutuhkan HTTPS yang belum tersedia di stack ini. Tunnel SSH adalah jalur akses
jarak yang didukung.

---

## 6. Verifikasi pasca-integrasi

1. **Uji integrasi live di server** (skrip ini menyentuh database untuk cleanup,
   sehingga harus dijalankan di host tempat aplikasi berada):
   ```bash
   ssh a1-8@10.33.109.77
   sudo -i
   cd ~/jalanantra-src        # atau salin repository bila memakai Jalur A
   printf '%s' '{"username":"admin","password":"<kata sandi admin>"}' > /run/jt-creds.json
   chmod 600 /run/jt-creds.json
   python3 tools/check_jalatantra.py < /run/jt-creds.json
   rm -f /run/jt-creds.json
   ```
   Harapan: sepuluh kelompok uji lulus (lihat Panduan Testing).
2. **Uji browser dari mesin Anda melalui tunnel** (skrip browser hanya berbicara
   HTTP ke 127.0.0.1:3080, sehingga tunnel membuatnya berlaku untuk server):
   ```bash
   printf '%s' '{"username":"admin","password":"<kata sandi admin>"}' | node tools/browser_jalatantra.mjs
   ```
3. **Pemeriksaan monitoring:** `python3 tools/check_local.py` dan
   `python3 tools/build_dashboards.py --check` di server.
4. **Jejak audit:** buka halaman Aktivitas di UI; pastikan entri login, pembuatan
   perangkat, dan persetujuan tercatat dengan aktor dan waktu.

---

## 7. Mendaftarkan perangkat real tambahan

Secara default hanya `127.0.0.1` yang boleh diperiksa dan diotomasi. Untuk perangkat
lain di jaringan server (mis. `10.33.109.20`):

1. Perluas kebijakan di `inventory/host_vars/prod01/main.yml`:
   ```yaml
   jalatantra_allowed_networks:
     - 127.0.0.0/8
     - 10.33.109.0/24
   jalatantra_managed_hosts:
     127.0.0.1: local
     10.33.109.20: node20
   jalatantra_automation_hosts:
     local:
       ansible_host: 127.0.0.1
       ansible_connection: local
       ansible_python_interpreter: /usr/bin/python3
     node20:
       ansible_host: 10.33.109.20
       ansible_user: ops
       ansible_become: true
       ansible_private_key_file: /etc/jalatantra/automation_key
       ansible_python_interpreter: /usr/bin/python3
   prometheus_node_exporter_targets:
     - 127.0.0.1:9100
     - 10.33.109.20:9100
   ```
2. Siapkan kunci otomasi di server (root-only, di luar home karena sandbox worker
   memakai `ProtectHome`):
   ```bash
   sudo ssh-keygen -t ed25519 -f /etc/jalatantra/automation_key -N ""
   sudo chmod 600 /etc/jalatantra/automation_key
   sudo ssh-copy-id -i /etc/jalatantra/automation_key.pub ops@10.33.109.20
   ```
3. Pastikan node_exporter di perangkat target mengikat alamat yang dapat dijangkau
   server (variabel `node_exporter_listen_address` pada host target, mis.
   `10.33.109.20:9100`), lalu redeploy tag terkait:
   `--tags jalatantra,prometheus,node_exporter`.
4. Daftarkan perangkat lewat UI (lingkungan Real, alamat `10.33.109.20`, port
   exporter 9100). Badge "Target terkelola" muncul hanya bila alamat terdaftar di
   `managed_hosts`; pemeriksaan tetap dibatasi `allowed_networks`.
5. Uji baca-saja dahulu: jalankan pemeriksaan layanan dan audit. Aksi
   `ensure_service`/`restart_service` pada perangkat nyata hanya setelah Anda
   memahami dampaknya dan melewati persetujuan admin di UI.

Alamat di luar cakupan tetap dapat dicatat sebagai inventaris, tetapi pemeriksaan
dan otomasinya ditolak server — itu perilaku yang diharapkan, bukan kerusakan.

### 7a. Mode auto-approve per perangkat (opsional)

Secara bawaan setiap perubahan layanan menunggu persetujuan administrator. Untuk
perangkat yang sudah dipercaya dan ingin dipulihkan cepat (mis. host lab), admin
dapat mengaktifkan auto-approve per perangkat:

- Di UI: buka detail perangkat → **Auto-approve layanan** → konfirmasi.
- Batasnya tetap: hanya `ensure_service` dan `restart_service`, hanya layanan yang
  terdaftar pada perangkat, hanya target terkelola, dan tetap tercatat audit
  (`auto_approve_changed` + `job_requested … auto-approve perangkat aktif`).
- Menonaktifkannya mengembalikan gerbang persetujuan untuk permintaan berikutnya.
  Jika dinonaktifkan saat job masih antre, worker menolak eksekusi (fail-safe).
- Karena mengubah `updated_at` perangkat, toggle ditolak 409 selama ada pekerjaan aktif.

### 7b. Asisten AI read-only (sepenuhnya opsional)

Aplikasi berjalan penuh tanpa AI. Saat aktif, asisten hanya **membaca** data operasional:
ringkasan insiden, saran tindak lanjut berdasarkan riwayat, tanya-jawab operasional,
prioritas insiden, dan handover. Deteksi anomali metrik tetap rule-based di worker; AI
hanya membantu menjelaskan data dan **tidak pernah** mengeksekusi atau mengubah status.

**Batas lingkungan ketat:** setiap permintaan AI wajib membawa lingkungan yang sedang
terpilih. Permintaan Real hanya membaca perangkat, insiden, pemeriksaan, dan pekerjaan
Real; permintaan Demo hanya membaca data sintetis Demo. Permintaan tanpa lingkungan
ditolak server, bukan diam-diam dialihkan ke Demo.

**Cara termudah: dari UI.** Login sebagai admin → menu profil (kanan atas) →
**Pengaturan AI** → isi penyedia:

| Kolom | Isi |
|---|---|
| Base URL | Endpoint Chat Completions, mis. `https://api.provider.com/v1` |
| Kunci API | Kunci rahasia penyedia (disimpan di database, selalu termasking saat ditampilkan) |
| Model ID | Nama model, mis. `qwen3.8-max` atau `deepseek-chat` |
| Batas waktu / token | Nilai wajar: 20 detik, 600 token |

Gunakan **Uji koneksi** untuk memastikan sebelum mengaktifkan, atau **Ambil daftar model**
untuk memilih Model ID dari penyedia. Lalu centang **Aktifkan asisten AI** dan simpan.
Kunci yang sudah tersimpan tidak akan ditampilkan kembali; kosongkan kolom untuk
mempertahankannya.

Catatan penting:

- Penyedia harus kompatibel OpenAI (`POST {base_url}/chat/completions`).
- Tanpa konfigurasi: `GET /api/ai/status` → `{"available": false}`, UI menyembunyikan
  analisis, dan semua fungsi inti tetap berjalan.
- Data yang dikirim hanya: nama/alamat/jenis/lokasi perangkat, teks insiden, hasil
  pemeriksaan terakhir, riwayat pekerjaan, dan jejak audit perangkat itu. Tidak ada
  kata sandi, token, atau isi konfigurasi rahasia.
- Setiap perubahan pengaturan tercatat di audit sebagai `ai_settings_changed`, dan
  setiap pemakaian sebagai `AI-Advisor incident_explained`,
  `incident_followup_suggested`, atau `operational_question_answered`.
- Permintaan AI dibatasi per akun untuk mencegah biaya tak disengaja. Hasil ringkasan
  insiden yang sama di-cache singkat agar membuka ulang detail tidak selalu memanggil penyedia.
- Pengalihan HTTP penyedia diblokir; ini mencegah kunci API terbawa ke alamat lain.
- Untuk verifikasi tanpa biaya, arahkan Base URL ke provider tiruan lokal
  (lihat docs/03 §3.8c).

<details>
<summary>Alternatif: konfigurasi lewat file (provisioning tanpa UI)</summary>

Buat `/etc/jalatantra/ai.json` (0600/0640, jangan masukkan ke repo). Nilai di
database (jika diisi lewat UI) selalu diprioritaskan di atas file ini.

```bash
sudo tee /etc/jalatantra/ai.json >/dev/null <<'JSON'
{
  "enabled": true,
  "base_url": "https://provider-anda/v1",
  "model": "nama-model",
  "api_key": "ISI-KUNCI-DI-SINI",
  "timeout": 20,
  "max_tokens": 600
}
JSON
sudo systemctl restart jalatantra
```

Deploy ulang tidak mengganti file yang sudah ada bila variabel provisioning AI kosong;
pengaturan yang dibuat lewat UI juga tidak terpengaruh karena tersimpan di database.
</details>

---

## 8. Backup, rollback, dan batas operasional

**Backup sebelum perubahan besar:**

```bash
sudo mysqldump -u root -p --databases jalatantra jalatantra_ops > /root/jalatantra-$(date +%F).sql
sudo tar czf /root/etc-jalatantra-$(date +%F).tgz /etc/jalatantra
```

Simpan salinan di luar server. `/etc/jalatantra` berisi konfigurasi dan kredensial
worker; perlakukan arsipnya sebagai rahasia (mode 0600).

**Rollback aplikasi:** simpan salinan repository versi sebelumnya; jalankan ulang
playbook dari salinan tersebut (`--tags jalatantra`). Skema database bersifat
additif (`IF NOT EXISTS`); jangan menurunkan versi dengan menghapus tabel.
Bila perubahan inventaris menyebabkan masalah, gunakan arsip perangkat di UI
(soft-archive, riwayat tetap tersimpan) alih-alih menghapus baris database.

**Batas yang perlu diterima:** worker mengklaim pekerjaan secara berurutan, tetapi
pemeriksaan perangkat diproses paralel terbatas dan dipaginasi sehingga satu perangkat
bermasalah tidak memotong seluruh putaran. Katalog otomasi mencakup audit, kumpulkan bukti
sistem, diagnosis layanan, pastikan layanan aktif, restart, dan reload terbatas. Reload
hanya tersedia untuk DNS/Prometheus, wajib approval, dan selalu diverifikasi ulang. Pekerjaan antrean kedaluwarsa setelah 30 menit,
permintaan persetujuan setelah 7 hari; worker mengirim heartbeat dan membersihkan riwayat
pemeriksaan >30 hari, pekerjaan >180 hari, serta audit >400 hari. Timeout Ansible tetap
120 detik. Belum ada notifikasi ke kanal eksternal atau TLS terminasi bawaan; akses jarak
jauh bergantung pada tunnel atau reverse proxy HTTPS yang dikelola operator.

---

## 9. Troubleshooting cepat

| Masalah | Penanganan |
|---|---|
| `dpkg was interrupted` saat apt | `sudo dpkg --configure -a && sudo apt-get -f install` |
| Ansible mengabaikan ansible.cfg | Jalankan dari filesystem Linux (bukan `/mnt/e`), atau set `ANSIBLE_ROLES_PATH` dan `-i` eksplisit |
| `Access denied for user 'root'` saat run ulang | `mariadb_login_password` di vault belum diperbarui ke kata sandi root saat ini |
| Vault menolak frasa sandi | Pastikan `--ask-vault-pass`; jangan menyimpan frasa vault di file plaintext |
| become gagal meski password benar | Periksa `ansible_become_pass` di vault; akun harus anggota sudo |
| `/api/health` 503 | `systemctl status mariadb`; periksa socket `/run/mysqld/mysqld.sock`; `journalctl -u jalatantra -n 50` |
| Pemeriksaan DNS perangkat real DOWN | Probe memakai `dns_probe_name` (default `ns1.<domain>`); bila resolver server tidak menunjuk BIND9 lokal, kondisi DOWN adalah jujur — arahkan resolver atau sesuaikan nama probe |
| Persetujuan ditolak "target telah berubah" | Inventaris perangkat diedit setelah permintaan dibuat; batalkan dan ajukan ulang (perilaku pengaman) |
| WSL tidak menjangkau subnet VPN | `.wslconfig` Windows: `[wsl2] networkingMode=mirrored`, lalu `wsl --shutdown`; atau pakai Jalur B |
| Port 3080 sudah dipakai di server | Ubah `jalatantra_http_port` di host vars dan redeploy; sesuaikan nomor tunnel |

---

## 10. Checklist akhir integrasi

- [ ] VPN aktif; `Test-NetConnection 10.33.109.77 -Port 22` True
- [ ] Kata sandi awal akun server diganti; kunci SSH deploy terpasang
- [ ] `sudo -v` berhasil; `dpkg --audit` bersih
- [ ] Vault dibuat; tidak ada rahasia di file plaintext atau argumen proses
- [ ] Playbook selesai `failed=0`; run ulang idempoten
- [ ] Tujuh layanan active; `/api/health` ok
- [ ] Tunnel SSH hidup; UI terbuka di http://127.0.0.1:3080
- [ ] Kata sandi admin JalaTantra diganti lewat UI
- [ ] `check_jalatantra.py` lulus di server; uji browser lulus melalui tunnel
- [ ] Backup database dan `/etc/jalatantra` taken dan tersimpan di luar server
- [ ] Perangkat real tambahan (bila ada) terdaftar dan teruji baca-saja dahulu

Setelah checklist ini hijau, server siap dipakai dan diuji mengikuti
`03-panduan-testing-lengkap.md`.
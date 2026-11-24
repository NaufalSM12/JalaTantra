# Panduan Testing Lengkap JalaTantra
## Dari pemasangan sampai pengujian realtime di aplikasi

Panduan ini mencakup seluruh siklus pengujian: menyiapkan lingkungan, memasang
aplikasi, menjalankan lapisan uji otomatis, menguji setiap modul secara realtime
lewat antarmuka, menguji perangkat real, mengamati perilaku sistem saat berjalan,
menjalankan uji negatif keamanan, dan menutup dengan kriteria penerimaan serta
template laporan.

Peta lapisan uji:

| Lapisan | Alat | Cakupan |
|---|---|---|
| Unit | `tests/test_jalatantra_api.py`, `tests/test_jalatantra_worker.py` | Validasi API, otorisasi, kebijakan worker, eksekusi Aman |
| Regresi collector | `tests/test_collector.py` | Generator metrik demo |
| Infrastruktur | `tools/check_local.py`, `tools/build_dashboards.py --check` | Layanan monitoring, dashboard, skenario demo |
| Integrasi live | `tools/check_jalatantra.py` | Alur penuh terhadap aplikasi berjalan + database |
| Browser E2E | `tools/browser_jalatantra.mjs` | UI desktop & mobile, alur pengguna nyata |
| Manual realtime | Checklist §3–§5 | Perilaku live, peran, perangkat real, observasi |
| Negatif keamanan | curl §6 | CSRF, origin, peran, batas payload, rate limit |

---

## 1. Persiapan dan pemasangan

### 1.1 Lingkungan uji lokal (WSL Ubuntu)

Prasyarat: Windows dengan WSL2 distribusi Ubuntu bersystemd, repository ini di
drive lokal, dan Node.js di Windows untuk uji browser.

1. Jaga WSL tetap hidup selama pengujian (layanan systemd tidak menahan WSL):
   ```bash
   wsl.exe -d Ubuntu -- python3 -c "import signal; signal.pause()"
   ```
   Jalankan sebagai proses latar belakang; hentikan bila sesi uji selesai.
2. Pasang aplikasi beserta seluruh stack melalui playbook (idempoten):
   ```bash
   MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash tools/run_deploy_jalatantra.sh <<'EOF'
   {"mariadb_login_password":"<root MariaDB saat ini, kosong bila baru>","mariadb_app_password":"<baru>","grafana_admin_password":"<baru>","jalatantra_admin_password":"<baru, minimal 12 karakter>"}
   EOF
   ```
   Skrip menulis rahasia ke file sementara 0600 di `/run` dan menghapusnya setelah
   selesai. Bila admin sudah ada, kata sandi admin tidak diubah oleh bootstrap.
3. Verifikasi pemasangan:
   ```bash
   MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash -c \
     'systemctl is-active mariadb prometheus grafana-server prometheus-node-exporter named jalatantra jalatantra-worker; curl -s http://127.0.0.1:3080/api/health'
   ```
   Harapan: semua `active`, health `{"ok":true}`.
4. Buka http://127.0.0.1:3080 dan login dengan akun admin yang dibuat saat deploy.

### 1.2 Lingkungan server asli

Ikuti `01-panduan-integrasi-server.md` sampai checklist akhirnya hijau. Untuk uji
browser dari mesin Anda, hidupkan tunnel SSH terlebih dahulu:

```bash
ssh -N -L 3080:127.0.0.1:3080 -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 a1-8@10.33.109.77
```

Semua perintah uji yang menunjuk `127.0.0.1:3080` berlaku unchanged melalui tunnel.
Uji yang menyentuh database (`check_jalatantra.py`, pembuatan akun uji) harus
dijalankan **di host tempat aplikasi berada**, bukan melalui tunnel.

### 1.3 Data uji bawaan

Lingkungan Demo berisi 8 perangkat persisten dengan skenario sengaja:
`app01` (SSH gagal), `backup01` (disk tinggi), `branch-offline01` (offline).
Lingkungan Real berisi `localhost` dengan SSH yang memang tidak aktif. Kondisi
DOWN/warning tersebut adalah **bahan uji**, bukan kerusakan — jangan "memperbaikinya"
dengan mengubah data.

---

## 2. Lapisan uji otomatis

Jalankan berurutan; catat hasil tiap lapisan pada template laporan §7.

```bash
# 1) Unit API + worker + AI (harapan: Ran 105 tests, OK)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- python3 -B -m unittest discover \
  -s '/mnt/e/AMJ-Network infrastruktur automation/tests' -p 'test_jalatantra_*.py'

# 2) Regresi collector demo (harapan: Ran 14 tests, OK)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- python3 -B -m unittest discover \
  -s '/mnt/e/AMJ-Network infrastruktur automation/tests' -p 'test_collector.py'

# 3) Dashboard & monitoring lokal (harapan: monitoring checks passed)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash -c \
  'cd "/mnt/e/AMJ-Network infrastruktur automation" && python3 tools/build_dashboards.py --check && python3 tools/check_local.py'

# 4) Integrasi live (di host aplikasi; harapan: 13 kelompok passed)
printf '%s' '{"username":"admin","password":"<kata sandi admin>"}' | python3 tools/check_jalatantra.py

# 5) Browser E2E (di Windows; harapan: 10 kelompok tests, errors: []  ·  pakai base_url IP WSL bila localhost terputus)
printf '%s' '{"base_url":"http://IP-WSL:3080","username":"admin","password":"<kata sandi admin>"}' | node tools/browser_jalatantra.mjs
```

Yang dicakup `check_jalatantra.py`: sesi & endpoint terlindungi; larangan tulis
viewer; pembuatan perangkat/duplikat/siklus induk/CSRF/origin; pemeriksaan gagal →
insiden → acknowledge; persetujuan admin + target terkunci + pemulihan simulasi +
insiden selesai otomatis; pembatalan & katalog aksi tetap; perangkat demo baru tanpa
riwayat fabrikasi; penolakan alamat di luar cakupan; audit Ansible read-only di
localhost dengan SSH tetap DOWN; auto-approve per perangkat (langsung eksekusi, gate kembali saat dinonaktifkan); diagnosis read-only dengan lampiran ke insiden; AI opsional (mode aktif diuji sebagai analisis dan saran read-only, mode nonaktif diuji sebagai unavailable); jejak audit & pencabutan sesi. Skrip membuat akun
uji sementara dan membersihkan dirinya sendiri.

Yang dicakup `browser_jalatantra.mjs`: login & wording produk; topologi; toggle auto-approve admin; kartu aksi diagnosis; buat perangkat
→ periksa → edit; rencana otomasi → tolak konfirmasi nama salah → setujui → worker
selesai → log menyatakan simulasi; insiden buat → tangani → selesaikan; arsip perangkat;
pemisah Real/Demo; mobile 390×844 tanpa overflow + drawer; logout. Tangkapan layar dan
`results.json` tersimpan di `%TEMP%\jalatantra-browser-results\`.

**Kriteria lulus lapisan otomatis:** tidak ada kegagalan/skip tak terjelaskan,
`errors: []` pada hasil browser, dan tidak ada regresi pada layanan monitoring lama.

---

## 3. Checklist manual realtime di aplikasi

Kerjakan berurutan sambil mengamati perubahan live. Kolom "Harapan" adalah kriteria
lulus; catat penyimpangan pada laporan.

### 3.1 Login, sesi, dan rate limit

| Langkah | Harapan |
|---|---|
| Login salah kata sandi 1× | Pesan netral "Nama pengguna atau kata sandi salah"; tidak menyebut keberadaan akun |
| Login benar | Masuk ke Ringkasan; banner lingkungan sesuai preferensi terakhir |
| Muat ulang halaman | Sesi bertahan (cookie 8 jam); tidak diminta login ulang |
| Logout dari menu profil | Kembali ke layar login; tombol kembali browser tidak memulihkan sesi |
| Pakai akun uji sementara (§3.2), gagal login 5× | Percobaan ke-6 ditolak 429 dengan pesan tunggu 15 menit; akun lain tidak terdampak |
| Ubah kata sandi sendiri | Berhasil; sesi browser lain akun yang sama dicabut (login ulang diminta) |

### 3.2 Peran (buat akun uji sementara)

Di host aplikasi, sebagai root:

```bash
python3 - <<'EOF'
import getpass, pymysql
from werkzeug.security import generate_password_hash
rootpw = getpass.getpass('Kata sandi root MariaDB: ')
testpw = getpass.getpass('Kata sandi untuk akun uji: ')
c = pymysql.connect(unix_socket='/run/mysqld/mysqld.sock', user='root', password=rootpw,
                    database='jalatantra', autocommit=True)
cur = c.cursor()
for name, role in (('uji_operator', 'operator'), ('uji_viewer', 'viewer')):
    cur.execute('INSERT INTO users(username,role,password_hash) VALUES(%s,%s,%s)',
                (name, role, generate_password_hash(testpw, method='scrypt')))
print('akun uji dibuat')
EOF
```

| Uji | Harapan |
|---|---|
| Viewer: buka semua halaman | Data terlihat; tombol tambah/edit/arsip/periksa/rencana tidak ada atau nonaktif |
| Viewer: paksa POST via curl (§6) | 403 |
| Operator: buat perangkat, periksa, buat insiden, ajukan otomasi | Semua berhasil |
| Operator: buka pekerjaan menunggu persetujuan | Tidak ada tombol setujui; teks "Menunggu persetujuan administrator" |
| Operator: batalkan pekerjaan orang lain | Ditolak 403 |
| Admin: setujui pekerjaan operator | Berhasil setelah konfirmasi nama persis |
| Hapus akun uji setelah selesai (§8) | Sesi dan akun terhapus |

### 3.3 Inventaris perangkat

| Langkah | Harapan |
|---|---|
| Tambah perangkat Demo (nama unik, IP mis. 192.0.2.210, layanan SSH, lokasi isi) | Konfirmasi muncul; setelah simpan, detail terbuka; status "Belum diperiksa" |
| Nama duplikat pada lingkungan sama | Ditolak dengan pesan konflik |
| Alamat hostname (`contoh.id`), multicast, link-local | Ditolak validasi alamat |
| Nama >80 karakter / kosong | Ditolak; batas input form mencegah kelebihan |
| Induk = dirinya sendiri / membentuk siklus | Ditolak |
| Induk beda lingkungan | Ditolak |
| Edit lokasi perangkat | Tersimpan; status kembali "Belum diperiksa"; riwayat pemeriksaan lama tetap ada |
| Cari nama/alamat/lokasi; filter status & jenis | Hasil sesuai; penghitung berubah |
| Arsip perangkat beranak aktif | Ditolak sampai anak dipindah/diarsipkan |
| Arsip perangkat dengan pekerjaan aktif | Ditolak sampai pekerjaan selesai/dibatalkan |
| Arsip perangkat bersih | Hilang dari inventaris aktif; riwayat tetap di Aktivitas |

### 3.4 Topologi

| Langkah | Harapan |
|---|---|
| Buka Topologi | Simpul = perangkat aktif; dikelompokkan per lokasi; jumlah simpul/koneksi sesuai inventaris |
| Pilih simpul | Panel kanan: alamat, status, jenis, cakupan, rute induk terbalik |
| Matikan "Tampilkan koneksi" | Garis hilang, simpul tetap |
| Perangkat tanpa induk | Rute hanya dirinya; teks rute menjelaskan berbasis inventaris |

### 3.5 Pemeriksaan layanan & status realtime

| Langkah | Harapan |
|---|---|
| Detail perangkat → Periksa layanan | Konfirmasi menyebut cakupan lingkungan; toast nomor pekerjaan |
| Amati panel riwayat | Status pekerjaan berjalan → selesai otomatis (polling ±2,4 detik); hasil per layanan + latensi muncul tanpa reload |
| Badge status perangkat | Berubah sesuai hasil; toast akhir muncul |
| Perangkat Demo dengan layanan gagal (app01) | Hasil SSH down; insiden otomatis terbuka di halaman Insiden |
| Tunggu >180 detik tanpa pemeriksaan baru | Status menjadi "Belum diperiksa" (bukan tetap sehat) |
| Perangkat Real di luar cakupan | Tombol periksa nonaktif dengan alasan; POST check ditolak 403 |
| Sembunyikan tab browser lalu kembali | Polling jeda saat tersembunyi dan segar kembali saat terlihat |

### 3.6 Metrik

| Langkah | Harapan |
|---|---|
| Ringkasan Demo | Grafik utilisasi & lalu lintas berlabel SINTETIS; celah ditampilkan sebagai celah |
| Perangkat Demo baru | Metrik kosong ("Belum tersedia"), bukan angka warisan |
| branch-offline01 | Metrik kosong/up 0; tidak ada nilai sehat fabrikasi |
| Perangkat Real localhost | Metrik dari node_exporter bila scraper segar; bila Prometheus mati, pesan netral tanpa detail internal |
| Bandingkan dengan Prometheus (tunnel :9090) | Nilai UI konsisten dengan query `node_*`/`k8_demo_*` untuk instance/device yang sama |

### 3.7 Insiden

| Langkah | Harapan |
|---|---|
| Buat insiden manual (judul, prioritas, rincian) | Tercatat; status Terbuka; penghitung navigasi bertambah |
| Mulai penanganan | Status Ditangani; "Ditugaskan ke" = nama akun Anda |
| Selesaikan tanpa catatan / catatan <8 alfanumerik | Ditolak |
| Selesaikan dengan catatan bermakna | Status Selesai; catatan & waktu penyelesaian tampil |
| Biarkan layanan demo gagal pulih (pastikan layanan aktif lalu periksa) | Insiden fingerprint sama selesai otomatis dengan catatan sistem |
| Gangguan kambuh | Insiden dibuka kembali, bukan duplikat baru |

### 3.8 Otomasi & persetujuan

| Langkah | Harapan |
|---|---|
| Otomasi → Rencanakan otomasi | Pratinjau menampilkan target, mode eksekusi, kebutuhan persetujuan |
| Pilih perangkat inventaris-saja (Real di luar managed) | Tombol ajukan nonaktif + penjelasan |
| Ajukan `ensure_service` pada perangkat Demo | Pekerjaan "Menunggu persetujuan"; tidak ada eksekusi |
| Edit inventaris perangkat itu lalu coba setujui | Ditolak "target telah berubah"; batalkan & ajukan ulang |
| Setujui dengan nama salah | Ditolak inline; pekerjaan tetap menunggu |
| Operator mencoba setujui | 403 |
| Admin setujui dengan nama persis | Antrean → worker → Berhasil; log menyebut "Mode: SIMULASI" dan "Ansible tidak dijalankan"; hasil verifikasi layanan up |
| Ajukan `audit` | Tanpa persetujuan; langsung antrean → selesai; log PLAY RECAP (Real) atau simulasi (Demo) |
| Ajukan aksi sama saat masih aktif | Ditolak 409 |
| Batalkan pekerjaan menunggu/antrean | Status Dibatalkan; tidak dieksekusi |
| Coba batalkan pekerjaan berjalan | Ditolak 409 |
| Amati log live | Log bertambah selama panel terbuka; status akhir menghentikan polling |

### 3.8a Diagnosis layanan (read-only)

| Langkah | Harapan |
|---|---|
| Otomasi | Ada kartu "Diagnosis layanan" berlabel PEMERIKSAAN |
| Buat rencana `diagnose` + pilih layanan | Tanpa langkah persetujuan; langsung antrean |
| Buka insiden terbuka perangkat yang sama | Setelah job selesai, detail insiden bertambah bagian "[Lampiran diagnosis]" berisi status unit, log terakhir, disk, memori |
| Ajukan `diagnose` tanpa memilih layanan | Ditolak 400 |
| Periksa audit | Tercatat `incident.diagnosed` |

Catatan: diagnosis hanya membaca. Tidak ada perintah yang mengubah layanan, dan hasilnya bukan klaim sehat — hanya bukti mentah.

### 3.8b Auto-approve per perangkat

| Langkah | Harapan |
|---|---|
| (Admin) Buka detail perangkat | Ada tombol "Auto-approve layanan" nonaktif |
| Klik → konfirmasi | Tombol menjadi aktif (kuning); audit `auto_approve_changed` |
| (Operator) Ajukan `ensure_service`/`restart_service` | **Langsung antrean**, tanpa langkah persetujuan; audit menyebut "auto-approve perangkat aktif" |
| (Operator) Ajukan `audit`/`diagnose` | Tetap tanpa persetujuan seperti biasa (bukan efek auto-approve) |
| Ubah nama/alamat perangkat saat job antre | Job gagal di worker: "Konfigurasi perangkat berubah" |
| Nonaktifkan auto-approve | Persetujuan admin kembali diwajibkan untuk permintaan baru |
| (Operator) Coba ubah toggle | 403 |
| Periksa batas | Katalog aksi tetap 4; layanan tetap whitelist; alamat tetap harus managed |

### 3.8c Asisten AI (opsional)

| Langkah | Harapan |
|---|---|
| Sebelum dikonfigurasi | Detail insiden menampilkan "Asisten AI tidak aktif…"; aplikasi berjalan normal; `GET /api/ai/status` → `{"available": false}` |
| Menu profil (admin) → Pengaturan AI | Modal dengan sakelar aktif, Base URL, Kunci API (bisa tampil/sembunyi), Model ID, batas waktu & token, tombol Uji koneksi dan Ambil daftar model |
| Isi Base URL ke provider tiruan lokal, model apa pun, kunci apa pun → Uji koneksi | Muncul hasil "Terhubung…" bila provider tiruan hidup; pesan jelas bila tidak |
| Ambil daftar model | Daftar ID model masuk ke pilihan Model ID; kunci tidak ditampilkan |
| Centang Aktifkan, Simpan | Toast "Asisten AI aktif"; audit `ai_settings_changed` |
| Buka insiden | Panel "Analisis asisten" muncul dengan badge `AI · <model> · baca saja` |
| Klik Saran tindak lanjut | Saran berurutan muncul, termasuk jumlah preseden selesai; tidak ada tindakan otomatis |
| Tombol Tanya asisten | Jawaban hanya memakai lingkungan aktif, insiden, perangkat, dan pekerjaan yang terlihat; modal juga menyediakan Prioritaskan insiden dan Buat handover |
| Ganti Demo ↔ Real lalu bertanya | Request AI wajib membawa environment; server menolak request tanpa environment, dan jawaban tidak mencampur data lingkungan lain |
| Muat ulang Pengaturan AI | Kunci tidak ditampilkan; hanya petunjuk 4 karakter terakhir; kosongkan kolom untuk mempertahankan kunci |
| Periksa efek samping | Status insiden, perangkat, pekerjaan **tidak berubah**; audit mencatat pemakaian AI sesuai aksi |
| Nonaktifkan lalu buka insiden | Kembali ke pesan "tidak aktif"; tidak ada 500 |
| (Operator) buka Pengaturan AI | Menu tersembunyi; endpoint mengembalikan 403 |

Catatan: AI tidak pernah menulis ke tabel operasional, tidak memicu Ansible, dan tidak mengubah status insiden. Pengaturan disimpan di tabel `ai_settings`; kunci API tidak pernah dikembalikan ke klien.

### 3.9 Aktivitas & audit

| Langkah | Harapan |
|---|---|
| Buka Aktivitas setelah rangkaian uji | Entri login, device_created/updated/archived, job_requested/approved/cancelled, incident_* dengan aktor & waktu |
| Cari kata kunci | Filter bekerja |
| Ganti lingkungan | Jejak sesuai lingkungan terpilih |

### 3.10 Lingkungan, mobile, dan aksesibilitas

| Langkah | Harapan |
|---|---|
| Ganti Demo ↔ Real | Banner & badge berubah; data tidak bercampur; preferensi tersimpan setelah reload |
| Ringkasan Real | localhost tampil dengan SSH DOWN jujur; tidak ada klaim sehat |
| Lebar 390px | Tanpa scroll horizontal; drawer navigasi terbuka/tertutup; Esc menutup |
| Keyboard saja | Skip-link, fokus terlihat, Esc menutup dialog/drawer, Tab terperangkap di drawer |
| Console browser | Nol error; nol permintaan eksternal (CSP self-only) |

---

## 4. Pengujian perangkat real

Lakukan hanya setelah perangkat terdaftar sesuai `01-panduan-integrasi-server.md` §7
(allowlist + managed_hosts + automation_hosts + exporter terjangkau).

1. **Baca-saja dahulu.** Daftarkan perangkat di UI (Real). Jalankan pemeriksaan:
   harapan hasil per layanan sesuai kondisi nyata (`systemctl is-active <unit>` di
   target sebagai pembanding), latensi terukur, dan riwayat tersimpan.
2. **Metrik nyata.** `curl -s http://<alamat>:9100/metrics | head` dari server harus
   berhasil; UI menampilkan CPU/memori/disk yang cocok dengan Prometheus
   (`node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, dst. untuk instance
   `<alamat>:9100`). Matikan scraper sementara → UI menunjukkan celah/pesan, bukan
   angka basi yang diklaim segar.
3. **Audit.** Ajukan `audit` → tanpa persetujuan → log PLAY RECAP nyata dari target.
4. **Insiden otomatis nyata.** Hentikan layanan non-kritis terdaftar di target
   (mis. `sudo systemctl stop node_exporter` pada node uji) → pemeriksaan berikutnya
   membuat insiden → hidupkan kembali → insiden selesai otomatis. Cocokkan waktu
   insiden dengan waktu pemeriksaan di riwayat.
5. **Perubahan terkontrol.** Ajukan `ensure_service`/`restart_service` pada layanan
   non-kritis di node uji, setujui sebagai admin dengan nama persis, lalu verifikasi
   di target: `systemctl is-active <unit>` dan `journalctl -u <unit> -n 20` menunjukkan
   restart/start pada waktu eksekusi. Hasil pekerjaan harus menyatakan verifikasi
   up; bila verifikasi gagal, pekerjaan gagal (bukan sukses palsu).
6. **Pagar cakupan.** Perangkat Real di luar allowlist: pemeriksaan & otomasi ditolak;
   di dalam allowlist tetapi bukan managed: pemeriksaan boleh, otomasi ditolak.
7. **Jangan** menguji restart pada layanan kritis produksi di luar jendela pemeliharaan;
   gunakan node uji atau layanan non-kritis.

---

## 5. Observasi realtime selama pengujian

Buka tiga jendela pengamatan bersamaan dengan UI:

```bash
# Di host aplikasi
journalctl -u jalatantra-worker -f      # klaim pekerjaan, probe, eksekusi, verifikasi
journalctl -u jalatantra -f             # permintaan HTTP, kode status, error
```

- **Worker:** saat pekerjaan diajukan, amati baris klaim → eksekusi → verifikasi →
  update status; saat siklus 60 detik, amati pemeriksaan berkala dan insiden otomatis.
- **Web:** setiap aksi UI menghasilkan satu baris request dengan kode 2xx; percobaan
  negatif menghasilkan 401/403/409/413/415 sesuai §6.
- **Prometheus** (tunnel :9090): `/targets` menunjukkan kesehatan scrape;
  `/graph` untuk membandingkan angka UI dengan query mentah.
- **DevTools browser:** tab Network memperlihatkan polling 12 detik (halaman) dan
  2,4–2,5 detik (panel pekerjaan); tab Console harus bersih; tab Application →
  Cookies memperlihatkan cookie sesi HttpOnly/SameSite=Strict.
- **UI:** toast, badge status, penghitung insiden navigasi, dan banner lingkungan
  adalah indikator realtime utama; semuanya harus berubah tanpa reload manual.

---

## 6. Uji negatif keamanan (curl)

Jalankan di host aplikasi (atau melalui tunnel). Ganti `<...>` sesuai lingkungan.

```bash
B=http://127.0.0.1:3080
# Tanpa sesi → 401
curl -s -o /dev/null -w '%{http_code}\n' $B/api/devices
# Login simpan cookie + csrf
curl -s -c /tmp/jt.jar -X POST -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<kata sandi>"}' $B/api/login
CSRF=$(python3 -c 'import json;print(json.load(open("/tmp/jt-csrf.json"))["csrf_token"])' 2>/dev/null || true)
# (simpan respons login ke /tmp/jt-csrf.json bila memakai variabel CSRF di atas)
# Tulis tanpa CSRF → 403
curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/jt.jar -X POST -H 'Content-Type: application/json' \
  -d '{}' $B/api/devices
# Origin asing → 403
curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/jt.jar -X POST -H 'Content-Type: application/json' \
  -H 'Origin: https://evil.example' -H "X-CSRF-Token: $CSRF" -d '{}' $B/api/devices
# Body bukan JSON → 415
curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/jt.jar -X POST -H 'X-CSRF-Token: '$CSRF \
  -d 'x=1' $B/api/devices
# Body >64KB → 413
head -c 70000 /dev/zero | curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/jt.jar -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" --data-binary @- $B/api/devices
# Aksi di luar katalog → 400
curl -s -b /tmp/jt.jar -X POST -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"device_id":1,"action":"../../shell"}' $B/api/jobs
```

Harapan: 401, 403, 403, 415, 413, 400 berurutan; tidak ada stack trace atau detail
internal pada body error. Uji viewer/operator memakai akun uji §3.2 dengan pola
yang sama (harapan 403 untuk tulis viewer dan approve operator). Uji rate limit
login memakai akun uji, bukan admin (§3.1).

---

## 7. Kriteria penerimaan dan template laporan

Penerimaan penuh bila: seluruh lapisan §2 lulus; checklist §3 hijau; §4 lulus pada
node uji; §6 sesuai harapan; tidak ada error konsol; deployment idempoten; dan
tidak ada wording non-produk maupun nilai sehat fabrikasi di UI.

Template laporan (salin dan isi):

```
LAPORAN PENGUJIAN JALATANTRA
Tanggal / penguji / lingkungan (lokal WSL | server <alamat>):
1. Unit API+worker:            [Lulus/Gagal]  hasil: Ran __ tests, __
2. Regresi collector:          [Lulus/Gagal]  hasil: Ran __ tests, __
3. Dashboard & monitoring:     [Lulus/Gagal]  catatan:
4. Integrasi live (10 kel.):   [Lulus/Gagal]  kelompok gagal:
5. Browser E2E (7 kel.):       [Lulus/Gagal]  errors: __  screenshot:
6. Manual login/sesi/peran:    [Lulus/Gagal]  catatan:
7. Manual inventaris/topologi: [Lulus/Gagal]  catatan:
8. Manual pemeriksaan/metrik:  [Lulus/Gagal]  catatan:
9. Manual insiden:             [Lulus/Gagal]  catatan:
10. Manual otomasi/persetujuan:[Lulus/Gagal]  catatan:
11. Perangkat real (bila ada): [Lulus/Gagal/Tidak diuji]  node:
12. Negatif keamanan:          [Lulus/Gagal]  kode menyimpang:
13. Mobile & aksesibilitas:    [Lulus/Gagal]  catatan:
14. Idempotensi deployment:    [Lulus/Gagal]  changed run ulang: __
Temuan & tindak lanjut:
- (gejala, langkah reproduksi, dugaan penyebab, status perbaikan)
Keputusan: [Diterima | Diterima dengan catatan | Ditolak]
```

---

## 8. Cleanup dan keselamatan pengujian

1. Hapus akun uji beserta sesinya (root di host aplikasi):
   ```bash
   python3 - <<'EOF'
   import getpass, pymysql
   c = pymysql.connect(unix_socket='/run/mysqld/mysqld.sock', user='root',
                       password=getpass.getpass('Kata sandi root MariaDB: '),
                       database='jalatantra', autocommit=True)
   cur = c.cursor()
   cur.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username IN ('uji_operator','uji_viewer'))")
   cur.execute("DELETE FROM users WHERE username IN ('uji_operator','uji_viewer')")
   print('akun uji dihapus')
   EOF
   ```
2. Arsipkan atau hapus perangkat uji lewat UI/ API (nama berprefiks uji Anda);
   jangan menghapus baris riwayat secara manual kecuali pembersihan terotorisasi.
3. Batalkan pekerjaan uji yang masih menunggu/antrean sebelum menutup sesi.
4. Jangan menguji brute-force pada akun admin nyata; kunci 15 menit akan mengganggu
   pengujian lain. Jangan menguji restart layanan kritis di luar jendela pemeliharaan.
5. Hentikan proses penjaga WSL bila sesi uji lokal selesai; layanan tetap enabled
   untuk boot berikutnya.
6. Simpan laporan dan tangkapan layar bersama tanggal serta versi repository yang
   diuji agar temuan dapat direproduksi.

Selamat menguji — setiap penyimpangan dari kolom "Harapan" adalah temuan yang layak
dicatat, sekecil apa pun.
# PRD — JalaTantra
## Product Requirements Document · Infrastructure Operations

| | |
|---|---|
| Nama produk | JalaTantra |
| Kategori | Operasi infrastruktur: inventaris, pemantauan, insiden, otomasi terkontrol |
| Status dokumen | Hidup — mengikuti rilis v1.0 |
| Antarmuka | Web tunggal, bahasa Indonesia, responsif desktop & mobile |
| Lingkungan operasi | Demo (simulasi sintetis persisten) dan Real (infrastruktur aktual) |

---

## 1. Ringkasan produk

JalaTantra adalah pusat kendali operasi infrastruktur dalam satu antarmuka:
memahami aset dan koneksinya, memantau kesehatan layanan, menangani insiden sampai
selesai, dan menjalankan perubahan layanan melalui otomasi yang meminta persetujuan
eksplisit serta mencatat setiap eksekusi. Produk ini menggantikan kebiasaan
berpindah-pindah antara lembar inventaris, dashboard metrik, dan terminal otomasi
yang tidak saling terhubung.

Janji produk: **Terhubung. Terpantau. Terkendali.** Setiap perubahan dapat
ditelusuri siapa yang meminta, siapa yang menyetujui, apa yang dieksekusi, dan
apa hasilnya.

## 2. Masalah yang diselesaikan

1. Inventaris perangkat tersebar dan tidak terhubung dengan kondisi layanannya.
2. Status kesehatan layanan tidak terlihat dalam satu pandangan; gangguan baru
   diketahui setelah berdampak.
3. Penanganan insiden tidak tercatat: tidak jelas siapa menangani, kapan selesai,
   dan apa tindakannya.
4. Perubahan layanan dijalankan langsung di terminal tanpa persetujuan dan tanpa
   jejak eksekusi yang dapat diaudit.
5. Data simulasi dan data nyata tercampur sehingga keputusan diambil dari angka
   yang salah.

## 3. Tujuan dan ukuran keberhasilan

| Tujuan | Ukuran |
|---|---|
| Satu pandangan kesehatan infrastruktur | Ringkasan menampilkan status seluruh perangkat aktif tanpa berpindah halaman |
| Insiden tertangani sampai selesai | Setiap insiden memiliki status, penanggung jawab, dan catatan penyelesaian |
| Perubahan terkendali | 100% aksi perubahan layanan melewati persetujuan admin + konfirmasi nama target |
| Jejak audit lengkap | Setiap permintaan, persetujuan, pembatalan, dan perubahan inventaris tercatat dengan aktor dan waktu |
| Kejujuran data | Tidak ada nilai sehat fabrikasi; data sintetis selalu berlabel; celah data ditampilkan sebagai celah |
| Akses aman | Tidak ada port aplikasi terbuka ke jaringan publik; akses jarak jauh melalui tunnel SSH |

## 4. Persona dan peran

| Peran | Kebutuhan utama | Hak |
|---|---|---|
| Administrator | Kendali penuh dan persetujuan perubahan | Semua hak operator + menyetujui pekerjaan, membatalkan pekerjaan siapa pun |
| Operator | Mencatat aset, memeriksa layanan, menangani insiden, mengajukan otomasi | Baca + tulis inventaris/insiden/pekerjaan; membatalkan pekerjaan sendiri; tidak dapat menyetujui |
| Viewer | Visibilitas tanpa risiko perubahan | Baca saja seluruh halaman |

Autentikasi memakai akun lokal dengan kata sandi hash scrypt; sesi cookie HttpOnly
SameSite=Strict berbatas 8 jam; pembatasan percobaan login (5 kegagalan / 15 menit
per identitas IP+akun). Manajemen pengguna dilakukan melalui provisioning, bukan
UI (lihat §11).

## 5. Kebutuhan fungsional

### 5.1 Autentikasi dan sesi
- FR-01 Login username/kata sandi dengan pesan kesalahan netral (tidak membocorkan
  keberadaan akun) dan rate limiting.
- FR-02 Logout mencabut sesi di server; perubahan kata sandi mencabut sesi lain.
- FR-03 Ubah kata sandi mandiri (minimal 12 karakter, konfirmasi ulang).
- FR-04 Seluruh endpoint API terlindungi kecuali login dan health; permintaan tulis
  wajib JSON, token CSRF, dan asal same-origin.

### 5.2 Inventaris perangkat
- FR-05 CRUD perangkat: nama, alamat IP literal, jenis (server/router/switch/storage),
  lokasi, layanan dipantau, catatan, perangkat induk, port node exporter.
- FR-06 Validasi ketat: nama 1–80 karakter aman, alamat IP literal (menolak hostname,
  multicast, unspecified, link-local), layanan dari katalog tetap, port 1–65535.
- FR-07 Relasi induk membentuk pohon: menolak siklus, induk beda lingkungan, dan
  induk terarsip.
- FR-08 Arsip lunak (soft-archive): riwayat tetap tersimpan; menolak arsip bila masih
  ada anak aktif atau pekerjaan aktif.
- FR-09 Edit inventaris mengunci perubahan selama pekerjaan aktif, dan mereset status
  kesehatan menjadi "Belum diperiksa" serta membatalkan kelayakan persetujuan yang
  tertunda (revisi target berubah).
- FR-10 Pencarian dan filter status/jenis; pengurutan stabil.

### 5.3 Topologi
- FR-11 Peta simpul berdasarkan relasi inventaris (bukan penemuan jaringan),
  dikelompokkan per lokasi, dengan status per simpul dan rute induk terpilih.
- FR-12 Detail simpul: alamat, jenis, cakupan pengelolaan, rute perangkat, dan
  tautan ke detail perangkat.

### 5.4 Pemeriksaan layanan dan status
- FR-13 Pemeriksaan on-demand per perangkat atas layanan terdaftar (DNS, MariaDB,
  SSH, Prometheus, Grafana, node exporter) dengan hasil per layanan, latensi, dan
  durasi; riwayat pemeriksaan persisten.
- FR-14 Pemeriksaan berkala oleh worker setiap 60 detik untuk perangkat demo dan
  perangkat real dalam cakupan; target dipaginasi dan diprobo paralel terbatas agar
  satu kegagalan tidak menghentikan seluruh putaran.
- FR-15 Status kesehatan diturunkan dari hasil pemeriksaan terakhir dengan masa
  berlaku 180 detik; lewat masa itu status menjadi "Belum diperiksa", bukan sehat.
- FR-16 Cakupan alamat: pemeriksaan hanya untuk alamat dalam `allowed_networks`;
  perangkat di luar cakupan tetap dapat dicatat namun pemeriksaan ditolak.
- FR-17 Lingkungan Demo memakai simulasi sintetis persisten (state layanan per
  perangkat), tidak pernah menghubungi jaringan nyata.

### 5.5 Metrik
- FR-18 Metrik perangkat (CPU, memori, disk, RX/TX, up) dibaca read-only dari
  Prometheus dengan selector terikat inventaris; riwayat 30 menit langkah 30 detik.
- FR-19 Kejujuran metrik: sampel basi (>60 detik), nilai di luar rentang, exporter
  down, atau perangkat offline menghasilkan nilai kosong, bukan angka sehat;
  celah riwayat ditampilkan sebagai celah.
- FR-20 Perangkat demo baru tidak mewarisi riwayat fabrikasi; metriknya kosong
  sampai generator demo menyediakan sampel berlabel sumber demo.
- FR-21 Kegagalan layanan metrik ditampilkan sebagai pesan netral tanpa membocorkan
  alamat/query internal.

### 5.6 Insiden
- FR-22 Insiden otomatis dari hasil pemeriksaan (fingerprint per perangkat+layanan):
  dibuat saat gangguan, dibuka kembali bila kambuh, dan diselesaikan otomatis saat
  layanan pulih dengan catatan sistem.
- FR-23 Insiden manual dengan judul, prioritas (info/warning/critical), dan rincian.
- FR-24 Siklus hidup: Terbuka → Ditangani (menugaskan pengguna saat ini) → Selesai;
  penyelesaian wajib catatan bermakna (minimal 8 karakter alfanumerik).
- FR-25 Daftar insiden dengan filter status/prioritas dan penghitung insiden aktif
  pada navigasi.
- FR-25a Timeline insiden append-only untuk pembuatan, perubahan status, pemulihan
  otomatis, dan lampiran diagnosis; catatan sebelumnya tidak tertimpa.
- FR-25b Anomali metrik berbasis baseline 30 menit: worker hanya membuka peringatan
  setelah lonjakan konsisten, tidak mengubah status perangkat dan tidak memicu otomasi.

### 5.7 Otomasi terkontrol
- FR-26 Katalog aksi tetap: `audit` (baca-saja, tanpa persetujuan), `ensure_service`
  dan `restart_service` (wajib persetujuan admin). Tidak ada aksi bebas/shell.
- FR-27 Pengajuan rencana memilih perangkat, aksi, dan layanan terdaftar pada
  perangkat; pratinjau rencana menampilkan target, mode eksekusi, dan kebutuhan
  persetujuan sebelum diajukan.
- FR-28 Persetujuan admin wajib konfirmasi nama perangkat sama persis; server
  memverifikasi ulang peran, status pekerjaan, revisi target, dan cakupan alamat
  pada saat persetujuan maupun saat eksekusi.
- FR-29 Eksekusi hanya oleh worker terpisah ber-identitas database sendiri:
  playbook tetap, inventory tepercaya, parameter melalui file sementara 0600,
  timeout 120 detik dengan penghentian proses anak yang bersih.
- FR-30 Pekerjaan demo tidak pernah menjalankan Ansible maupun menyentuh jaringan
  nyata; log menyatakan mode simulasi secara eksplisit.
- FR-31 Pekerjaan real menjalankan playbook tetap pada host terkelola
  (`managed_hosts` + `automation_hosts`), lalu memverifikasi hasil dengan
  pemeriksaan layanan; sukses hanya bila layanan target benar-benar aktif.
- FR-32 Antrean dan konkurensi: satu pekerjaan aktif per aksi per perangkat;
  klaim pekerjaan memakai lock baris; pekerjaan yatim saat worker restart ditandai
  gagal tanpa replay otomatis.
- FR-33 Pembatalan hanya untuk status menunggu persetujuan/antrean; operator hanya
  boleh membatalkan pekerjaannya sendiri.
- FR-34 Log eksekusi dan hasil terstruktur tampil live selama panel terbuka, dengan
  status akhir dan riwayat pekerjaan per lingkungan.
- FR-34a Pekerjaan antrean kedaluwarsa setelah 30 menit, permintaan tanpa keputusan
  dibatalkan setelah 7 hari, dan pekerjaan running yang kehilangan pelaporan ditandai gagal.
- FR-34b Worker mempublikasikan heartbeat; riwayat pemeriksaan, pekerjaan, dan audit
  dipangkas otomatis sesuai masa simpan terkonfigurasi.

### 5.8 Aktivitas dan audit
- FR-35 Jejak audit append-only: login/logout, perubahan inventaris, permintaan/
  persetujuan/pembatalan pekerjaan, pembuatan/penanganan insiden, perubahan kata
  sandi, dan pemakaian AI; aktor, waktu UTC, lingkungan, dan perangkat terkait.
- FR-36 Asisten AI opsional dan baca-saja menyediakan ringkasan insiden, saran tindak
  lanjut berbasis riwayat, tanya-jawab, prioritas insiden, dan handover. Pemakaian dibatasi
  per akun, hasil ringkasan singkat di-cache, dan pengalihan penyedia diblokir.
- FR-36a Setiap permintaan AI wajib membawa lingkungan Demo/Real; konteks, cache, audit,
  dan hasilnya dipisahkan tegas agar data sintetis tidak muncul pada jawaban Real.
- FR-37 Katalog read-only mencakup pengumpulan bukti sistem; katalog korektif mencakup
  reload layanan hanya untuk DNS/Prometheus, dengan approval dan verifikasi yang sama
  ketatnya dengan restart.
- FR-36 Halaman Aktivitas dengan pencarian dan filter lingkungan.

### 5.9 Lingkungan dan pengalaman pakai
- FR-37 Pemisah Demo/Real global dengan banner dan badge di setiap panel; preferensi
  tersimpan per browser; data kedua lingkungan tidak pernah bercampur.
- FR-38 Ringkasan operasi: kartu statistik, grafik utilisasi dan lalu lintas dengan
  penanda celah, kesehatan perangkat, insiden aktif, pekerjaan tertunda, aktivitas
  terakhir.
- FR-39 Pembaruan berkala (12 detik) yang tidak merusak panel/modal terbuka; polling
  pekerjaan 2,4–2,5 detik dan jeda saat tab tersembunyi.
- FR-40 Konfirmasi dua lapis untuk tindakan berisiko: dialog konfirmasi dengan
  penjelasan cakupan lingkungan, plus konfirmasi nama persis untuk persetujuan.
- FR-41 Responsif mobile (drawer navigasi, tanpa overflow horizontal), keyboard
  accessible (Esc, fokus terperangkap pada drawer, skip-link), dan toast status.
- FR-42 Seluruh teks antarmuka berbahasa Indonesia dan berorientasi produk; tidak
  memuat konteks pengadaan/aturan internal pembuatnya.

## 6. Aturan bisnis inti

1. **Persetujuan tidak pernah implisit.** Mengajukan rencana ≠ menyetujui. Admin
   mengonfirmasi nama target secara terpisah; perubahan inventaris setelah pengajuan
   membatalkan kelayakan persetujuan.
2. **Cakupan alamat adalah pagar keras.** `allowed_networks` membatasi pemeriksaan;
   `managed_hosts` membatasi otomasi. Keduanya dikonfigurasi server-side, bukan UI.
3. **Data sintetis selalu berlabel.** Demo dinyatakan sintetis di banner, badge,
   log, dan hasil; tidak ada klaim kondisi nyata dari data demo.
4. **Tidak ada angka sehat fabrikasi.** Nilai kosong/basi/down ditampilkan apa
   adanya; keberhasilan otomasi diverifikasi ulang, bukan diasumsikan.
5. **Riwayat tidak dihapus oleh UI.** Arsip perangkat dan penyelesaian insiden
   mempertahankan jejak; penghapusan keras hanya melalui operasi database terotorisasi.
6. **Satu sumber kebenaran inventaris.** Topologi, selector metrik, dan target
   otomasi semuanya diturunkan dari inventaris yang sama.

## 7. Kebutuhan non-fungsional

| Aspek | Ketentuan |
|---|---|
| Keamanan transport | Cookie HttpOnly SameSite=Strict; secure bila non-loopback; CSP self-only; X-Frame-Options DENY; nosniff; Referrer same-origin |
| Keamanan aplikasi | CSRF token per sesi; validasi asal; batas body 64 KB; hash scrypt; rate limit login; pesan error netral tanpa stack trace |
| Hak minimum | Akun web DB hanya SELECT/INSERT/UPDATE/DELETE via unix socket; worker berakun DB terpisah; kode & konfigurasi milik root; sandbox systemd (ProtectSystem=strict, ProtectHome, PrivateTmp, proteksi kernel, tanpa kapabilitas untuk web) |
| Kinerja | Cache metrik 10 detik; fan-out query Prometheus terbatas (6); polling UI 12 detik; worker siklus 60 detik; timeout Ansible 120 detik |
| Keandalan | Deployment idempoten; bootstrap tidak men-seed ulang data yang ada; pekerjaan yatim gagal aman; transaksi DB dengan lock ordering perangkat→pekerjaan |
| Privasi | Tanpa CDN/aset eksternal; tanpa telemetri keluar; rahasia tidak pernah di log, argumen proses, atau respons API |
| Kompatibilitas | Ubuntu 24.04 dengan systemd; browser modern desktop & mobile; akses jarak jauh via tunnel SSH |
| Observabilitas | Log terstruktur systemd journald; health endpoint; audit append-only |

## 8. Arsitektur dan stack teknis

- **Web:** Flask + Gunicorn (2 worker, 4 thread) sebagai pengguna sistem tanpa
  hak istimewa; menyajikan API JSON dan SPA statis.
- **Frontend:** HTML/CSS/JavaScript vanilla + SVG inline; tanpa framework, tanpa
  build step, tanpa dependensi eksternal.
- **Database:** MariaDB (skema `jalatantra`): users, sessions, login_attempts,
  devices, checks, jobs, incidents, audit_events, demo_state.
- **Worker:** proses root terpisah dengan akun DB sendiri; probe layanan,
  pemeliharaan insiden otomatis, eksekusi playbook Ansible tetap, verifikasi hasil.
- **Metrik:** Prometheus + node_exporter; query read-only terikat inventaris;
  generator demo memberi sampel berlabel `source="demo"`.
- **Dashboard internal:** Grafana (datasource Prometheus) untuk kebutuhan internal;
  bukan antarmuka pengguna produk.
- **Otomasi:** Ansible dengan inventory tepercaya dan playbook tetap
  (audit/ensure_service/restart_service); konfigurasi root-only.
- **Provisioning:** playbook Ansible idempoten (role `jalatantra` + role layanan),
  bootstrap skema/seed, unit systemd tersandbox.

Alur data: UI → API (validasi+audit) → MariaDB → worker (klaim pekerjaan) →
probe/Ansible → hasil+verifikasi → MariaDB → UI (polling). Metrik: UI → API →
Prometheus (selector inventaris) → UI.

## 9. Prinsip UI/UX

- Satu ruang operasi: navigasi kiri tetap, breadcrumb, pemisah lingkungan global.
- Status selalu berwarna **dan** berlabel teks; tidak mengandalkan warna saja.
- Setiap tindakan berisiko menjelaskan cakupan (demo/real) dan dampaknya sebelum
  konfirmasi; persetujuan menampilkan nama target yang harus diketik persis.
- Kekosongan dan kegagalan ditampilkan jujur dengan langkah lanjut yang jelas
  ("Belum ada pemeriksaan", "Metrik belum tersedia", tombol coba lagi).
- Kedalaman visual konsisten: kartu, badge, glyph perangkat, dan motif jaringan
  yang sama di seluruh halaman; mode cetak ramah laporan.
- Bahasa Indonesia operasional yang tenang dan tegas; tanpa jargon internal proyek.

## 10. Kriteria rilis ( acceptance )

Rilis dianggap layak bila seluruh lapisan berikut lulus pada lingkungan target:

1. 105 uji unit API, worker, dan AI lulus.
2. 14 uji regresi collector demo lulus; pemeriksaan dashboard dan monitoring lokal lulus.
3. 10 kelompok uji integrasi live lulus (otorisasi, CSRF/origin, siklus insiden,
   persetujuan, eksekusi, pembatalan, cakupan alamat, audit, pencabutan sesi).
4. Uji browser end-to-end desktop+mobile lulus tanpa error konsol/jaringan:
   login → inventaris → pemeriksaan → edit → otomasi → persetujuan → eksekusi →
   insiden → arsip → pemisah lingkungan → mobile → logout.
5. Deployment idempoten (run ulang tidak merusak data) dan layanan lama tidak regresi.
6. Tidak ada wording non-produk di antarmuka; tidak ada nilai sehat fabrikasi.

## 11. Di luar cakupan v1.0 (roadmap)

- Notifikasi keluar (email/IM/webhook) dan eskalasi insiden.
- Retensi/arsip otomatis checks, jobs, audit; ekspor laporan.
- UI manajemen pengguna/peran dan reset kata sandi oleh admin.
- Otomasi multi-node paralel dan playbook kustom oleh pengguna.
- Terminasi TLS/HTTPS native dan akses publik tanpa tunnel.
- Penemuan jaringan otomatis (topologi tetap berbasis inventaris).
- High availability web/worker dan replikasi database.

## 12. Risiko dan mitigasi

| Risiko | Mitigasi |
|---|---|
| Perubahan layanan mengganggu ketersediaan | Persetujuan admin + konfirmasi nama + verifikasi hasil; aksi restart hanya pada layanan terdaftar |
| Data demo disalahartikan sebagai nyata | Label sintetis menyeluruh; pemisah lingkungan; log mode eksplisit |
| Kredensial bocor | Vault provisioning; file 0600 root-only; no_log; rahasia tidak di argumen proses/log/respons |
| Worker disalahgunakan sebagai shell | Katalog aksi tetap; playbook tetap; parameter file sementara; validasi ulang saat eksekusi |
| Kehilangan data operasional | Backup terjadwal di luar server; arsip lunak; skema additif |
| Akses jarak jauh tidak aman | Bind loopback + tunnel SSH; penolakan bind publik tanpa cookie secure |

## 13. Glosarium

- **Simpul/node:** perangkat dalam inventaris yang ditampilkan pada topologi.
- **Cakupan pemeriksaan:** himpunan jaringan (`allowed_networks`) yang boleh diprobe.
- **Host terkelola:** alamat terdaftar (`managed_hosts`) yang boleh menjadi target otomasi.
- **Revisi target:** stempel waktu perubahan inventaris yang mengunci kelayakan persetujuan.
- **Pekerjaan (job):** unit permintaan pemeriksaan/otomasi dengan status dan jejak.
- **Insiden:** catatan gangguan layanan dengan siklus hidup dan catatan penanganan.
- **Demo/Real:** dua lingkungan data terpisah; Demo sintetis persisten, Real aktual.
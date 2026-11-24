# JalaTantra

Portal operasi infrastruktur untuk inventaris perangkat, pemeriksaan layanan, penanganan insiden, dan otomatisasi Ansible dengan persetujuan serta riwayat eksekusi.

## Mulai lokal

Buka **http://127.0.0.1:3080**. Login menggunakan akun `admin` dan password awal yang ditentukan saat deployment. Ganti password melalui menu akun. Password tidak disimpan dalam source code.

Pada Windows/WSL, biarkan satu terminal `wsl -d Ubuntu` terbuka selama memakai aplikasi. Layanan systemd saja tidak selalu mempertahankan sesi WSL. Jika koneksi ditolak, buka Ubuntu kembali; data MariaDB dan Prometheus tetap tersimpan.

### Alur penggunaan

1. Pilih **Demo** untuk simulasi persisten atau **Real** untuk perangkat nyata.
2. Buka inventaris, tambahkan perangkat, pilih layanan yang diperiksa, lokasi, dan perangkat induk jika ada.
3. Jalankan pemeriksaan. Hasil layanan yang gagal menghasilkan insiden otomatis; pekerjaan pemeriksaan yang selesai tidak berarti perangkat sehat.
4. Tinjau atau akui insiden. Insiden manual juga dapat dibuat dan diselesaikan dengan catatan.
5. Pilih tindakan dari katalog otomatisasi. Audit bersifat baca-saja. Memulai atau me-restart layanan membutuhkan persetujuan administrator dengan konfirmasi nama perangkat.
6. Tinjau log eksekusi dan verifikasi sesudah tindakan. Pemulihan layanan menutup insiden otomatis yang terkait.

Status yang belum diperiksa atau kedaluwarsa tidak ditampilkan sebagai sehat. Grafik tidak mengisi data kosong dengan nol atau riwayat buatan. Topologi mengikuti relasi induk yang tercatat dalam inventaris, bukan hasil penemuan jaringan otomatis.

## Data demo dan nyata

Delapan perangkat simulasi diinisialisasi sekali ke MariaDB, beserta relasi topologi dan kondisi layanannya. Skenario awal mencakup layanan SSH simulasi pada `app01` yang gagal, peringatan kapasitas `backup01`, dan `branch-offline01` yang offline. Ini adalah skenario sintetis, bukan perangkat yang dihubungi melalui jaringan.

Perubahan inventaris, tindakan, insiden, dan riwayat tersimpan dalam database `jalatantra`. Deployment ulang tidak mereset data demo maupun password akun. Penghapusan perangkat melalui portal mengarsipkan inventaris sambil mempertahankan riwayatnya.

Metrik beban demo berasal dari generator persisten yang sudah tersedia. Dataset generator berada di `/var/lib/kelompok8/demo-devices.json`, state penghitung di `/var/lib/kelompok8/demo-state.json`, dan time-series di Prometheus. Identitas path/metric internal ini tidak menjadi identitas produk. Metrik beban dan hasil tindakan simulasi layanan adalah dua sumber berbeda: tindakan layanan tidak mengubah skenario beban generator. Perangkat demo baru tidak otomatis memperoleh metrik historis. State layanan dan disk simulasi untuk pemeriksaan disimpan di tabel `demo_state`.

Mode Real diinisialisasi dengan `localhost`. Layanan yang tidak aktif, termasuk SSH, ditampilkan apa adanya. Aktivasi atau restart layanan nyata tidak dilakukan hanya karena pengguna membuka dashboard.

## Arsitektur

- Portal: Flask, Gunicorn, HTML/CSS/JavaScript lokal tanpa frontend framework atau CDN.
- Database operasional: MariaDB, berisi akun, sesi, perangkat, pemeriksaan, insiden, pekerjaan, dan audit.
- Metrik: Prometheus dan Node Exporter; endpoint backend membatasi query yang dapat dijalankan.
- DNS: Bind9.
- Otomatisasi: worker terpisah, empat playbook tetap (audit, diagnosis, pastikan layanan, restart), target inventory yang didaftarkan operator sistem.
- Grafana: komponen monitoring internal, tetap tersedia untuk operator pada loopback port 3000; bukan antarmuka utama produk.
- Asisten AI opsional: ringkasan insiden, saran tindak lanjut, dan tanya-jawab baca-saja; worker mendeteksi anomali metrik terhadap baseline tanpa memicu otomasi.

Aplikasi web berjalan sebagai akun OS `jalatantra` tanpa privilege root. Autentikasi database web memakai Unix socket. Worker berjalan terpisah dengan akun database khusus dan credential root-only; source, konfigurasi target, dan playbook dimiliki root. Worker menolak action, service, alamat, atau revisi konfigurasi yang tidak sesuai rencana yang disetujui. Browser tidak menerima endpoint shell, SQL, URL probe bebas, atau unggahan playbook.

Peran akun: `viewer` membaca, `operator` mengelola inventaris/insiden dan meminta tindakan, `admin` menyetujui tindakan. Deployment membuat satu admin awal; pengelolaan akun tambahan belum tersedia di UI. Sesi memakai cookie HttpOnly/SameSite Strict, token CSRF, pemeriksaan origin, dan pembatasan percobaan login.

## Deployment Ubuntu

Target awal adalah Ubuntu 24.04 dengan systemd, Python 3, sudo, Ansible, dan akses repositori paket. Portal dan MariaDB harus berada pada host yang sama. Penyebaran infrastruktur pendukung ke beberapa host tersedia melalui inventory Ansible, tetapi pemisahan database portal belum didukung.

Dari direktori proyek:

```bash
ansible-galaxy collection install -r requirements.yml
export ANSIBLE_ROLES_PATH="$PWD/roles"
ansible-playbook -i inventory/hosts.yml playbooks/site.yml --syntax-check
sudo python3 tools/deploy_local.py
```

Pada mount Windows `/mnt/...`, Ansible dapat mengabaikan `ansible.cfg` karena direktori dianggap world-writable. Wrapper menggunakan inventory dan role path eksplisit serta hanya menargetkan localhost.

Wrapper meminta password root MariaDB saat ini, password akun database pendukung, password awal Grafana, dan password awal JalaTantra. Password JalaTantra minimal 12 karakter ketika admin belum ada; boleh kosong saat rerun. Password Grafana hanya diterapkan saat inisialisasi pertama. Root MariaDB pada instalasi baru dapat menggunakan autentikasi socket tanpa password. Jangan memakai credential uji lokal untuk deployment lain.

Secret dikirim melalui file sementara mode 0600 di `/run`, lalu otomatis dihapus setelah Ansible selesai. Untuk deployment melalui Vault, simpan `mariadb_login_password`, `mariadb_app_password`, `grafana_admin_password`, dan `jalatantra_admin_password` dalam Vault, bukan source code. `mariadb_root_password` opsional jika ingin mengatur password root.

```bash
ansible-vault encrypt inventory/group_vars/all.yml
ansible-playbook -i inventory/hosts.yml playbooks/site.yml --ask-vault-pass
```

Memperbarui portal saja:

```bash
sudo python3 tools/deploy_local.py --tags jalatantra
```

## Mendaftarkan perangkat nyata

Inventaris portal saja tidak memberikan izin akses jaringan. Secara default hanya `127.0.0.0/8` yang boleh diperiksa dan hanya `127.0.0.1` yang dapat dikelola dengan Ansible.

1. Tambahkan alamat/subnet yang Anda kelola ke `jalatantra_allowed_networks` pada inventory vars.
2. Untuk otomatisasi, daftarkan alamat ke alias pada `jalatantra_managed_hosts` dan koneksi Ansible alias tersebut pada `jalatantra_automation_hosts`. Pastikan pemetaan alamat dan alias benar; file ini merupakan konfigurasi tepercaya, bukan input pengguna portal.
3. Siapkan akses SSH dan known_hosts dari operator sistem. Konfigurasi worker saat ini melindungi direktori home; letakkan kunci/known_hosts yang diperlukan di lokasi root-only di luar home dan konfigurasikan secara eksplisit. Verifikasi remote enrollment sebelum mengaktifkan tindakan perubahan.
4. Deploy konfigurasi ulang. Daftarkan perangkat dengan alamat IP literal dan layanan yang benar dalam mode Real.
5. Untuk grafik host, pasang Node Exporter, tambahkan target ke `prometheus_node_exporter_targets`, dan sesuaikan `exporter_port` di perangkat. Instance Prometheus harus berbentuk `alamat:port`.
6. Uji pemeriksaan dan audit baca-saja dahulu. Tidak ada koneksi otomatis ke alamat contoh, VPN, atau jaringan lain di luar allowlist.

`inventory/multi-node.example.yml` hanya contoh. Jangan jalankan alamat contoh sebelum menggantinya dengan target yang berizin. DNS probe mengikuti `jalatantra_dns_probe_name`; sesuaikan dengan record yang memang tersedia pada server DNS target.

## Pemeriksaan operasional

```bash
sudo systemctl status jalatantra jalatantra-worker mariadb prometheus prometheus-node-exporter grafana-server
sudo journalctl -u jalatantra -u jalatantra-worker -n 60 --no-pager
curl -fsS http://127.0.0.1:3080/api/health
python3 -B -m unittest discover -s tests -v
python3 tools/build_dashboards.py --check
python3 tools/check_local.py
```

`tools/check_jalatantra.py` adalah uji integrasi lokal yang menerima JSON login melalui stdin. Jalankan sebagai root pada host aplikasi. Uji membuat perangkat sementara, menguji alur persetujuan simulasi, mengarsipkannya, serta menjalankan audit Ansible baca-saja pada localhost. Riwayat pengujian tetap tercatat; uji tidak me-restart layanan nyata.

`tools/browser_jalatantra.mjs` menguji portal menggunakan Edge headless lokal melalui Chrome DevTools Protocol. Tidak membutuhkan Playwright; credential diterima melalui stdin dan profil browser sementara dibersihkan.

## Batas operasional saat ini

- Default semua listener terbatas loopback. Untuk akses jarak jauh, gunakan SSH tunnel. Publikasi jaringan membutuhkan HTTPS, secure cookies, firewall, backup, dan evaluasi keamanan deployment; jangan membuka HTTP langsung ke internet.
- Pemeriksaan layanan berbasis DNS, TCP, dan health endpoint tetap, bukan pemindaian port bebas atau SNMP. Status UP layanan TCP hanya membuktikan koneksi port berhasil. Probe MariaDB localhost juga menjalankan SELECT 1; target remote hanya diuji koneksi TCP.
- Worker memeriksa sampai 200 perangkat aktif per siklus dan menjalankan satu pekerjaan pada satu waktu. Pekerjaan perubahan yang terinterupsi tidak diputar ulang otomatis.
- Tidak ada retensi otomatis riwayat MariaDB, notifikasi eksternal, penemuan perangkat otomatis, atau pengelolaan pengguna melalui UI. Prometheus menggunakan retensi bawaan 15 hari.
- Sebelum penggunaan produksi, siapkan backup/restore MariaDB dan konfigurasi, rotasi secret, kebijakan retensi, serta uji akses dari klien yang sebenarnya. Pengujian lokal bukan bukti kesiapan produksi atau keberhasilan deployment remote.

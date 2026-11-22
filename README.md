# Aplikasi PMB, KRS, Penjadwalan, dan Manajemen Nilai — Tugas Minggu 9 (lanjutan Minggu 3–8)

Aplikasi akademik berbasis FastAPI, SQLAlchemy 2.0, Alembic, dan SQLite dengan modul PMB, KRS, penjadwalan kelas, observer, transactional outbox, invalidasi KRS, Conflict Resolver, dan ekspor kalender.

**Panduan terbaru (Minggu 9):** [README_MINGGU9.md](README_MINGGU9.md) · [ADR Kebijakan Nilai](docs/ADR-004-grade-policy.md) · [OPAR Minggu 9](docs/OPAR_MINGGU9.md) · [AI Usage Log Minggu 9](AI_USAGE_LOG_MINGGU9.md).

**Arsip dokumentasi Minggu 8:** [README_MINGGU8.md](README_MINGGU8.md) · [UML Sequence Minggu 8](docs/SEQUENCE_OBSERVER_MINGGU8.md) · [OPAR Minggu 8](docs/OPAR_MINGGU8.md) · [AI Usage Log Minggu 8](AI_USAGE_LOG_MINGGU8.md).

## Fitur

- Registrasi calon mahasiswa dengan validasi Pydantic dan email unik.
- Persetujuan (`approve`) dan penolakan (`reject`) pendaftar.
- Generator NIM otomatis dengan format `YYYYKKKNNNN` (11 digit, tanpa strip).
- Counter NIM terpisah berdasarkan kombinasi tahun dan kode program studi.
- Approve idempotent: approve berulang mengembalikan NIM lama tanpa menaikkan counter.
- Proteksi transaksi dan penguncian database untuk menghindari nomor urut ganda.
- Endpoint status pendaftaran dan statistik menggunakan agregasi `GROUP BY`.
- Pengujian otomatis Pytest dan laporan coverage.
- Modul KRS: empat tabel inti (`matakuliah`, `krs`, `krs_detail`, `prerequisite`) ditambah `skala_nilai`.
- KRS Manager untuk menambah, menghapus, dan memvalidasi mata kuliah.
- Chain of Responsibility dengan empat validator: duplikasi, SKS, prasyarat, dan bentrok jadwal.
- Query prasyarat menggunakan `NOT EXISTS` dan pembobotan nilai numerik.
- Penguncian KRS dan transaksi untuk mencegah race condition saat penambahan mata kuliah.

## Format NIM

NIM disimpan sebagai 11 digit angka: `YYYYKKKNNNN`.

- `YYYY`: tahun persetujuan (UTC).
- `KKK`: kode program studi, tepat tiga digit angka.
- `NNNN`: nomor urut empat digit, dimulai dari `0001` untuk setiap kombinasi tahun dan kode prodi.

Contoh: `20260010001`. Format tanpa strip dipilih agar konsisten dengan pola 11 digit yang diminta pada contoh pengujian video. Keputusan ini didokumentasikan di README.

## Menjalankan aplikasi

```bash
python -m venv .venv
```

Windows:
```powershell
.venv\Scripts\Activate.ps1
```

Install dependensi dan buat database:
```bash
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Buka Swagger UI: http://127.0.0.1:8000/docs
Alternatif dokumentasi: http://127.0.0.1:8000/redoc

## Data referensi

Kode program studi untuk generator NIM wajib berupa tiga digit angka, misalnya `001` atau `002`. Seed awal menyiapkan kode `001` untuk Sistem Informasi dan kode jalur masuk SNBP, SNBT, serta Mandiri. Jika database lama masih memiliki kode nonnumerik seperti `SIF`, ubah kode tersebut menjadi kode tiga digit sebelum melakukan approve.

```bash
python -m app.seed
```

## Endpoint API

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/pmb/register` | Registrasi calon mahasiswa |
| PUT | `/api/pmb/{candidate_id}/approve` | Menyetujui pendaftar dan membuat NIM |
| PUT | `/api/pmb/{candidate_id}/reject` | Menolak pendaftar pending |
| GET | `/api/pmb/status/{candidate_id}` | Melihat status pendaftaran |
| GET | `/api/pmb/stats` | Statistik pendaftar |

### Kode respons penting

- `201`: registrasi berhasil.
- `200`: approve/reject/status/stats berhasil.
- `400`: referensi atau kode program studi untuk NIM tidak valid.
- `404`: ID pendaftar tidak ditemukan.
- `409`: email duplikat atau konflik transisi status.
- `422`: format request gagal divalidasi Pydantic/FastAPI (termasuk nomor telepon tidak valid).

## Strategi konsistensi NIM

- Kolom `calon_mahasiswa.nim` memiliki unique constraint sebagai perlindungan terakhir.
- Counter memiliki primary key gabungan `tahun` dan `kode_prodi`.
- Generator menaikkan counter dalam transaksi endpoint approve dan tidak melakukan commit sendiri.
- Pada MySQL/InnoDB, query counter menggunakan `SELECT ... FOR UPDATE`; unique constraint dan retry menjadi perlindungan untuk konflik pembuatan counter pertama.
- SQLite tidak mendukung row-level `SELECT FOR UPDATE`. Karena itu, proses approve memulai transaksi dengan `BEGIN IMMEDIATE` sebelum membaca data sehingga transaksi penulis terserialisasi. Unique constraint NIM tetap aktif.
- SQLite in-memory pada pengujian tidak membuktikan perilaku row lock MySQL. Uji beban multi-worker dan verifikasi locking MySQL masih perlu dilakukan bila lingkungan MySQL tersedia.

## Pengujian

Jalankan semua tes dan ukur coverage:

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

Tes menggunakan database SQLite in-memory, fixture Pytest, dan dependency override FastAPI. Database pengujian tidak menggunakan database pengembangan.

## Fondasi Modul KRS (Minggu 5)

### Format semester
Semester disimpan sebagai lima karakter: `YYYY1` untuk semester ganjil dan `YYYY2` untuk semester genap. Format ini menjaga pengurutan leksikografis sama dengan urutan semester. KRS hanya dapat dibuat untuk NIM yang sudah ada pada `calon_mahasiswa.nim` (mahasiswa yang telah di-approve).

### Tabel dan constraint
- `matakuliah`: kode, nama, SKS (1–4), hari (1=Senin sampai 6=Sabtu), jam mulai dan selesai.
- `krs`: satu kartu per NIM per semester; status awal `draft`.
- `krs_detail`: mata kuliah di dalam kartu, nilai nullable untuk hasil akhir semester.
- `prerequisite`: tabel penghubung self-referencing antara mata kuliah dan prasyarat.
- `skala_nilai`: pemetaan nilai huruf ke bobot dan status lulus. Seed nilai A=4, B=3, C=2 (lulus), D=1 dan E=0 (tidak lulus).

Unique constraint pada `(nim, semester)` dan `(krs_id, kode_mk)` sekaligus menyediakan indeks untuk pencarian yang sesuai. Primary key gabungan `prerequisite(kode_mk, kode_prasyarat)` melindungi pasangan prasyarat dari duplikasi.

### Chain of Responsibility
Urutan implementasi dipilih `Duplicate → SKS → Prerequisite → Conflict`. Duplikasi ditempatkan pertama karena pemeriksaannya murah dan tidak membutuhkan query tambahan. Rantai berhenti pada kegagalan pertama untuk `add_course`. `validate_krs` mengumpulkan kesalahan dari seluruh mata kuliah pada kartu. Keputusan ini juga dicatat dalam `docs/ADR-001-krs-validation.md`.

Bentrok jadwal diperiksa dengan irisan interval: hari sama, `mulai_A < selesai_B`, dan `mulai_B < selesai_A`. Karena menggunakan operator `<`, dua kelas yang bersambung tepat pada batas waktu tidak dianggap bentrok.

### Endpoint KRS Minggu 5
| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/krs/{nim}/{semester}/courses` | Tambah mata kuliah; body `{"kode_mk":"IF101"}` |
| DELETE | `/api/krs/{nim}/{semester}/courses/{kode_mk}` | Hapus mata kuliah |
| GET | `/api/krs/{nim}/{semester}/validate` | Validasi seluruh KRS |
| GET | `/api/krs/{nim}/{semester}` | Lihat isi dan total SKS |

`semester` harus berbentuk `YYYY1` (ganjil) atau `YYYY2` (genap). `add_course` dan `remove_course` hanya dapat mengubah KRS berstatus `draft` atau `revision`. Minggu 5 belum mengimplementasikan transisi state machine `submit`/`approve`; bagian tersebut dikerjakan pada Minggu 6.

### Query prasyarat dan bukti indeks
Query aplikasi menggunakan `NOT EXISTS` terhadap riwayat KRS mahasiswa dan `skala_nilai.bobot >= 2` dengan `lulus = true`; nilai huruf tidak dibandingkan sebagai string. Untuk memeriksa rencana query SQLite pada database yang telah dimigrasikan dan di-seed, jalankan:

```sql
EXPLAIN QUERY PLAN
SELECT m.nama
FROM prerequisite p
JOIN matakuliah m ON m.kode_mk = p.kode_prasyarat
WHERE p.kode_mk = 'IF201'
  AND NOT EXISTS (
    SELECT 1
    FROM krs_detail kd
    JOIN krs k ON k.id = kd.krs_id
    JOIN skala_nilai sn ON sn.nilai = kd.nilai
    WHERE k.nim = 'NIM_MAHASISWA'
      AND k.semester < '20261'
      AND kd.kode_mk = p.kode_prasyarat
      AND sn.lulus = 1 AND sn.bobot >= 2
  );
```

Perhatikan `SEARCH ... USING INDEX` dibandingkan `SCAN` pada hasil. Unique constraint menyediakan indeks pada pasangan NIM-semester dan KRS ID-kode MK; primary key prerequisite mengindeks kode MK pada posisi pertama. Hasil EXPLAIN bergantung pada ukuran dan statistik database, sehingga bukti aktual harus diambil dari database pengujian/pengembangan yang digunakan. SQLite EXPLAIN tidak membuktikan row locking MySQL.

### Transaksi dan row lock
Pada database yang mendukungnya, KRS dibaca dengan `SELECT ... FOR UPDATE`. SQLite mengabaikan `FOR UPDATE`, sehingga kode memakai `BEGIN IMMEDIATE` untuk menserialisasi penulis. Validasi dan insert detail dilakukan dalam satu transaksi; commit hanya dilakukan setelah validasi berhasil. Pengujian SQLite tidak dapat membuktikan row-level lock MySQL/InnoDB.

## Migration

Migration `0001_initial` membuat tabel dasar PMB, `0002_nim_counter` menambahkan counter NIM, `0003_krs_module` menambahkan skema KRS, dan `0004_krs_state_machine` menambahkan dukungan state machine KRS.

Database baru:
```bash
alembic upgrade head
```

Database Minggu 3 yang tabel-tabelnya sudah ada tetapi tabel `alembic_version` kosong (seperti kondisi database yang ditemukan pada arsip awal):
1. Cadangkan `pmb.db` terlebih dahulu.
2. Tandai skema lama sebagai revisi awal, tanpa membuat ulang tabel:
```bash
alembic stamp 0001_initial
```
3. Terapkan migration counter:
```bash
alembic upgrade head
```

Jangan menjalankan `alembic stamp` pada database kosong. Untuk database kosong, langsung gunakan `alembic upgrade head`.

Untuk menguji rollback pada database khusus, gunakan konfigurasi database uji dan jangan melakukan downgrade pada database yang berisi data penting.

Contoh hasil `EXPLAIN QUERY PLAN` dari SQLite setelah migration dan seed pada project ini menunjukkan penggunaan indeks:

```text
SEARCH p USING COVERING INDEX sqlite_autoindex_prerequisite_1 (kode_mk=?)
SEARCH k USING COVERING INDEX sqlite_autoindex_krs_1 (nim=? AND semester<?)
SEARCH kd USING INDEX sqlite_autoindex_krs_detail_1 (krs_id=? AND kode_mk=?)
SEARCH sn USING INDEX sqlite_autoindex_skala_nilai_1 (nilai=?)
SEARCH m USING INDEX sqlite_autoindex_matakuliah_1 (kode_mk=?)
```

Ini merupakan bukti rencana query pada SQLite lokal hasil seed, bukan jaminan rencana yang sama pada MySQL atau database produksi.

## Modul KRS (Minggu 6) – State Machine dan Approval

### State dan transisi yang diizinkan

| Status asal | Aktor | Status tujuan | Keterangan |
|---|---|---|---|
| `draft` | mahasiswa pemilik | `submitted` | Mengajukan KRS setelah validasi dan tidak kosong |
| `submitted` | dosen PA terdaftar | `approved` | Menyetujui KRS |
| `submitted` | dosen PA terdaftar | `revision` | Mengembalikan KRS dengan catatan revisi |
| `revision` | mahasiswa pemilik | `submitted` | Mengajukan ulang setelah perbaikan |

Tidak ada transisi `draft → approved` atau `revision → approved`. `approved` adalah status akhir. Pengecekan dilakukan oleh `KRS.check_transition()` dan perubahan status hanya dilakukan melalui `KRS.transition()` pada service.

### Endpoint Minggu 6

| Method | Endpoint | Body | Aktor |
|---|---|---|---|
| POST | `/api/krs/{nim}/{semester}/submit` | `{"version": 1}` | Mahasiswa pemilik |
| POST | `/api/krs/{nim}/{semester}/approve` | `{"dosen_pa_id": 501, "version": 2}` | Dosen PA yang sama |
| POST | `/api/krs/{nim}/{semester}/revise` | `{"dosen_pa_id": 501, "version": 2, "catatan": "Lengkapi mata kuliah wajib."}` | Dosen PA yang sama |

Contoh header aktor untuk Swagger/demo:

Mahasiswa:
```text
X-Actor-Role: mahasiswa
X-Actor-NIM: 20260010001
```

Dosen PA:
```text
X-Actor-Role: dosen_pa
X-Actor-Id: 501
```

**Penting:** Header tersebut hanya simulasi identitas untuk tugas dan test, bukan autentikasi yang aman untuk produksi. Dalam aplikasi nyata, role/NIM/ID dosen harus berasal dari token atau session login tervalidasi. Body `dosen_pa_id` harus sama dengan `X-Actor-Id` dan dengan `krs.dosen_pa_id` yang sudah ditetapkan oleh proses akademik.

### Menetapkan dosen PA untuk data demo

Sebelum pengujian approve/revise, baris KRS perlu memiliki `dosen_pa_id`. Untuk database lokal yang memang digunakan sebagai data demo, nilai dapat ditetapkan melalui SQL:

```sql
UPDATE krs
SET dosen_pa_id = 501
WHERE nim = '20260010001' AND semester = '20261';
```

Jangan memakai query demo ini sebagai mekanisme penetapan dosen pada sistem produksi; penetapan harus berasal dari data penugasan akademik.

### Transaksi, audit, dan notifikasi

- `submit_krs`: mengunci KRS, memeriksa versi dan transisi, menolak KRS kosong, menjalankan ulang semua validator, mengubah status dan mencatat waktu submit.
- `approve_krs`: memeriksa versi dan kepemilikan dosen PA, lalu menyimpan status `approved`, `approved_at`, `krs_log`, dan `krs_notification` dalam satu transaksi.
- `revise_krs`: memeriksa dosen PA, mewajibkan catatan, mengubah status menjadi `revision`, dan mencatat log/notifikasi dalam satu transaksi.
- `KRS.version` menggunakan SQLAlchemy `version_id_col`. Versi yang dikirim klien wajib cocok dengan versi database; versi usang menghasilkan HTTP 409.
- Add/remove juga memperbarui `krs.updated_at`, sehingga perubahan pada `krs_detail` menaikkan versi parent.
- SQLite memakai `BEGIN IMMEDIATE`; database dengan dukungan row-level locking memakai `SELECT FOR UPDATE`.
- Notifikasi pada tahap ini hanya berupa record database. Pengiriman email/push tidak dilakukan di dalam transaksi dan menjadi pengembangan pada tahap berikutnya.

### Kode respons

- `400`: aturan bisnis gagal, misalnya KRS kosong, validasi gagal, atau catatan revisi kosong.
- `403`: role/identitas/ownership tidak berhak.
- `404`: mahasiswa, mata kuliah, atau KRS tidak ditemukan.
- `409`: transisi ilegal, KRS sedang terkunci oleh status, atau versi yang dikirim sudah usang.
- `422`: format body/header tidak sesuai validasi FastAPI/Pydantic.

### Pengujian Minggu 6

- Hypothesis property SKS memakai `max_examples=1000`, menambahkan mata kuliah satu per satu, dan memeriksa bahwa sistem tidak pernah menerima total di atas 24 serta tidak menolak tanpa alasan.
- Hypothesis property bentrok membangkitkan hari, jam, dan durasi acak; oracle pengujian menggunakan himpunan slot jam yang terpisah dari rumus validator.
- State machine menguji 32 kombinasi status asal, status tujuan, dan aktor: 4 transisi legal serta 28 kombinasi ilegal.
- Integration test mencakup KRS kosong, submit/approve, dosen PA salah, versi usang, revise dan submit ulang, serta ownership mahasiswa.

Jalankan:
```bash
pip install -r requirements.txt
alembic upgrade head
python -m pytest -q
```

Hasil validasi terbaru:
- `python -m pytest -v --cov=app --cov-report=term-missing` menghasilkan 64 passed, 0 failed, dan 0 errors; total coverage aplikasi 85%.
- Hypothesis berhasil dijalankan setelah dependensi dipasang. Dua property test utama menggunakan `max_examples=1000`, masing-masing untuk batas maksimal SKS dan bentrok jadwal.
- Pengujian parameterized mencakup empat transisi legal dan 28 transisi ilegal.
- `alembic upgrade head` berhasil sampai migration `0004_krs_state_machine`, dan `alembic current` menunjukkan `0004_krs_state_machine (head)`.
- Database SQLite lokal berhasil dibuat dengan tabel hasil migrasi.
- Terdapat satu peringatan deprecation dari integrasi Starlette TestClient dan HTTPX, tetapi seluruh tes tetap berhasil.
- Pengujian row-level locking MySQL/InnoDB, race condition lintas worker, dan rollback akibat kegagalan transaksi belum dilakukan. SQLite tidak membuktikan perilaku tersebut.


## Penyelesaian Modul KRS (Minggu 6)

Folder proyek dan paket pengumpulan ini menggunakan nama `pmb_app_tugas_minggu6_krs`.
Implementasi Minggu 6 melanjutkan fondasi Minggu 5, bukan mengganti modul PMB/KRS yang sudah ada.

Fitur Minggu 6:
- State machine status `draft`, `submitted`, `approved`, dan `revision` dengan transisi berbasis aktor.
- Operasi `submit_krs`, `approve_krs`, dan `revise_krs`.
- Pemeriksaan role dan ownership pada endpoint serta service.
- Penolakan KRS kosong dan validasi ulang ketika submit/approve.
- Audit log dan notifikasi database dalam transaksi approval.
- Pessimistic locking sesuai dialect dan optimistic versioning.
- Property-based test SKS dan bentrok jadwal dengan 1.000 contoh masing-masing.
- Pengujian 32 kombinasi status/aktor: 4 transisi legal dan 28 ilegal.
- AI Usage Log, OPAR, ADR-002, dan Pull Request template.

Lihat `docs/VERIFIKASI_MINGGU6.md` untuk batas verifikasi, risiko, dan perintah pengujian.

---

## Implementasi Minggu 7 - Jadwal dan Ruangan

Minggu 7 melanjutkan aplikasi PMB dan KRS dengan modul pengelolaan jadwal perkuliahan, ruangan, dosen, dan kelas. Implementasi sebelumnya tetap dipertahankan sebagai fondasi sistem.

### Fitur Minggu 7

- Model SQLAlchemy untuk `ruangan`, `dosen`, `kelas`, dan `jadwal`.
- Migration Alembic `0005_scheduling`, termasuk foreign key, constraint, dan indeks.
- Validasi hari dan interval waktu jadwal.
- Deteksi bentrok ruangan dan dosen menggunakan algoritma naive serta grouping dan sweep.
- Interval setengah terbuka: jadwal yang berakhir tepat saat jadwal lain dimulai tidak dianggap bentrok.
- Validasi kapasitas ruangan berdasarkan kuota kelas dan jumlah mahasiswa terdaftar.
- SchedulingService untuk membuat, memperbarui, menghapus, dan memeriksa konflik jadwal.
- API penjadwalan dengan respons HTTP terstruktur.
- Seed data minimal 10 ruangan, 15 dosen, dan 40 jadwal.
- Pengujian API dan property-based testing menggunakan Hypothesis.

### Hasil Verifikasi Minggu 7

Pemeriksaan pada lingkungan pengembangan lokal menghasilkan:

- `python -m pytest -v`: **74 passed**, dengan satu peringatan deprecation.
- Migration database berhasil mencapai `0005_scheduling (head)`.
- `python -m alembic check`: tidak ditemukan operasi upgrade baru.
- Seed menghasilkan 10 ruangan, 15 dosen, 40 kelas, dan 40 jadwal.
- Pemeriksaan 40 jadwal hasil seed tidak menemukan konflik.
- Dua pengujian properti Hypothesis untuk modul penjadwalan berhasil dijalankan.

Hasil tersebut merupakan verifikasi lokal, bukan klaim bahwa seluruh skenario produksi telah diuji. Pengujian concurrency pada PostgreSQL/MySQL dan beban multi-worker masih menjadi batasan.

### Dokumentasi Minggu 7

- [Panduan instalasi dan endpoint Minggu 7](README_MINGGU7.md)
- [ADR-003: Strategi deteksi konflik](docs/ADR-003-scheduling-interval-tree.md)
- [OPAR Minggu 7](docs/OPAR_MINGGU7.md)
- [Laporan verifikasi Minggu 7](docs/VERIFIKASI_MINGGU7.md)
- [AI Usage Log Minggu 7](AI_USAGE_LOG_MINGGU7.md)

### Riwayat Pengembangan dan Penggunaan AI

Dokumentasi Minggu 3-6 tetap tersedia untuk menjelaskan perkembangan modul PMB dan KRS:

- [AI Usage Log pengembangan sebelumnya](AI_USAGE_LOG.md)
- [ADR-001: Validasi KRS](docs/ADR-001-krs-validation.md)
- [ADR-002: State machine dan transaksi KRS](docs/ADR-002-krs-state-transactions.md)
- [Laporan verifikasi Minggu 6](docs/VERIFIKASI_MINGGU6.md)

Kedua AI Usage Log dipisahkan untuk memudahkan penelusuran kontribusi AI pada setiap tahap pengembangan.

### Menjalankan Modul Minggu 7

Lihat [README_MINGGU7.md](README_MINGGU7.md) untuk langkah instalasi, migration, seed, dan endpoint API.


---

## Implementasi Minggu 8 — Observer, Outbox, KRS & Conflict Resolver

Minggu 8 melanjutkan seluruh modul Minggu 3–7 tanpa menghapus riwayat dokumentasinya. Perubahan jadwal disimpan secara atomik bersama invalidasi KRS terkait dan event outbox. Setelah commit, dispatcher mengirim notifikasi simulasi melalui tiga observer dan kanal Email/SMS/Push, dengan isolasi kegagalan dan deduplikasi receipt.

- **Observer:** `ScheduleSubject`, `StudentObserver`, `LecturerObserver`, `AdminObserver`.
- **Outbox:** migration `0006_schedule_observers`, `OutboxDispatcher`, `DeliveryReceipt`.
- **KRS:** aktor `sistem` menambahkan transisi `submitted/approved -> revision`; 48 kombinasi (6 legal, 42 ilegal).
- **Conflict Resolver:** UI admin, prompt AI Step 3, daftar slot deterministik, `saring_saran`, dan revalidasi saat apply.
- **Calendar:** endpoint `.ics` dengan UID stabil, SEQUENCE, dan RRULE mingguan.
- **Dokumentasi:** [README Minggu 8](README_MINGGU8.md), [sequence diagram](docs/SEQUENCE_OBSERVER_MINGGU8.md), [OPAR](docs/OPAR_MINGGU8.md), [AI Usage Log](AI_USAGE_LOG_MINGGU8.md), [PR template](.github/pull_request_template.md).

**Verifikasi lingkungan pembuatan paket:** 92 tes non-Hypothesis lulus, migrasi SQLite sampai `0006_schedule_observers` berhasil, dan `alembic check` tidak menemukan operasi baru. Pengujian properti Hypothesis lama belum dijalankan ulang karena paket tidak tersedia di lingkungan tersebut. Hasil pengujian Minggu 6 dan 7 di bagian sebelumnya merupakan riwayat pada saat itu, bukan hasil run terbaru Minggu 8.

---

# Tugas Minggu 9 — Modul Nilai (Bagian 1)

Proyek ini merupakan kelanjutan **Tugas Minggu 8**. Minggu 9 berfokus pada input nilai, IPS/IPK Decimal, dan audit perubahan. Transkrip PDF dikerjakan pada Minggu 10.

## Menjalankan

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
pytest -q
```

Buka `/docs` untuk API, atau `/nilai/form` untuk form demo.

**PENTING:** form/demo menggunakan `x-actor-role: dosen` dan `x-dosen-id` yang **dapat dipalsukan**. Jangan deploy sebagai sistem produksi atau memasukkan data mahasiswa nyata. Presensi default `PresensiStub()` sengaja menolak input bila belum ada data; untuk pengujian gunakan dependency override atau injeksi `PresensiStub({(nim, kelas_id): 75})`.

Endpoint: `PUT /api/kelas/{kelas_id}/nilai/{nim}`; `GET /api/nilai/{nim}/ips/{semester}`, `GET /api/nilai/{nim}/ipk`, `GET /api/nilai/{nim}/riwayat` (demo-header dosen). Huruf nilai dikirim sebagai string A, B, C, D, atau E. Bobot nilai menggunakan Decimal, sedangkan hasil IPS/IPK ditampilkan dengan dua angka desimal.

## Checklist

- [x] Migrasi Numeric dan grade_history (FK nilai dan lulus telah ada dari Minggu 8)
- [x] GradeService, otorisasi pengampu, presensi port/stub, API dan form demo
- [x] Pure IPS/IPK, NilaiRepo, GPACalculator, view riwayat
- [x] Pertanyaan stakeholder, ADR, AI Log, OPAR
- [ ] Konfirmasi stakeholder tentang D/C dan E/I
- [ ] Auth dosen sesungguhnya dan presensi nyata (modul mendatang)

Baca `docs/ADR-004-grade-policy.md` untuk keputusan sementara dan risiko.

## Hasil Verifikasi Terbaru

- Pengujian otomatis: **131 passed, 1 warning**.
- Migrasi Alembic: berhasil sampai `0007_grade_management (head)`.
- Struktur tabel dan SQL VIEW `v_grade_history`: terverifikasi.
- Pemeriksaan integritas foreign key: tidak ditemukan pelanggaran.
- Pengujian regresi: IPK memilih nilai tertinggi yang lulus untuk mata kuliah berulang.
- Catatan: warning berasal dari deprecation Starlette/httpx dan tidak menggagalkan pengujian.

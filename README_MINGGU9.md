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

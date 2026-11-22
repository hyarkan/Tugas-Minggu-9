# ADR-004 — Kebijakan Nilai dan Riwayat (Minggu 9)

## Status: keputusan sementara, menunggu stakeholder

**Pertanyaan untuk dosen/bagian akademik:** Dokumen menyebut “lulus jika nilai ≥ D (2.0)”, tetapi skala A=4, B=3, C=2, D=1, E/I=0. Apakah lulus minimal C (2.0) atau D (1.0)? Selain itu, dokumen menyebut huruf E, sementara video menyebut I. Huruf mana yang resmi digunakan dan bagaimana nilai belum lengkap diperlakukan?

**Asumsi sementara:** lulus minimal C, D dan E tidak lulus. Kolom `skala_nilai.lulus` menjadi sumber aturan (bukan hardcode). Seed proyek awal memakai E; I tidak ditambahkan tanpa konfirmasi. Data dummy saja.

- Nilai tetap di `krs_detail.nilai` (nullable FK yang sudah ada sejak Minggu 8), bukan tabel nilai kedua.
- `skala_nilai.bobot` menjadi NUMERIC(3,2), Python Decimal.
- IPS menghitung seluruh nilai terisi dalam semester termasuk tidak lulus.
- IPK menyaring nilai dengan `lulus=true` terlebih dahulu, kemudian memilih bobot tertinggi **per kode_mk** agar mata kuliah yang diulang tidak dihitung dua kali.
- IPS/IPK dihitung saat dibaca (tanpa cache), agar perubahan nilai otomatis tercermin.
- `grade_history` append-only melalui GradeService dalam **transaksi yang sama**; bukan trigger ganda. SQL manual di luar service **tidak otomatis diaudit**, sehingga perubahan manual harus dilarang secara operasional. SQLite `FOR UPDATE` tidak mengunci baris seperti PostgreSQL; multi-worker perlu kontrol konkurensi tambahan.
- Presensi menggunakan port dan stub fail-closed karena modul nyata baru Minggu 12. Tidak boleh mengasumsikan 100% presensi.
- Identitas dosen pada header hanya DEMO, **tidak aman untuk produksi**; perlu JWT/session terverifikasi.
- Minggu 10: transkrip PDF, predikat, acceptance multi-semester; di luar lingkup Minggu 9.

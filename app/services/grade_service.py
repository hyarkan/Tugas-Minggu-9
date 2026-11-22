"""Authorized, attendance-checked, transactional grade management."""
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import KRS, KRSDetail, SkalaNilai
from app.models.scheduling import Jadwal
from app.models.grades import GradeHistory

class GradeError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code

class PresensiPort(Protocol):
    def persentase(self, nim: str, kelas_id: int) -> float: ...

class PresensiStub:
    """Temporary adapter until attendance module arrives in Week 12.
    Fail closed when no attendance data exists; no fabricated attendance.
    """
    def __init__(self, values: dict[tuple[str, int], float] | None = None):
        self.values = values or {}
    def persentase(self, nim: str, kelas_id: int) -> float:
        if (nim, kelas_id) not in self.values:
            raise GradeError("Presensi belum tersedia; nilai tidak dapat diinput.", 409)
        value = self.values[(nim, kelas_id)]
        if not 0 <= value <= 100:
            raise GradeError("Data presensi tidak valid.", 409)
        return value

class GradeService:
    def __init__(self, db: Session, presensi: PresensiPort):
        self.db = db
        self.presensi = presensi

    def is_pengampu(self, kelas_id: int, dosen_id: int) -> bool:
        return self.db.scalar(select(Jadwal.id).where(Jadwal.kelas_id == kelas_id, Jadwal.dosen_id == dosen_id).limit(1)) is not None

    def input_nilai(self, *, dosen_id: int, kelas_id: int, nim: str, nilai: str, reason: str | None = None):
        if not self.is_pengampu(kelas_id, dosen_id):
            raise GradeError("Hanya dosen pengampu yang boleh mengisi nilai.", 403)
        detail = self.db.scalar(select(KRSDetail).join(KRS, KRS.id == KRSDetail.krs_id)
            .where(KRS.nim == nim, KRSDetail.kelas_id == kelas_id).with_for_update())
        if detail is None:
            raise GradeError("Peserta kelas tidak ditemukan.", 404)
        if self.presensi.persentase(nim, kelas_id) < 75:
            raise GradeError("Presensi kurang dari 75%.", 403)
        if self.db.get(SkalaNilai, nilai) is None:
            raise GradeError("Huruf nilai tidak tersedia dalam skala nilai.", 422)
        if detail.nilai == nilai:
            return {"nim": nim, "kelas_id": kelas_id, "nilai": nilai, "changed": False}
        if detail.nilai is not None and not (reason or "").strip():
            raise GradeError("Alasan wajib untuk perubahan nilai.", 422)
        old = detail.nilai
        try:
            detail.nilai = nilai
            self.db.add(GradeHistory(grade_id=detail.id, old_value=old, new_value=nilai,
                                     changed_by=dosen_id, reason=reason.strip() if reason else None))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"nim": nim, "kelas_id": kelas_id, "nilai": nilai, "changed": True}

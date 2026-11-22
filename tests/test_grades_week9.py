"""Week 9: 14 parametrized GPA cases + 3 Hypothesis properties + integration."""
from decimal import Decimal
import pytest
from hypothesis import given, strategies as st, settings
from app.services.gpa import Skala, NilaiRecord as R, hitung_ips, hitung_ipk
from app.services.grade_service import GradeService, GradeError, PresensiStub
from app.services.nilai_repo import NilaiRepo, GPACalculator
from app.models import KRS, KRSDetail, MataKuliah, SkalaNilai
from app.models.scheduling import Dosen, Kelas, Jadwal, Ruangan
from app.models.grades import GradeHistory
from datetime import time

S = {k: Skala(Decimal(str(n)), passed) for k, n, passed in [
    ("A", 4, True), ("B", 3, True), ("C", 2, True), ("D", 1, False), ("E", 0, False)]}
def r(k, sem, sks, grade): return R(k, sem, sks, grade)

@pytest.mark.parametrize('records,expected', [
    ([r('a','20241',3,'A')], '4.00'),
    ([], '0.00'),
    ([r('a','20241',3,'E')], '0.00'),
    ([r('a','20241',3,'D')], '0.00'),
    ([r('a','20241',3,'C')], '2.00'),
    ([r('a','20241',3,'E'),r('a','20242',3,'B')], '3.00'),
    ([r('a','20241',3,'A'),r('a','20242',3,'C')], '4.00'),
    ([r('a','20241',3,'A'),r('a','20242',3,'A')], '4.00'),
    ([r('a','20241',3,'A'),r('b','20241',3,'B')], '3.50'),
    ([r('a','20241',3,'A'),r('b','20241',1,'B')], '3.75'),
    ([r('a','20241',1,'A'),r('b','20241',2,'B')], '3.33'),
    ([r('a','20241',3,'D'),r('b','20241',3,'A')], '4.00'),
    ([r('a','20241',1,'C'),r('b','20241',3,'A')], '3.50'),
    ([r('a','20241',3,'C'),r('b','20241',3,'B'),r('c','20241',3,'A')], '3.00'),
])
def test_ipk_parametrized(records, expected):
    assert hitung_ipk(records, S) == Decimal(expected)

@pytest.mark.parametrize('records,semester,expected', [
    ([], '20241', '0.00'),
    ([r('a','20241',3,'E'),r('b','20241',3,'A')], '20241', '2.00'),
    ([r('a','20241',3,'A'),r('b','20242',3,'B')], '20241', '4.00'),
    ([r('a','20241',1,'C'),r('b','20241',2,'B')], '20241', '2.67'),
])
def test_ips_parametrized(records, semester, expected):
    assert hitung_ips(records, S, semester) == Decimal(expected)

def test_round_half_up_once():
    special = {'X':Skala(Decimal('3.125'), True)}
    assert hitung_ipk([r('x','20241',1,'X')], special) == Decimal('3.13')

def test_lulus_is_data():
    scale = dict(S)
    scale['D'] = Skala(Decimal('1'), True)
    assert hitung_ipk([r('a','20241',3,'D')], scale) == Decimal('1.00')

@given(st.lists(st.tuples(st.integers(min_value=1,max_value=4), st.sampled_from(list(S))), max_size=30))
def test_property_gpa_bounds(items):
    rows = [r(str(i),'20241',s,g) for i,(s,g) in enumerate(items)]
    assert Decimal('0') <= hitung_ipk(rows,S) <= Decimal('4')

@given(st.lists(st.tuples(st.integers(min_value=1,max_value=4), st.sampled_from(['A','B','C'])),max_size=30))
def test_property_adding_new_a_never_lowers_gpa(items):
    rows = [r(str(i),'20241',s,g) for i,(s,g) in enumerate(items)]
    assert hitung_ipk(rows+[r('new','20242',3,'A')],S) >= hitung_ipk(rows,S)

@given(st.lists(st.tuples(st.integers(min_value=0,max_value=7), st.sampled_from(list(S))), max_size=40))
def test_property_record_order_irrelevant(items):
    rows = [r(str(i),'20241',3,g) for i,g in items]
    assert hitung_ipk(rows,S) == hitung_ipk(list(reversed(rows)),S)

def setup_grade_data(db):
    db.add_all([SkalaNilai(nilai=k,bobot=v.bobot,lulus=v.lulus) for k,v in S.items()])
    db.add(MataKuliah(kode_mk='T901',nama='Demo',sks=3,hari=1,jam_mulai=time(8),jam_selesai=time(10)))
    db.add(Ruangan(kode='R901',kapasitas=30))
    db.add(Dosen(id=901,nidn='D901',nama='Dosen Demo'))
    db.add(Dosen(id=902,nidn='D902',nama='Dosen Lain'))
    db.flush()
    db.add(Kelas(id=901,kode_mk='T901',nama='A',kuota=30,semester='20241'))
    db.flush()
    db.add(Jadwal(kelas_id=901,hari=1,jam_mulai=time(8),jam_selesai=time(10),ruangan_kode='R901',dosen_id=901))
    # NIM belongs to a registered PMB applicant, fixture only uses dummy data.
    from app.models import CalonMahasiswa
    import inspect
    # The existing API registration flow creates the approved applicant below.
    # Construct via existing model fields to avoid any external API calls.
    db.add(CalonMahasiswa(nama_lengkap='Mahasiswa Dummy',email='dummy901@example.com',phone='081234567890',tanggal_lahir=__import__('datetime').date(2005,1,1),alamat='Dummy',program_studi_id=1,jalur_masuk_id=1,status='approve',nim='9010001'))
    db.flush()
    krs=KRS(nim='9010001',semester='20241',status='approved')
    db.add(krs);db.flush()
    detail=KRSDetail(krs_id=krs.id,kode_mk='T901',kelas_id=901)
    db.add(detail);db.commit()
    return detail.id

def test_grade_transaction_and_history(db_session):
    detail_id=setup_grade_data(db_session)
    svc=GradeService(db_session, PresensiStub({('9010001',901):75}))
    with pytest.raises(GradeError) as err:
        svc.input_nilai(dosen_id=902,kelas_id=901,nim='9010001',nilai='A')
    assert err.value.status_code==403
    assert svc.input_nilai(dosen_id=901,kelas_id=901,nim='9010001',nilai='B')['changed']
    assert GPACalculator(NilaiRepo(db_session)).calculate_ipk('9010001')==Decimal('3.00')
    assert not svc.input_nilai(dosen_id=901,kelas_id=901,nim='9010001',nilai='B')['changed']
    with pytest.raises(GradeError):
        svc.input_nilai(dosen_id=901,kelas_id=901,nim='9010001',nilai='A')
    svc.input_nilai(dosen_id=901,kelas_id=901,nim='9010001',nilai='A',reason='Koreksi penilaian')
    assert GPACalculator(NilaiRepo(db_session)).calculate_ipk('9010001')==Decimal('4.00')
    history=NilaiRepo(db_session).history('9010001')
    assert [(h['old_value'],h['new_value']) for h in history]==[(None,'B'),('B','A')]
    assert db_session.query(GradeHistory).filter_by(grade_id=detail_id).count()==2

def test_presensi_fail_closed(db_session):
    setup_grade_data(db_session)
    with pytest.raises(GradeError) as err:
        GradeService(db_session, PresensiStub()).input_nilai(dosen_id=901,kelas_id=901,nim='9010001',nilai='A')
    assert err.value.status_code == 409
    with pytest.raises(GradeError) as err:
        GradeService(db_session, PresensiStub({('9010001',901):74.99})).input_nilai(dosen_id=901,kelas_id=901,nim='9010001',nilai='A')
    assert err.value.status_code == 403


def test_ipk_memilih_nilai_tertinggi_yang_lulus():
    """Mata kuliah berulang harus memakai nilai tertinggi yang lulus."""
    skala = {
        "A": Skala(Decimal("4.00"), False),
        "B": Skala(Decimal("3.00"), True),
    }

    records = [
        R("MK001", "20241", 3, "A"),
        R("MK001", "20242", 3, "B"),
    ]

    assert hitung_ipk(records, skala) == Decimal("3.00")

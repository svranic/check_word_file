"""Batch provjera (priča 4.1): obilazak mape, otisak, validacija i otpornost."""

import json
import socket
import string
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from alati.generator import ispravan

from provjera.adapteri import batch
from provjera.adapteri.popis import ZONA, Student, zapisi_izdano
from provjera.jezgra import naziv, profil
from provjera.jezgra.nalaz import KontekstProvjere, NacinUparivanja, Status
from provjera.jezgra.predaje import opis_razloga
from provjera.jezgra.provjera import UkupniStatus, provjeri

KORIJEN = Path(__file__).resolve().parents[1]
PROFIL = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())


def _prezime(i: int) -> str:
    """Prezimena samo od slova: znamenke se iz kanonskog naziva izbacuju."""
    slova = string.ascii_lowercase
    return "Test" + slova[i // 26] + slova[i % 26]


def _studenti(broj: int) -> tuple[Student, ...]:
    return tuple(
        Student(rbr=r, jmbag=f"{9900000000 + r}", ime="Ana", prezime=_prezime(r), aktivan=True)
        for r in range(1, broj + 1)
    )


def _naziv(s: Student) -> str:
    return naziv.kanonski(s.ime, s.prezime, PROFIL)


def _predaj(mapa: Path, student: Student, relativno: str | None = None, sadrzaj: bytes | None = None) -> Path:
    putanja = mapa / (relativno or _naziv(student))
    putanja.parent.mkdir(parents=True, exist_ok=True)
    putanja.write_bytes(ispravan(student.rbr, PROFIL) if sadrzaj is None else sadrzaj)
    return putanja


def test_sretan_put_s_podmapom_i_napretkom(tmp_path):
    studenti = _studenti(3)
    _predaj(tmp_path, studenti[0])
    _predaj(tmp_path, studenti[1])
    _predaj(tmp_path, studenti[2], f"podmapa/{_naziv(studenti[2])}")
    koraci = []
    rezultat = batch.pokreni(tmp_path, PROFIL, studenti, lambda i, n: koraci.append((i, n)))
    assert koraci == [(1, 3), (2, 3), (3, 3)]
    assert [d.status for d in rezultat.datoteke] == [UkupniStatus.SPREMNO] * 3
    assert {d.student for d in rezultat.datoteke} == set(studenti)
    assert all(d.nacin is NacinUparivanja.TOCAN for d in rezultat.datoteke)
    assert rezultat.datoteke[2].relativno == f"podmapa/{_naziv(studenti[2])}"
    assert rezultat.profil_verzija == profil.verzija(PROFIL)
    assert [rezultat.status_studenta(s) for s in studenti] == [UkupniStatus.SPREMNO] * 3


def _sakrij(putanja: Path) -> None:
    import ctypes

    assert ctypes.windll.kernel32.SetFileAttributesW(str(putanja), 2)  # FILE_ATTRIBUTE_HIDDEN


def test_preskace_privremene_skrivene_i_sistemske(tmp_path):
    (tmp_path / "rad.docx").write_bytes(b"x")
    for ime in ("~$rad.docx", ".skriveno.docx", "Thumbs.db", "DESKTOP.INI", "desktop.ini"):
        (tmp_path / "podmapa").mkdir(exist_ok=True)
        (tmp_path / "podmapa" / ime).write_bytes(b"x")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "rad.docx").write_bytes(b"x")
    if sys.platform == "win32":
        skrivena = tmp_path / "skrivena.docx"
        skrivena.write_bytes(b"x")
        _sakrij(skrivena)
        mapa = tmp_path / "skrivena_mapa"
        mapa.mkdir()
        (mapa / "rad.docx").write_bytes(b"x")
        _sakrij(mapa)
    assert batch.pronadi_datoteke(tmp_path) == (tmp_path / "rad.docx",)


def test_izuzeta_podatkovna_mapa(tmp_path):
    (tmp_path / "rad.docx").write_bytes(b"x")
    podaci = tmp_path / "ProvjeraWord" / "vjezba_1"
    podaci.mkdir(parents=True)
    (podaci / "popis.csv").write_bytes(b"x")
    assert batch.pronadi_datoteke(tmp_path, izuzeto=podaci) == (tmp_path / "rad.docx",)


def test_sortirano_po_relativnoj_putanji(tmp_path):
    for ime in ("b.docx", "a/z.docx", "a.docx"):
        (tmp_path / ime).parent.mkdir(exist_ok=True)
        (tmp_path / ime).write_bytes(b"x")
    relativno = [p.relative_to(tmp_path).as_posix() for p in batch.pronadi_datoteke(tmp_path)]
    assert relativno == ["a/z.docx", "a.docx", "b.docx"]


@pytest.mark.parametrize(
    ("priprema", "ocekivano"),
    [
        (None, batch.StanjeOtiska.NEMA_IZDANOG),
        ("isti", batch.StanjeOtiska.ISTI),
        ("drugi", batch.StanjeOtiska.RAZLICIT),
        ("smece", batch.StanjeOtiska.NECITLJIVO),
    ],
)
def test_stanje_otiska(tmp_path, priprema, ocekivano):
    if priprema is not None:
        zapisi_izdano(tmp_path, PROFIL, datetime(2026, 10, 1, 12, 0, tzinfo=ZONA))
    izdano = tmp_path / "izdano.json"
    if priprema == "drugi":
        podaci = json.loads(izdano.read_text(encoding="utf-8"))
        podaci["formula_otisak"] = "000000000000"
        izdano.write_text(json.dumps(podaci), encoding="utf-8")
    elif priprema == "smece":
        izdano.write_bytes(b"{")
    assert batch.stanje_otiska(PROFIL, tmp_path) is ocekivano


def test_problemi_konfiguracije():
    assert [p.kljuc for p in batch.problemi_konfiguracije(PROFIL, None)] == ["spremnost.nema_popisa"]
    neaktivni = tuple(
        Student(s.rbr, s.jmbag, s.ime, s.prezime, aktivan=False) for s in _studenti(2)
    )
    assert [p.kljuc for p in batch.problemi_konfiguracije(PROFIL, neaktivni)] == [
        "spremnost.nema_aktivnih"
    ]
    # Samoprovjera nije uvjet za batch (odluka 2026-10-15).
    assert batch.problemi_konfiguracije(PROFIL, _studenti(3)) == ()


def test_ostecena_datoteka_ne_zaustavlja_ostale(tmp_path):
    studenti = _studenti(2)
    _predaj(tmp_path, studenti[0], sadrzaj=b"PK\x03\x04smece")
    _predaj(tmp_path, studenti[1])
    rezultat = batch.pokreni(tmp_path, PROFIL, studenti)
    po_studentu = {d.student: d for d in rezultat.datoteke}
    pokvarena = po_studentu[studenti[0]]
    assert pokvarena.status is UkupniStatus.NEUSPJELA_OBRADA
    assert opis_razloga(pokvarena) == "datoteka je oštećena"
    assert po_studentu[studenti[1]].status is UkupniStatus.SPREMNO


def test_iznimka_ne_zaustavlja_ostale(tmp_path, monkeypatch):
    studenti = _studenti(3)
    for s in studenti:
        _predaj(tmp_path, s)
    pravi = batch.provjeri

    def provjeri_s_greskom(docx, p, kontekst):
        if kontekst.rbr == 2:
            raise RuntimeError("puklo")
        return pravi(docx, p, kontekst)

    monkeypatch.setattr(batch, "provjeri", provjeri_s_greskom)
    rezultat = batch.pokreni(tmp_path, PROFIL, studenti)
    statusi = [d.status for d in rezultat.datoteke]
    assert statusi == [UkupniStatus.SPREMNO, UkupniStatus.NEUSPJELA_OBRADA, UkupniStatus.SPREMNO]
    assert rezultat.datoteke[1].greska == "RuntimeError"
    assert opis_razloga(rezultat.datoteke[1]) == "neočekivana greška pri obradi (RuntimeError)"


def test_necitljiva_datoteka_ne_zaustavlja_ostale(tmp_path, monkeypatch):
    studenti = _studenti(2)
    for s in studenti:
        _predaj(tmp_path, s)
    pravi = batch._procitaj

    def procitaj(putanja):
        if putanja.name == _naziv(studenti[0]):
            raise PermissionError("zaključano")
        return pravi(putanja)

    monkeypatch.setattr(batch, "_procitaj", procitaj)
    statusi = [d.status for d in batch.pokreni(tmp_path, PROFIL, studenti).datoteke]
    assert statusi == [UkupniStatus.NEUSPJELA_OBRADA, UkupniStatus.SPREMNO]


def test_doc_s_tocnim_nazivom_je_neispravan_format(tmp_path):
    student = _studenti(1)[0]
    _predaj(tmp_path, student, _naziv(student).removesuffix(".docx") + ".doc", b"\xd0\xcf\x11\xe0")
    (redak,) = batch.pokreni(tmp_path, PROFIL, (student,)).datoteke
    assert redak.student == student
    assert redak.status is UkupniStatus.NEISPRAVAN_FORMAT


def test_prevelika_datoteka_se_ne_cita_cijela(tmp_path, monkeypatch):
    monkeypatch.setattr(batch.ulaz, "NAJVECA_VELICINA", 1000)
    student = _studenti(1)[0]
    _predaj(tmp_path, student, sadrzaj=b"PK\x03\x04" + b"0" * 5000)
    procitano = []
    pravi = batch.provjeri
    monkeypatch.setattr(
        batch, "provjeri", lambda d, p, k: procitano.append(len(d)) or pravi(d, p, k)
    )
    (redak,) = batch.pokreni(tmp_path, PROFIL, (student,)).datoteke
    assert procitano == [1001]
    assert opis_razloga(redak) == "datoteka je veća od dopuštene"


def test_nepovezana_datoteka_se_ne_provjerava(tmp_path, monkeypatch):
    (tmp_path / "nesto.docx").write_bytes(b"x")
    monkeypatch.setattr(batch, "provjeri", lambda *a: pytest.fail("ne smije se provjeriti"))
    (redak,) = batch.pokreni(tmp_path, PROFIL, _studenti(1)).datoteke
    assert redak.student is None and redak.status is None
    assert opis_razloga(redak) == "datoteka nije povezana ni s jednim studentom"


def test_nalazi_jednaki_web_provjeri_osim_naziva(tmp_path):
    student = _studenti(1)[0]
    sadrzaj = _predaj(tmp_path, student).read_bytes()
    (redak,) = batch.pokreni(tmp_path, PROFIL, (student,)).datoteke
    web = provjeri(sadrzaj, PROFIL, KontekstProvjere(_naziv(student), student.rbr, None, None))
    bez_naziva = lambda nalazi: [n for n in nalazi if n.pravilo_id != "R-NAZIV"]  # noqa: E731
    assert bez_naziva(redak.izvjestaj.nalazi) == bez_naziva(web.nalazi)
    (naziv_nalaz,) = [n for n in redak.izvjestaj.nalazi if n.pravilo_id == "R-NAZIV"]
    assert naziv_nalaz.status is Status.PROSLO


def test_80_dokumenata_brzo_i_bez_mreze(tmp_path, monkeypatch):
    studenti = _studenti(80)
    sadrzaj = ispravan(1, PROFIL)
    for s in studenti:
        _predaj(tmp_path, s, sadrzaj=sadrzaj)

    def zabranjeno(*_a, **_k):
        raise AssertionError("batch ne smije koristiti mrežu")

    monkeypatch.setattr(socket, "socket", zabranjeno)
    monkeypatch.setattr(socket, "create_connection", zabranjeno)
    pocetak = time.perf_counter()
    rezultat = batch.pokreni(tmp_path, PROFIL, studenti)
    assert time.perf_counter() - pocetak < 120
    assert len(rezultat.datoteke) == 80
    assert all(d.izvjestaj is not None for d in rezultat.datoteke)


def test_svaki_razlog_odbijanja_ima_kratak_opis():
    from provjera.jezgra.poruke import KATALOG
    from provjera.jezgra.ulaz import RazlogOdbijanja

    for razlog in RazlogOdbijanja:
        assert f"batch.odbijeno.{razlog.value}" in KATALOG


def test_isti_naziv_dva_studenta_ostaje_nepovezan(tmp_path):
    studenti = (
        Student(1, "9900000001", "Ana", "Horvat", True),
        Student(2, "9900000002", "Ana", "Horvat", True),
    )
    _predaj(tmp_path, studenti[0])
    (redak,) = batch.pokreni(tmp_path, PROFIL, studenti).datoteke
    assert redak.student is None
    assert opis_razloga(redak) == "datoteka nije povezana ni s jednim studentom"


def test_necitljiva_podmapa_baca_oserror(tmp_path, monkeypatch):
    (tmp_path / "podmapa").mkdir()
    pravi = batch.os.scandir

    def scandir(putanja):
        if Path(putanja).name == "podmapa":
            raise PermissionError("zaključano")
        return pravi(putanja)

    monkeypatch.setattr(batch.os, "scandir", scandir)
    with pytest.raises(OSError):
        batch.pronadi_datoteke(tmp_path)


def test_izuzeta_mapa_kao_korijen_nema_datoteka(tmp_path):
    (tmp_path / "popis.csv").write_bytes(b"x")
    assert batch.pronadi_datoteke(tmp_path, izuzeto=tmp_path) == ()
    assert batch.pronadi_datoteke(tmp_path, izuzeto=tmp_path.parent) == ()


def test_preskace_poveznice_i_junctione(tmp_path):
    vani = tmp_path / "vani"
    vani.mkdir()
    (vani / "tudi.docx").write_bytes(b"x")
    mapa = tmp_path / "predaje"
    mapa.mkdir()
    (mapa / "rad.docx").write_bytes(b"x")
    if sys.platform == "win32":
        import subprocess

        subprocess.run(["cmd", "/c", "mklink", "/J", str(mapa / "spoj"), str(vani)], check=True,
                       capture_output=True)
    try:
        (mapa / "poveznica").symlink_to(vani, target_is_directory=True)
    except OSError:
        pass  # Windows bez prava za simboličke poveznice
    assert batch.pronadi_datoteke(mapa) == (mapa / "rad.docx",)


def test_greska_atributa_ne_zaustavlja_obilazak(tmp_path, monkeypatch):
    (tmp_path / "rad.docx").write_bytes(b"x")

    class Unos:
        name = "rad.docx"
        path = str(tmp_path / "rad.docx")

        def is_symlink(self):
            return False

        def is_junction(self):
            return False

        def stat(self, follow_symlinks=True):
            raise FileNotFoundError

    assert batch._preskace_se(Unos()) is False

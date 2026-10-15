"""Povezivanje datoteke sa studentom (priča 4.2, FR26)."""

from pathlib import Path

import pytest
from alati.generator import ispravan

from provjera.adapteri import batch
from provjera.adapteri.popis import Student
from provjera.jezgra import model, naziv, profil
from provjera.jezgra.nalaz import NacinUparivanja, Status
from provjera.jezgra.predaje import opis_kandidata, opis_nacina, opis_razloga
from provjera.jezgra.provjera import UkupniStatus
from provjera.jezgra.uparivanje import (
    Nepovezano,
    RazlogNepovezanosti,
    Uparivanje,
    razrijesi_visestruke,
    upari,
)

KORIJEN = Path(__file__).resolve().parents[1]
PROFIL = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())

ANA = Student(1, "0012345678", "Ana", "Horvat", True)
SASA = Student(2, "0023456789", "Ivan", "Šašić", True)
DORDE = Student(3, "0034567890", "Đorđe", "Kovač", True)
IVAN_1 = Student(4, "0045678901", "Ivan", "Babić", True)
IVAN_2 = Student(5, "0056789012", "Ivan", "Babić", True)
ISPISAN = Student(6, "0067890123", "Petra", "Marić", False)
OLE = bytes.fromhex("d0cf11e0a1b11ae1")
STUDENTI = (ANA, SASA, DORDE, IVAN_1, IVAN_2, ISPISAN)


def _upari(naziv_datoteke, mape=(), brojevi=frozenset(), studenti=STUDENTI):
    pozvano = []

    def citaj():
        pozvano.append(True)
        return frozenset(brojevi)

    return upari(naziv_datoteke, list(mape), studenti, PROFIL, citaj), bool(pozvano)


# --- Koraci ---------------------------------------------------------------------


def test_tocan_naziv():
    (rezultat, citano) = _upari("Ana_Horvat_GiG_OG_Vjezba_1.docx")
    assert rezultat == Uparivanje(ANA, NacinUparivanja.TOCAN, "Ana_Horvat_GiG_OG_Vjezba_1.docx")
    assert not citano  # naslovnica se ne čita kad naziv odlučuje


def test_priblizan_naziv():
    (rezultat, _) = _upari("ana_horvat_gig_og_vjezba_1 (1).docx")
    assert (rezultat.student, rezultat.nacin) == (ANA, NacinUparivanja.PRIBLIZAN)


@pytest.mark.parametrize(
    ("datoteka", "student"),
    [("Ivan_Sasic_GiG_OG_Vjezba_1.docx", SASA), ("Dorde_Kovac_GiG_OG_Vjezba_1.docx", DORDE)],
)
def test_dijakritici(datoteka, student):
    (rezultat, _) = _upari(datoteka)
    assert (rezultat.student, rezultat.nacin) == (student, NacinUparivanja.PRIBLIZAN)


def test_podmapa():
    (rezultat, _) = _upari("rad.docx", ["Ana Horvat_123_assignsubmission_file_"])
    assert (rezultat.student, rezultat.nacin) == (ANA, NacinUparivanja.PODMAPA)


def test_najbliza_podmapa_odlucuje():
    (rezultat, _) = _upari("rad.docx", ["Ana Horvat", "Ivan Šašić_77"])
    assert rezultat.student == SASA


def test_podmapa_trazi_cijele_rijeci():
    (rezultat, _) = _upari("rad.docx", ["Anabela Horvatić"])
    assert rezultat == Nepovezano(RazlogNepovezanosti.BEZ_PODUDARANJA)


def test_jmbag_s_naslovnice():
    (rezultat, citano) = _upari("rad.docx", brojevi={ANA.jmbag, "1111111111"})
    assert (rezultat.student, rezultat.nacin) == (ANA, NacinUparivanja.JMBAG)
    assert citano


def test_jmbag_nije_na_popisu():
    (rezultat, _) = _upari("rad.docx", brojevi={"1111111111"})
    assert rezultat == Nepovezano(RazlogNepovezanosti.JMBAG_NIJE_NA_POPISU)


def test_vise_jmbagova():
    (rezultat, _) = _upari("rad.docx", brojevi={ANA.jmbag, SASA.jmbag})
    assert rezultat.razlog is RazlogNepovezanosti.VISE_JMBAGOVA
    assert set(rezultat.kandidati) == {ANA, SASA}


def test_kolizija_razlucuje_jmbag():
    (rezultat, _) = _upari("Ivan_Babic_GiG_OG_Vjezba_1.docx", brojevi={IVAN_2.jmbag})
    assert (rezultat.student, rezultat.nacin) == (IVAN_2, NacinUparivanja.JMBAG)


def test_kolizija_tocnog_naziva_razlucuje_jmbag():
    (rezultat, _) = _upari("Ivan_Babić_GiG_OG_Vjezba_1.docx", brojevi={IVAN_1.jmbag})
    assert (rezultat.student, rezultat.nacin) == (IVAN_1, NacinUparivanja.JMBAG)


def test_kolizija_bez_jmbaga_je_dvosmislena():
    # JMBAG drugog studenta ne razlučuje kandidate.
    (rezultat, _) = _upari("Ivan_Babić_GiG_OG_Vjezba_1.docx", brojevi={ANA.jmbag})
    assert rezultat == Nepovezano(RazlogNepovezanosti.DVOSMISLENO, (IVAN_1, IVAN_2))


def test_kolizija_u_podmapi_je_dvosmislena():
    (rezultat, _) = _upari("rad.docx", ["Ivan Babić"])
    assert rezultat == Nepovezano(RazlogNepovezanosti.DVOSMISLENO, (IVAN_1, IVAN_2))


def test_bez_podudaranja():
    (rezultat, _) = _upari("nesto.docx")
    assert rezultat == Nepovezano(RazlogNepovezanosti.BEZ_PODUDARANJA)


def test_neaktivan_student():
    (rezultat, _) = _upari("Petra_Marić_GiG_OG_Vjezba_1.docx")
    assert rezultat == Nepovezano(RazlogNepovezanosti.NEAKTIVAN, (ISPISAN,))


def test_visestruke_ostaje_najbolja():
    tocna = Uparivanje(ANA, NacinUparivanja.TOCAN, "x")
    priblizna = Uparivanje(ANA, NacinUparivanja.PRIBLIZAN, "x")
    druga = Uparivanje(SASA, NacinUparivanja.JMBAG, "y")
    druga_jmbag = Uparivanje(SASA, NacinUparivanja.JMBAG, "y")
    assert razrijesi_visestruke([priblizna, druga, tocna, druga_jmbag]) == [
        Nepovezano(RazlogNepovezanosti.VISESTRUKO, (ANA,)),
        druga,
        tocna,
        Nepovezano(RazlogNepovezanosti.VISESTRUKO, (SASA,)),
    ]


# --- Naslovnica -------------------------------------------------------------------


def test_brojevi_naslovnice():
    docx = ispravan(1, PROFIL, naslovnica="Ana Horvat, JMBAG 0012345678, tel. 01234567890, 1111111111")
    assert model.brojevi_naslovnice(docx, PROFIL.uloge) == {"0012345678", "1111111111"}


def test_brojevi_naslovnice_neparsiv_dokument():
    assert model.brojevi_naslovnice(b"PK\x03\x04smece", PROFIL.uloge) == frozenset()


# --- Kroz batch ----------------------------------------------------------------------


def _pokreni(mapa: Path, studenti=STUDENTI):
    rezultat = batch.pokreni(mapa, PROFIL, studenti)
    return {d.relativno: d for d in rezultat.datoteke}


def _naziv_nalaz(redak):
    (nalaz,) = [n for n in redak.izvjestaj.nalazi if n.pravilo_id == "R-NAZIV"]
    return nalaz


def test_batch_koraci_i_r_naziv(tmp_path):
    (tmp_path / "Ana_Horvat_GiG_OG_Vjezba_1.docx").write_bytes(ispravan(1, PROFIL))
    (tmp_path / "ivan_sasic_gig_og_vjezba_1 (1).docx").write_bytes(ispravan(2, PROFIL))
    podmapa = tmp_path / "Đorđe Kovač_99_assignsubmission_file_"
    podmapa.mkdir()
    (podmapa / "rad.docx").write_bytes(ispravan(3, PROFIL))
    (tmp_path / "zadnji.docx").write_bytes(ispravan(5, PROFIL, naslovnica=f"Ivan Babić {IVAN_2.jmbag}"))
    retci = _pokreni(tmp_path)
    tocna = retci["Ana_Horvat_GiG_OG_Vjezba_1.docx"]
    assert (tocna.student, tocna.nacin, tocna.status) == (ANA, NacinUparivanja.TOCAN, UkupniStatus.SPREMNO)
    for relativno, student, nacin in (
        ("ivan_sasic_gig_og_vjezba_1 (1).docx", SASA, NacinUparivanja.PRIBLIZAN),
        (f"{podmapa.name}/rad.docx", DORDE, NacinUparivanja.PODMAPA),
        ("zadnji.docx", IVAN_2, NacinUparivanja.JMBAG),
    ):
        redak = retci[relativno]
        assert (redak.student, redak.nacin) == (student, nacin)
        assert _naziv_nalaz(redak).status is Status.NE_PROLAZI
        assert redak.status is UkupniStatus.NIJE_SPREMNO
        assert all(n.status is Status.PROSLO for n in redak.izvjestaj.nalazi if n.pravilo_id != "R-NAZIV")


def test_batch_format_i_nepovezano(tmp_path):
    (tmp_path / "Ana_Horvat_GiG_OG_Vjezba_1.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "nesto.docx").write_bytes(ispravan(1, PROFIL, naslovnica="bez broja"))
    (tmp_path / "Ivan_Babić_GiG_OG_Vjezba_1.docx").write_bytes(ispravan(4, PROFIL, naslovnica="bez broja"))
    retci = _pokreni(tmp_path)
    pdf = retci["Ana_Horvat_GiG_OG_Vjezba_1.pdf"]
    assert (pdf.student, pdf.status) == (ANA, UkupniStatus.NEISPRAVAN_FORMAT)
    nesto = retci["nesto.docx"]
    assert nesto.student is None and nesto.nepovezano is RazlogNepovezanosti.BEZ_PODUDARANJA
    dvosmisleno = retci["Ivan_Babić_GiG_OG_Vjezba_1.docx"]
    assert opis_razloga(dvosmisleno) == "dvosmisleno – datoteka odgovara više studenata, a JMBAG ih ne razlučuje"
    assert opis_kandidata(dvosmisleno) == "4. Ivan Babić; 5. Ivan Babić"


def test_batch_dvije_datoteke_istog_studenta(tmp_path):
    (tmp_path / "ana_horvat_gig_og_vjezba_1 (1).docx").write_bytes(ispravan(1, PROFIL))
    (tmp_path / "Ana_Horvat_GiG_OG_Vjezba_1.docx").write_bytes(ispravan(1, PROFIL))
    rezultat = batch.pokreni(tmp_path, PROFIL, STUDENTI)
    retci = {d.relativno: d for d in rezultat.datoteke}
    assert retci["Ana_Horvat_GiG_OG_Vjezba_1.docx"].nacin is NacinUparivanja.TOCAN
    visestruka = retci["ana_horvat_gig_og_vjezba_1 (1).docx"]
    assert (visestruka.student, visestruka.nepovezano) == (None, RazlogNepovezanosti.VISESTRUKO)
    assert visestruka.kandidati == (ANA,)
    assert visestruka.izvjestaj is None
    assert rezultat.status_studenta(ANA) is UkupniStatus.SPREMNO


def test_batch_neaktivan_se_ne_provjerava(tmp_path, monkeypatch):
    (tmp_path / "Petra_Marić_GiG_OG_Vjezba_1.docx").write_bytes(ispravan(6, PROFIL))
    monkeypatch.setattr(batch, "provjeri", lambda *a: pytest.fail("ne smije se provjeriti"))
    (redak,) = batch.pokreni(tmp_path, PROFIL, STUDENTI).datoteke
    assert redak.nepovezano is RazlogNepovezanosti.NEAKTIVAN


def test_podmapa_prednost_ima_dulje_ime():
    marija = Student(7, "0078901234", "Ana Marija", "Horvat", True)
    (rezultat, _) = _upari("rad.docx", ["Ana Marija Horvat_1"], studenti=(ANA, marija))
    assert (rezultat.student, rezultat.nacin) == (marija, NacinUparivanja.PODMAPA)


def test_visestruke_prednost_ima_docx():
    pdf = Uparivanje(ANA, NacinUparivanja.TOCAN, "x")
    docx = Uparivanje(ANA, NacinUparivanja.PRIBLIZAN, "x")
    assert razrijesi_visestruke([pdf, docx], [False, True]) == [
        Nepovezano(RazlogNepovezanosti.VISESTRUKO, (ANA,)),
        docx,
    ]


def test_brojevi_naslovnice_samo_ascii_znamenke():
    docx = ispravan(1, PROFIL, naslovnica="Ana Horvat " + "".join(chr(0xFF10 + i) for i in range(10)))
    assert model.brojevi_naslovnice(docx, PROFIL.uloge) == frozenset()


def test_batch_najbliza_podmapa(tmp_path):
    mapa = tmp_path / "Ana Horvat" / "Ivan Šašić_77"
    mapa.mkdir(parents=True)
    (mapa / "rad.docx").write_bytes(ispravan(2, PROFIL))
    (redak,) = _pokreni(tmp_path).values()
    assert (redak.student, redak.nacin) == (SASA, NacinUparivanja.PODMAPA)
    assert opis_nacina(redak) == "imenu podmape"


def test_batch_necitljiva_nepovezana_ne_zaustavlja_ostale(tmp_path, monkeypatch):
    (tmp_path / "rad.docx").write_bytes(ispravan(1, PROFIL))
    (tmp_path / "Ivan_Šašić_GiG_OG_Vjezba_1.docx").write_bytes(ispravan(2, PROFIL))
    pravi = batch._procitaj

    def procitaj(putanja):
        if putanja.name == "rad.docx":
            raise PermissionError("zaključano")
        return pravi(putanja)

    monkeypatch.setattr(batch, "_procitaj", procitaj)
    retci = _pokreni(tmp_path)
    assert retci["rad.docx"].nepovezano is RazlogNepovezanosti.BEZ_PODUDARANJA
    assert retci["Ivan_Šašić_GiG_OG_Vjezba_1.docx"].status is UkupniStatus.SPREMNO


def test_batch_nesigurna_datoteka_ne_cita_naslovnicu(tmp_path, monkeypatch):
    (tmp_path / "rad.docx").write_bytes(OLE + b"0" * 100)  # OLE: odbija ulaz
    (tmp_path / "rad.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(batch.model, "brojevi_naslovnice", lambda *a: pytest.fail("ne smije parsirati"))
    retci = _pokreni(tmp_path)
    assert {r.nepovezano for r in retci.values()} == {RazlogNepovezanosti.BEZ_PODUDARANJA}

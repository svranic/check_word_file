"""Fiksne margine: iste margine tijela za sve studente, bez unosa Rbr. na webu."""

import io
import re
from pathlib import Path

import pytest
from alati.generator import ispravan
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from provjera.word.adapteri import batch
from provjera.word.adapteri.pdf_svojstva import izradi_pdf
from provjera.word.adapteri.popis import Student
from provjera.word.jezgra import formula, jedinice, profil, spremnost, svojstva
from provjera.zajednicko import naziv
from provjera.word.jezgra.jedinice import Jedinica
from provjera.word.jezgra.nalaz import KontekstProvjere, Status
from provjera.word.jezgra.poruke import formatiraj, poruka
from provjera.word.jezgra.provjera import UkupniStatus, provjeri
from provjera.word.jezgra.samoprovjera import usporedi
from provjera.word.jezgra.sazetak import html_sazetka

KORIJEN = Path(__file__).resolve().parents[2]
VJEZBA_1 = KORIJEN / "tests" / "word" / "fixtures" / "vjezba_1_baseline.toml"
STUDENT = str(KORIJEN / "apps" / "student.py")
NASTAVNIK = str(KORIJEN / "apps" / "nastavnik.py")
# Zamrznuta kopija profila Vježbe 1 iz commita b1e4d52 (prije uvođenja zastavice).
BASELINE = KORIJEN / "tests" / "word" / "fixtures" / "vjezba_1_baseline.toml"
# Otisak i verzija baseline profila izračunati prije uvođenja zastavice.
OTISAK_BASELINE = "888f585e36ac"
VERZIJA_BASELINE = "fbefd03e"
STRANE = ("gore", "dolje", "lijevo", "desno")
PROLAZ = (usporedi("ispravan", set(), set(), {"R-MARGINE"}),)


def _toml_fiksni(minimalan: bool = True) -> bytes:
    """Vježba 1 s ``fiksne_margine = true``; minimalan bez ``raspon``/``korak``/``sjeme``."""
    tekst = VJEZBA_1.read_text(encoding="utf-8")
    if minimalan:
        for kljuc in ("raspon", "korak", "sjeme"):
            tekst, broj = re.subn(rf"(?m)^{kljuc} = .*\n", "", tekst)
            assert broj == 1, kljuc
    tekst, broj = re.subn(r"(?m)^\[formula\]\n", "[formula]\nfiksne_margine = true\n", tekst)
    assert broj == 1
    return tekst.encode("utf-8")


@pytest.fixture(scope="module")
def vjezba() -> profil.Profil:
    return profil.ucitaj(VJEZBA_1.read_bytes())


@pytest.fixture(scope="module")
def fiksni() -> profil.Profil:
    return profil.ucitaj(_toml_fiksni())


def _osnovice(p: profil.Profil) -> formula.Margine:
    f = p.formula
    return formula.Margine(f.osnovica_gore, f.osnovica_dolje, f.osnovica_lijevo, f.osnovica_desno)


# --- Formula i profil --------------------------------------------------------


def test_baseline_ima_isti_otisak_i_verziju():
    baseline = profil.ucitaj(BASELINE.read_bytes())
    assert not baseline.formula.fiksne_margine
    assert formula.otisak(baseline.formula) == OTISAK_BASELINE
    assert profil.verzija(baseline) == VERZIJA_BASELINE
    assert "fiksne_margine" not in baseline.formula.model_dump(mode="json")


def test_izricito_false_ne_mijenja_otisak_ni_verziju(vjezba):
    tekst = VJEZBA_1.read_text(encoding="utf-8").replace(
        "[formula]\n", "[formula]\nfiksne_margine = false\n", 1
    )
    izricito = profil.ucitaj(tekst.encode("utf-8"))
    assert formula.otisak(izricito.formula) == formula.otisak(vjezba.formula)
    assert profil.verzija(izricito) == profil.verzija(vjezba)


def test_fiksne_mijenjaju_otisak(vjezba):
    puni = profil.ucitaj(_toml_fiksni(minimalan=False))
    assert formula.otisak(puni.formula) != formula.otisak(vjezba.formula)
    assert profil.verzija(puni) != profil.verzija(vjezba)


def test_fiksni_otisak_ne_ovisi_o_nekoristenom_sjemenu():
    a = profil.ucitaj(_toml_fiksni(minimalan=False))
    tekst = _toml_fiksni(minimalan=False).decode("utf-8").replace("sjeme = 20261012", "sjeme = 1")
    b = profil.ucitaj(tekst.encode("utf-8"))
    assert a.formula.sjeme != b.formula.sjeme
    assert formula.otisak(a.formula) == formula.otisak(b.formula)
    assert profil.verzija(a) == profil.verzija(b)
    minimalan = profil.ucitaj(_toml_fiksni())
    assert formula.otisak(minimalan.formula) == formula.otisak(a.formula)


def test_minimalan_fiksni_profil_se_ucitava(fiksni):
    f = fiksni.formula
    assert f.fiksne_margine
    assert (f.raspon, f.korak, f.sjeme) == (None, None, None)
    assert "raspon" not in f.model_dump(mode="json")


@pytest.mark.parametrize("rbr", [None, 1, 54, 10**6])
def test_margine_uz_fiksne_su_osnovice(fiksni, rbr):
    assert formula.margine(rbr, fiksni.formula) == _osnovice(fiksni)


def test_najveci_rbr_uz_fiksne_ne_gradi_tablicu(fiksni, monkeypatch):
    monkeypatch.setattr(formula, "_dopustene", lambda _p: pytest.fail("_dopustene pozvan"))
    assert formula.najveci_rbr(fiksni.formula) is None
    formula.margine(None, fiksni.formula)


def test_individualne_bez_rbr_bacaju(vjezba):
    with pytest.raises(ValueError):
        formula.margine(None, vjezba.formula)


@pytest.mark.parametrize("kljuc", ["raspon", "korak", "sjeme"])
def test_individualne_traze_raspon_korak_i_sjeme(kljuc):
    tekst, broj = re.subn(rf"(?m)^{kljuc} = .*\n", "", VJEZBA_1.read_text(encoding="utf-8"))
    assert broj == 1
    with pytest.raises(profil.GreskaProfila) as greska:
        profil.ucitaj(tekst.encode("utf-8"))
    assert any(kljuc in g for g in greska.value.greske)


def test_fiksne_ne_traze_toleranciju_manju_od_pola_koraka():
    tekst = _toml_fiksni().decode("utf-8").replace('margine = "0,03 cm"', 'margine = "1 cm"')
    assert profil.ucitaj(tekst.encode("utf-8")).tolerancije.margine == jedinice.mm_u_twips(10)


def test_neispravna_zastavica_je_greska_profila():
    tekst = _toml_fiksni().decode("utf-8").replace("fiksne_margine = true", 'fiksne_margine = "da"')
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(tekst.encode("utf-8"))


# --- Provjera i sažetak ------------------------------------------------------


def test_provjera_bez_rbr_uspoređuje_s_osnovicama(fiksni):
    izvjestaj = provjeri(
        ispravan(54, fiksni), fiksni, KontekstProvjere("rad.docx", None, None, None)
    )
    assert izvjestaj.rbr is None
    margine = [n for n in izvjestaj.nalazi if n.pravilo_id == "R-MARGINE"]
    assert margine and all(n.status is Status.PROSLO for n in margine)


def test_krive_margine_tijela_ne_prolaze_uz_fiksne(fiksni, vjezba):
    # Rad s individualnim marginama za Rbr. 54 nema osnovice u tijelu.
    izvjestaj = provjeri(
        ispravan(54, vjezba), fiksni, KontekstProvjere("rad.docx", None, None, None)
    )
    statusi = {n.status for n in izvjestaj.nalazi if n.pravilo_id == "R-MARGINE"}
    assert Status.NE_PROLAZI in statusi


def test_sazetak_bez_rbr(fiksni):
    izvjestaj = provjeri(
        ispravan(1, fiksni), fiksni, KontekstProvjere("rad.docx", None, None, None)
    )
    html = html_sazetka(izvjestaj, "Vježba 1", "-")
    assert poruka("sazetak.rbr") not in html
    assert poruka("sazetak.vjezba") in html
    assert poruka("sazetak.datoteka_bez_rbr") == "sazetak_provjere.html"


# --- Spremnost ---------------------------------------------------------------


def test_spremnost_uz_fiksne_bez_problema_margina(fiksni):
    rezultat = spremnost.pregled(fiksni, [1, 2, 3, 10**6], 4, PROLAZ)
    assert rezultat.spremno, rezultat.problemi
    assert rezultat.margine_jedinstvene is None


def test_spremnost_uz_fiksne_i_dalje_prijavljuje_dupli_rbr(fiksni):
    rezultat = spremnost.pregled(fiksni, [1, 2, 2], 3, PROLAZ)
    assert rezultat.problemi == (spremnost.Problem("spremnost.dupli_rbr", {"rbrovi": "2"}),)


def test_nastavnik_prikazuje_fiksne_margine(tmp_path, monkeypatch):
    from provjera.word.adapteri.popis import spremi

    dom = tmp_path / "dom"
    dom.mkdir()
    monkeypatch.setenv("USERPROFILE", str(dom))
    monkeypatch.setenv("HOME", str(dom))
    pravi = profil.ucitaj_sve
    monkeypatch.setattr(
        profil, "ucitaj_sve", lambda _imenovani: pravi([("vjezba_1.toml", _toml_fiksni())])
    )
    podaci = tmp_path / "ProvjeraWord"
    studenti = tuple(
        Student(r, f"{9900000000 + r}", "Ana", f"Testić{r}", True) for r in (1, 2, 3)
    )
    spremi(studenti, podaci / "vjezba_1" / "popis.csv")
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    at = at.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    tekst = "\n".join(m.value for m in at.markdown)
    assert poruka("spremnost.margine_fiksne") in tekst
    assert poruka("spremnost.margine_neprovjerene") not in tekst
    for prvi, drugi in ((1, 2), (1, 3), (2, 3)):
        assert poruka("spremnost.iste_margine", prvi=prvi, drugi=drugi) not in tekst


# --- PDF ---------------------------------------------------------------------


def _popis() -> tuple[Student, ...]:
    return (
        Student(2, "0036000002", "Đurđa", "Šćekić", True),
        Student(1, "0036000001", "Ana", "Horvat", True),
        Student(3, "0036000003", "Ispisani", "Neaktivnić", False),
    )


def test_retci_bez_margina(fiksni):
    retci = svojstva.retci(fiksni, _popis())
    assert [r.rbr for r in retci] == [1, 2]
    assert all(getattr(r, s) is None for r in retci for s in STRANE)
    assert retci[0].naziv == naziv.kanonski("Ana", "Horvat", fiksni)


def test_zajednicki_zahtjevi_navode_margine_tijela(fiksni):
    twips = _osnovice(fiksni).u_twips()
    ocekivano = poruka(
        "pdf.zahtjev",
        naziv=poruka("pdf.margine_tijela"),
        svojstva=poruka(
            "pdf.opis.margine_tijela",
            **{s: formatiraj(twips[s], Jedinica.TWIPS) for s in STRANE},
        ),
    )
    assert ocekivano in svojstva.zajednicki_zahtjevi(fiksni)


def test_zahtjev_naslovnice_uz_fiksne(fiksni):
    naslovnica = formatiraj(jedinice.mm_u_twips(fiksni.formula.naslovnica), Jedinica.TWIPS)
    ocekivano = poruka(
        "pdf.zahtjev",
        naziv=poruka("pdf.naslovnica"),
        svojstva=poruka("pdf.opis.naslovnica_fiksne", naslovnica=naslovnica),
    )
    assert ocekivano in svojstva.zajednicki_zahtjevi(fiksni)


def test_margine_tijela_navedene_i_uz_iskljucen_r_margine(fiksni):
    pravila = dict(fiksni.pravila)
    pravila["R-MARGINE"] = pravila["R-MARGINE"].model_copy(update={"ukljuceno": False})
    bez = fiksni.model_copy(update={"pravila": pravila})
    zahtjevi = svojstva.zajednicki_zahtjevi(bez)
    assert any(poruka("pdf.margine_tijela") in z for z in zahtjevi)
    assert not any(poruka("pdf.naslovnica") in z for z in zahtjevi)


def test_individualni_zahtjevi_bez_margina_tijela(vjezba):
    assert not any(
        poruka("pdf.margine_tijela") in z for z in svojstva.zajednicki_zahtjevi(vjezba)
    )


def test_pdf_tablica_bez_stupaca_margina(fiksni):
    citac = PdfReader(io.BytesIO(izradi_pdf(fiksni, _popis())))
    tekst = " ".join(" ".join(s.extract_text() for s in citac.pages).split())
    assert poruka("pdf.margine_tijela") in tekst
    assert poruka("pdf.tablica_naslov_fiksne") in tekst
    assert " ".join(poruka("pdf.uputa_fiksne").split()) in tekst
    assert " ".join(poruka("pdf.uputa").split()) not in tekst
    assert poruka("pdf.tablica_opis") not in tekst
    for stupac in STRANE:
        assert poruka(f"pdf.stupac_{stupac}") not in tekst
    assert naziv.kanonski("Đurđa", "Šćekić", fiksni) in tekst


# --- Batch -------------------------------------------------------------------


def test_batch_uz_fiksne(tmp_path, fiksni):
    studenti = tuple(Student(r, f"{9900000000 + r}", "Ana", p, True) for r, p in ((1, "Testa"), (2, "Testb")))
    for s in studenti:
        (tmp_path / naziv.kanonski(s.ime, s.prezime, fiksni)).write_bytes(ispravan(s.rbr, fiksni))
    rezultat = batch.pokreni(tmp_path, fiksni, studenti)
    assert [d.status for d in rezultat.datoteke] == [UkupniStatus.SPREMNO] * 2


# --- Studentska aplikacija ---------------------------------------------------


@pytest.fixture
def aplikacija_fiksna(monkeypatch, fiksni):
    monkeypatch.setattr(profil, "objavljeni", lambda _sadrzaji: ([fiksni], 0))
    return AppTest.from_file(STUDENT).run()


def test_student_bez_rbr_odmah_ucitava(aplikacija_fiksna, fiksni):
    at = aplikacija_fiksna
    assert not at.exception
    assert not at.text_input
    assert at.file_uploader
    ocekivane = _osnovice(fiksni).u_twips()
    assert [(m.label, m.value) for m in at.metric] == [
        (poruka(f"margine.{s}"), formatiraj(ocekivane[s], Jedinica.TWIPS)) for s in STRANE
    ]
    assert poruka("margine.naslov_fiksne") in [s.value for s in at.subheader]
    natpisi = [c.value for c in at.caption]
    assert poruka("margine.naslovnica", naslovnica="2,5 cm") in natpisi
    assert poruka("margine.usporedi") not in natpisi
    assert "Ime_Prezime_GiG_OG_Vjezba_1.docx" in " ".join(m.value for m in at.markdown)


def test_student_ucitava_i_dobiva_sazetak_bez_rbr(monkeypatch, aplikacija_fiksna, fiksni):
    import streamlit

    pozivi = []
    pravi = streamlit.download_button

    def spijun(*a, **k):
        pozivi.append(k)
        return pravi(*a, **k)

    monkeypatch.setattr(streamlit, "download_button", spijun)
    at = aplikacija_fiksna
    at.file_uploader[0].set_value(
        ("Lucija_Šimek_GiG_OG_Vjezba_1.docx", ispravan(54, fiksni), "application/octet-stream")
    )
    at = at.run()
    assert not at.exception
    assert [s.value for s in at.success] == [poruka("izvjestaj.spremno")]
    assert at.session_state["izvjestaj"].rbr is None
    assert pozivi[-1]["file_name"] == "sazetak_provjere.html"
    assert poruka("sazetak.rbr") not in pozivi[-1]["data"].decode("utf-8")

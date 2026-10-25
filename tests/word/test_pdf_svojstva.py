"""PDF sa svojstvima (priča 3.5): ``jezgra.svojstva`` i adapter ``pdf_svojstva``."""

import io
from pathlib import Path

import pytest
from pypdf import PdfReader

from provjera.word.adapteri.pdf_svojstva import izradi_pdf, spremi_pdf
from provjera.word.adapteri.popis import Student
from provjera.word.jezgra import formula, profil, svojstva
from provjera.zajednicko import naziv
from provjera.word.jezgra.jedinice import Jedinica
from provjera.word.jezgra.poruke import formatiraj, poruka

VJEZBA_1 = Path(__file__).resolve().parents[2] / "tests" / "word" / "fixtures" / "vjezba_1_baseline.toml"


@pytest.fixture(scope="module")
def vjezba() -> profil.Profil:
    return profil.ucitaj(VJEZBA_1.read_bytes())


def _popis() -> tuple[Student, ...]:
    """Rbr. 1–5, Rbr. 3 je ispisan; namjerno nije poredan po Rbr."""
    return (
        Student(2, "0036000002", "Đurđa", "Šćekić", True),
        Student(1, "0036000001", "Ana Marija", "Horvat-Kovač", True),
        Student(3, "0036000003", "Ispisani", "Neaktivnić", False),
        Student(5, "0036000005", "Žana", "Čolić", True),
        Student(4, "0036000004", "Ivo", "Babić", True),
    )


def _tekst(sadrzaj: bytes) -> str:
    citac = PdfReader(io.BytesIO(sadrzaj))
    return "\n".join(stranica.extract_text() for stranica in citac.pages)


def _bez_prijeloma(tekst: str) -> str:
    return " ".join(tekst.split())


@pytest.fixture(scope="module")
def tekst_pdf(vjezba) -> str:
    return _tekst(izradi_pdf(vjezba, _popis()))


def test_retci_samo_aktivni_redom_po_rbr(vjezba):
    retci = svojstva.retci(vjezba, _popis())
    assert [r.rbr for r in retci] == [1, 2, 4, 5]
    assert [(r.ime, r.prezime) for r in retci][:2] == [
        ("Ana Marija", "Horvat-Kovač"),
        ("Đurđa", "Šćekić"),
    ]


def test_margine_i_nazivi_jednaki_funkcijama_jezgre(vjezba):
    for r in svojstva.retci(vjezba, _popis()):
        twips = formula.margine(r.rbr, vjezba.formula).u_twips()
        assert (r.gore, r.dolje, r.lijevo, r.desno) == tuple(
            formatiraj(twips[s], Jedinica.TWIPS) for s in ("gore", "dolje", "lijevo", "desno")
        )
        assert r.naziv == naziv.kanonski(r.ime, r.prezime, vjezba)
    prvi = svojstva.retci(vjezba, _popis())[0]
    assert prvi.naziv == "AnaMarija_HorvatKovač_GiG_OG_Vjezba_1.docx"
    assert "," in prvi.lijevo or prvi.lijevo.endswith(" cm")


def test_margine_za_sve_rbr_jednake_web_provjeri(vjezba):
    # Web provjera prikazuje formatiraj(formula.margine(rbr).u_twips()[strana], TWIPS).
    studenti = [Student(r, f"{9900000000 + r}", "Ana", "Anić", True) for r in range(1, 501)]
    for redak in svojstva.retci(vjezba, studenti):
        web = formula.margine(redak.rbr, vjezba.formula).u_twips()
        for strana in ("gore", "dolje", "lijevo", "desno"):
            assert getattr(redak, strana) == formatiraj(web[strana], Jedinica.TWIPS)
            assert "." not in getattr(redak, strana)


def test_pdf_sadrzi_retke_aktivnih_studenata(vjezba, tekst_pdf):
    retci = svojstva.retci(vjezba, _popis())
    assert len(retci) == 4
    redovi_teksta = tekst_pdf.splitlines()
    for r in retci:
        ocekivano = " ".join(
            (str(r.rbr), r.ime, r.prezime, r.naziv, r.gore, r.dolje, r.lijevo, r.desno)
        )
        assert ocekivano in redovi_teksta
    assert "Neaktivnić" not in tekst_pdf
    assert "Ispisani" not in tekst_pdf


def test_hrvatski_znakovi(tekst_pdf):
    assert "Đurđa" in tekst_pdf
    assert "Šćekić" in tekst_pdf
    assert "Žana" in tekst_pdf
    assert "Čolić" in tekst_pdf


def test_bez_jmbaga(tekst_pdf):
    for s in _popis():
        assert s.jmbag not in tekst_pdf
    assert "0036" not in tekst_pdf
    assert poruka("nastavnik.stupac_jmbag") not in tekst_pdf


def test_uvodni_dio(vjezba, tekst_pdf):
    tekst = _bez_prijeloma(tekst_pdf)
    assert poruka("pdf.naslov", naziv=vjezba.vjezba.naziv) in tekst
    assert poruka("pdf.verzija", verzija=profil.verzija(vjezba)) in tekst
    assert poruka("pdf.poveznica", poveznica=vjezba.vjezba.poveznica) in tekst
    assert _bez_prijeloma(poruka("privatnost.obrada")) in tekst
    assert "SAD" in tekst
    for zahtjev in svojstva.zajednicki_zahtjevi(vjezba):
        assert _bez_prijeloma(zahtjev) in tekst


def test_pdf_ima_poveznicu_na_web_provjeru(vjezba):
    citac = PdfReader(io.BytesIO(izradi_pdf(vjezba, _popis())))
    poveznice = [
        a.get_object()["/A"]["/URI"]
        for a in citac.pages[0].get("/Annots", [])
        if "/A" in a.get_object()
    ]
    assert vjezba.vjezba.poveznica in poveznice


def test_zajednicki_zahtjevi_vjezbe_1(vjezba):
    zahtjevi = svojstva.zajednicki_zahtjevi(vjezba)
    assert [z.split(":")[0] for z in zahtjevi] == [
        poruka("pravilo.R-NAZIV"),
        poruka("pravilo.R-SEKCIJE"),
        poruka("pdf.naslovnica"),
        poruka("pravilo.R-TEKST"),
        poruka("pravilo.R-NASLOVI"),
        poruka("pravilo.R-SAZETAK"),
        poruka("pravilo.R-LITERATURA"),
        poruka("pravilo.R-BROJ-STRANICE"),
        poruka("pravilo.R-STILOVI"),
        poruka("pravilo.R-PROMJENE"),
        poruka("pravilo.R-OKVIRI"),
    ]
    naziv_dat, sekcije, naslovnica, tekst, naslovi, sazetak = zahtjevi[:6]
    assert vjezba.naziv_datoteke.obrazac in naziv_dat
    assert poruka("pdf.opis.R-SEKCIJE") in sekcije
    assert poruka("pdf.opis.R-PROMJENE") in zahtjevi[-2]
    assert poruka("pdf.opis.R-OKVIRI") in zahtjevi[-1]
    assert "2,5 cm" in naslovnica
    assert "Calibri" in tekst and "12 pt" in tekst and "6 pt" in tekst
    assert poruka("poravnanje.obostrano") in tekst
    assert poruka("prored.jednostruko") in tekst
    assert "1., 2." in naslovi
    assert "{n}" not in naslovi
    assert "3,5 cm" in sazetak


def _bez_pravila(pravilo_id: str) -> profil.Profil:
    sadrzaj = VJEZBA_1.read_text(encoding="utf-8")
    zaglavlje = f"[pravila.{pravilo_id}]\n"
    pocetak = sadrzaj.index(zaglavlje)
    kraj = sadrzaj.index("ukljuceno = true", pocetak)
    assert "[pravila." not in sadrzaj[pocetak + len(zaglavlje) : kraj]
    sadrzaj = sadrzaj[:kraj] + "ukljuceno = false" + sadrzaj[kraj + len("ukljuceno = true") :]
    return profil.ucitaj(sadrzaj.encode("utf-8"))


def test_iskljuceno_pravilo_se_ne_navodi():
    bez_literature = _bez_pravila("R-LITERATURA")
    zahtjevi = svojstva.zajednicki_zahtjevi(bez_literature)
    assert len(zahtjevi) == 10
    assert not any(z.startswith(poruka("pravilo.R-LITERATURA") + ":") for z in zahtjevi)
    tekst = _tekst(izradi_pdf(bez_literature, _popis()))
    assert poruka("pravilo.R-LITERATURA") + ":" not in tekst
    assert poruka("pravilo.R-TEKST") + ":" in tekst


def test_iskljucene_margine_bez_naslovnice():
    zahtjevi = svojstva.zajednicki_zahtjevi(_bez_pravila("R-MARGINE"))
    assert not any(z.startswith(poruka("pdf.naslovnica") + ":") for z in zahtjevi)


def test_vise_stranica_ponavlja_zaglavlje_tablice(vjezba):
    studenti = [Student(r, f"{9900000000 + r}", "Ana", f"Anić{r}", True) for r in range(1, 151)]
    citac = PdfReader(io.BytesIO(izradi_pdf(vjezba, studenti)))
    assert len(citac.pages) > 1
    zaglavlje = poruka("pdf.stupac_naziv")
    for stranica in citac.pages:
        assert zaglavlje in stranica.extract_text()
    zadnja = citac.pages[-1].extract_text()
    assert poruka("pdf.stranica", broj=len(citac.pages), ukupno=len(citac.pages)) in zadnja


def test_rbr_izvan_formule_baca_value_error(vjezba):
    najveci = formula.najveci_rbr(vjezba.formula)
    with pytest.raises(ValueError):
        izradi_pdf(vjezba, [Student(najveci + 1, "0036000001", "Ana", "Anić", True)])


def test_spremi_pdf_prepisuje_atomski(tmp_path):
    putanja = tmp_path / "vjezba_1" / "svojstva_vjezba_1.pdf"
    spremi_pdf(b"%PDF-staro", putanja)
    spremi_pdf(b"%PDF-novo", putanja)
    assert putanja.read_bytes() == b"%PDF-novo"
    assert [p.name for p in putanja.parent.iterdir()] == [putanja.name]


@pytest.mark.parametrize(
    ("pravilo_id", "naziv_retka"),
    [
        ("R-NAZIV", "pravilo.R-NAZIV"),
        ("R-SEKCIJE", "pravilo.R-SEKCIJE"),
        ("R-PROMJENE", "pravilo.R-PROMJENE"),
        ("R-OKVIRI", "pravilo.R-OKVIRI"),
        ("R-STILOVI", "pravilo.R-STILOVI"),
        ("R-BROJ-STRANICE", "pravilo.R-BROJ-STRANICE"),
    ],
)
def test_iskljuceno_pravilo_bez_retka(vjezba, pravilo_id, naziv_retka):
    def nazivi(p):
        return [z.split(":")[0] for z in svojstva.zajednicki_zahtjevi(p)]

    assert poruka(naziv_retka) in nazivi(vjezba)
    bez = nazivi(_bez_pravila(pravilo_id))
    assert poruka(naziv_retka) not in bez
    assert len(bez) == len(nazivi(vjezba)) - 1

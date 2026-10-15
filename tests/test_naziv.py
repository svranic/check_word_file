import unicodedata
from pathlib import Path

import pytest

from provjera.jezgra import naziv, profil
from provjera.jezgra.nalaz import KontekstProvjere, NacinUparivanja, Status
from provjera.jezgra.pravila import REGISTAR

KORIJEN = Path(__file__).resolve().parents[1]
PROFIL = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
LUCIJA = "Lucija_Šimek_GiG_OG_Vjezba_1.docx"


def nfd(tekst: str) -> str:
    return unicodedata.normalize("NFD", tekst)


def r_naziv(naziv_datoteke, ocekivani=None, nacin=None):
    kontekst = KontekstProvjere(naziv_datoteke, 54, ocekivani, nacin)
    pravilo = REGISTAR["R-NAZIV"]
    return pravilo.funkcija(None, kontekst, PROFIL.pravila["R-NAZIV"], PROFIL)


@pytest.mark.parametrize(
    ("ime", "prezime", "ocekivano"),
    [
        ("Ana Marija", "Horvat-Kovač", "AnaMarija_HorvatKovač_GiG_OG_Vjezba_1.docx"),
        ("IVA", "Horvat", "Iva_Horvat_GiG_OG_Vjezba_1.docx"),
        ("  Lucija ", "ŠIMEK", "Lucija_Šimek_GiG_OG_Vjezba_1.docx"),
        ("Ana  marija", "horvat kovač", "AnaMarija_HorvatKovač_GiG_OG_Vjezba_1.docx"),
        (nfd("Đurđa"), nfd("Čačić"), "Đurđa_Čačić_GiG_OG_Vjezba_1.docx"),
    ],
)
def test_kanonski(ime, prezime, ocekivano):
    assert naziv.kanonski(ime, prezime, PROFIL) == ocekivano


@pytest.mark.parametrize("naziv_datoteke", [LUCIJA, nfd(LUCIJA), "AnaMarija_HorvatKovač_GiG_OG_Vjezba_1.docx"])
def test_web_ispravan_naziv(naziv_datoteke):
    [nalaz] = r_naziv(naziv_datoteke)
    assert nalaz.status is Status.PROSLO


@pytest.mark.parametrize(
    "naziv_datoteke",
    [
        "Lucija Šimek_GiG_OG_Vjezba_1.docx",
        "Lucija_Šimek.docx",
        "Lucija_GiG_OG_Vjezba_1.docx",
        "Lucija_Šimek_GiG_OG_Vjezba_1.doc",
        "Lucija2_Šimek_GiG_OG_Vjezba_1.docx",
        "Lucija_Šimek_GiG_OG_Vjezba_1.DOCX",
        "Lucija_Šimek_gig_og_vjezba_1.docx",
    ],
)
def test_web_neispravan_naziv(naziv_datoteke):
    [nalaz] = r_naziv(naziv_datoteke)
    assert nalaz.status is Status.NE_PROLAZI
    assert nalaz.ocekivano.iznos == "Ime_Prezime_GiG_OG_Vjezba_1.docx"
    assert nalaz.pronadeno.iznos == naziv_datoteke


def test_batch_tocan_naziv_nfc_i_nfd():
    [nalaz] = r_naziv(nfd(LUCIJA), LUCIJA, NacinUparivanja.TOCAN)
    assert nalaz.status is Status.PROSLO


@pytest.mark.parametrize("nacin", [NacinUparivanja.PRIBLIZAN, NacinUparivanja.PODMAPA, NacinUparivanja.JMBAG])
def test_batch_drugi_nacin_uparivanja(nacin):
    [nalaz] = r_naziv(LUCIJA, LUCIJA, nacin)
    assert nalaz.status is Status.NE_PROLAZI
    assert nalaz.poruka_kljuc == "R-NAZIV.nije_tocno_upareno"


def test_batch_drugi_naziv():
    [nalaz] = r_naziv("lucija_simek_GiG_OG_Vjezba_1.docx", LUCIJA, NacinUparivanja.PRIBLIZAN)
    assert nalaz.status is Status.NE_PROLAZI
    assert nalaz.ocekivano.iznos == LUCIJA


def test_kljucevi_r_naziv_su_deklarirani():
    deklarirani = set(REGISTAR["R-NAZIV"].poruke)
    slucajevi = [
        r_naziv(LUCIJA),
        r_naziv("x.docx"),
        r_naziv(LUCIJA, LUCIJA, NacinUparivanja.TOCAN),
        r_naziv(LUCIJA, LUCIJA, NacinUparivanja.JMBAG),
        r_naziv("x.docx", LUCIJA, NacinUparivanja.TOCAN),
    ]
    assert {n.poruka_kljuc for s in slucajevi for n in s} == deklarirani


def test_kanonski_uklanja_znakove_koji_nisu_slova_i_odgovara_obrascu():
    kanonski = naziv.kanonski("Ana M.", "D'Angelo", PROFIL)
    assert kanonski == "AnaM_DAngelo_GiG_OG_Vjezba_1.docx"
    assert naziv.odgovara_obrascu(kanonski, PROFIL)


@pytest.mark.parametrize(("ime", "prezime"), [("", "Horvat"), ("Ana", "  - ")])
def test_kanonski_odbija_prazno_ime(ime, prezime):
    with pytest.raises(ValueError):
        naziv.kanonski(ime, prezime, PROFIL)


@pytest.mark.parametrize(("ocekivani", "nacin"), [(LUCIJA, None), (None, NacinUparivanja.TOCAN)])
def test_kontekst_trazi_oba_polja_zajedno(ocekivani, nacin):
    with pytest.raises(ValueError):
        KontekstProvjere(LUCIJA, 54, ocekivani, nacin)


# --- naziv.kljuc_uparivanja ---------------------------------------------------


@pytest.mark.parametrize(
    "tekst",
    [
        "Ana_Horvat_GiG_OG_Vjezba_1.docx",
        "ana_horvat_gig_og_vjezba_1 (1).DOCX",
        "ANA_HORVAT_GIG_OG_VJEZBA_1(2).docx",
        "Ana_Horvat_GiG_OG_Vjezba_1.pdf",
    ],
)
def test_kljuc_uparivanja(tekst):
    assert naziv.kljuc_uparivanja(tekst) == naziv.kljuc_uparivanja(
        naziv.kanonski("Ana", "Horvat", PROFIL)
    )


def test_kljuc_bez_dijakritika_i_d():
    assert naziv.kljuc_uparivanja("Đorđe_Šašić") == naziv.kljuc_uparivanja("Dorde_Sasic")
    assert naziv.kljuc_uparivanja("Ana_Horvat_x") != naziv.kljuc_uparivanja("Ana_Horvat_y")


def test_kljuc_vise_sufiksa_kopije():
    assert naziv.kljuc_uparivanja("Ana_Horvat (1) (2).docx") == naziv.kljuc_uparivanja("Ana_Horvat.docx")

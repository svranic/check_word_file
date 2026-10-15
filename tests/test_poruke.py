from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.nalaz import Dio, Izvor, Lokacija, Nalaz, Status, Vrijednost, VrstaIzvora
from provjera.jezgra.poruke import KATALOG, opis_izvora, opis_lokacije, tekst_nalaza


def test_tekst_nalaza_umece_formatirane_vrijednosti():
    nalaz = Nalaz(
        "R-NAZIV",
        Status.NE_PROLAZI,
        Lokacija(Dio.NAZIV),
        "R-NAZIV.ne_odgovara_obrascu",
        ocekivano=Vrijednost("Ime_Prezime_GiG_OG_Vjezba_1.docx", Jedinica.TEKST),
        pronadeno=Vrijednost("rad.docx", Jedinica.TEKST),
    )
    tekst = tekst_nalaza(nalaz)
    assert "„rad.docx“" in tekst
    assert "Ime_Prezime_GiG_OG_Vjezba_1.docx" in tekst


def test_tekst_nalaza_s_parametrima():
    nalaz = Nalaz("R-X", Status.NEPROVJERLJIVO, Lokacija(Dio.DOKUMENT), "opce.neprovjerljivo", parametri={"razlog": "KeyError"})
    assert "KeyError" in tekst_nalaza(nalaz)


def test_opis_lokacije():
    assert opis_lokacije(Lokacija(Dio.NAZIV)) == "Naziv datoteke"
    assert opis_lokacije(Lokacija(Dio.TIJELO, sekcija=2, odlomak=5, isjecak="Uvod u")) == (
        "Tijelo dokumenta, sekcija 2, odlomak 5: „Uvod u…“"
    )


def test_opis_izvora():
    assert opis_izvora(Izvor(VrstaIzvora.STIL, "Normal")) == "stil „Normal“"
    assert opis_izvora(Izvor(VrstaIzvora.TEMA)) == "tema dokumenta"


def test_svaki_status_dio_i_izvor_ima_poruku():
    for status in Status:
        assert f"status.{status.value}" in KATALOG
        assert f"izvjestaj.grupa.{status.value}" in KATALOG
    for dio in Dio:
        assert f"lokacija.{dio.value}" in KATALOG
    for vrsta in VrstaIzvora:
        assert f"izvor.{vrsta.value}" in KATALOG


def test_status_ima_ikonu_i_tekst():
    for status in Status:
        tekst = KATALOG[f"status.{status.value}"]
        ikona, _, rijec = tekst.partition(" ")
        assert ikona and not ikona.isalpha() and rijec


def test_svaki_nacin_i_razlog_uparivanja_ima_poruku():
    from provjera.jezgra.nalaz import NacinUparivanja
    from provjera.jezgra.uparivanje import RazlogNepovezanosti

    for razlog in RazlogNepovezanosti:
        assert f"uparivanje.{razlog.value}" in KATALOG
    for nacin in NacinUparivanja:
        assert f"uparivanje.nacin.{nacin.value}" in KATALOG

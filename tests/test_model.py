import io
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from alati.generator import VARIJANTE, ispravan

from provjera.jezgra import formula, model, profil
from provjera.jezgra.model import TipPocetka
from provjera.jezgra.model.uloge import Uloga, uloge_sekcija
from provjera.jezgra.nalaz import KontekstProvjere, Status
from provjera.jezgra.poruke import KATALOG, tekst_nalaza
from provjera.jezgra.pravila import REGISTAR
from provjera.jezgra.provjera import provjeri
from provjera.jezgra.ulaz import RazlogOdbijanja

KORIJEN = Path(__file__).resolve().parents[1]
PROFIL = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
KONTEKST = KontekstProvjere("Ana_Horvat_GiG_OG_Vjezba_1.docx", 54, None, None)


def test_uloge_sekcija():
    assert uloge_sekcija(0) == ()
    assert uloge_sekcija(1) == (Uloga.TIJELO,)
    assert uloge_sekcija(3) == (Uloga.NASLOVNICA, Uloga.TIJELO, Uloga.TIJELO)


def test_model_ispravnog_rada_u_twipsima():
    m = model.procitaj(ispravan(54, PROFIL), PROFIL.uloge)
    naslovnica, tijelo = m.sekcije
    assert naslovnica.uloga is Uloga.NASLOVNICA and tijelo.uloga is Uloga.TIJELO
    assert (naslovnica.gore, naslovnica.lijevo) == (1417, 1417)
    ocekivane = formula.margine(54, PROFIL.formula).u_twips()
    assert {s: getattr(tijelo, s) for s in ocekivane} == ocekivane
    assert (tijelo.sirina, tijelo.visina, tijelo.gutter, tijelo.pejzazno) == (11906, 16838, 0, False)
    assert tijelo.pocetak is TipPocetka.SLJEDECA_STRANICA
    assert not m.zrcalne_margine


def test_model_prepoznaje_zrcalne_margine_i_neprekinuto():
    assert model.procitaj(VARIJANTE["zrcalne"](54, PROFIL), PROFIL.uloge).zrcalne_margine
    assert model.procitaj(VARIJANTE["neprekinuti_prijelom"](54, PROFIL), PROFIL.uloge).sekcije[1].pocetak is TipPocetka.NEPREKINUTO


def test_dokument_bez_dijelova_je_odbijen_kao_ostecen():
    spremnik = io.BytesIO()
    with zipfile.ZipFile(spremnik, "w") as arhiva:
        arhiva.writestr("[Content_Types].xml", b"<Types/>")
        arhiva.writestr("word/document.xml", b"<nije-xml")
    with pytest.raises(model.NeispravanDokument):
        model.procitaj(spremnik.getvalue(), PROFIL.uloge)
    izvjestaj = provjeri(spremnik.getvalue(), PROFIL, KONTEKST)
    assert izvjestaj.odbijeno is RazlogOdbijanja.OSTECENA
    assert izvjestaj.nalazi == ()


def test_nedostajuca_margina_je_neprovjerljiva():
    m = model.procitaj(ispravan(54, PROFIL), PROFIL.uloge)
    m = replace(m, sekcije=(m.sekcije[0], replace(m.sekcije[1], lijevo=None)))
    pravilo = REGISTAR["R-MARGINE"]
    nalazi = pravilo.funkcija(m, KONTEKST, PROFIL.pravila["R-MARGINE"], PROFIL)
    assert [n.status for n in nalazi if n.lokacija.sekcija == 2] == [Status.NEPROVJERLJIVO]


def test_nalaz_margina_navodi_sve_cetiri_margine_i_toleranciju():
    izvjestaj = provjeri(VARIJANTE["krive_margine_tijela"](54, PROFIL), PROFIL, KONTEKST)
    [nalaz] = [n for n in izvjestaj.nalazi if n.status is Status.NE_PROLAZI]
    tekst = tekst_nalaza(nalaz)
    assert "Sekcija 2" in tekst and "2,6 cm" in tekst and "2,7 cm" in tekst and "0,03 cm" in tekst
    for strana in ("gore", "dolje", "lijevo", "desno"):
        assert strana in tekst


def test_svi_kljucevi_novih_pravila_se_formatiraju():
    for varijanta in VARIJANTE.values():
        for nalaz in provjeri(varijanta(54, PROFIL), PROFIL, KONTEKST).nalazi:
            assert nalaz.poruka_kljuc in REGISTAR[nalaz.pravilo_id].poruke
            assert "{" not in tekst_nalaza(nalaz)
    for pravilo_id in ("R-SEKCIJE", "R-MARGINE"):
        assert all(k in KATALOG for k in REGISTAR[pravilo_id].poruke)


def _s_promjenom(promjena) -> bytes:
    import docx as python_docx

    dokument = python_docx.Document(io.BytesIO(ispravan(54, PROFIL)))
    promjena(dokument)
    spremnik = io.BytesIO()
    dokument.save(spremnik)
    return spremnik.getvalue()


def _kljucevi_koji_padaju(sadrzaj: bytes) -> set[str]:
    return {n.poruka_kljuc for n in provjeri(sadrzaj, PROFIL, KONTEKST).nalazi if n.status is not Status.PROSLO}


def test_pejzazna_a4_je_samo_pejzaz_ne_i_kriva_velicina():
    assert _kljucevi_koji_padaju(VARIJANTE["pejzazno"](54, PROFIL)) == {"R-MARGINE.pejzazno"}


def test_pejzaz_prema_dimenzijama_bez_atributa_orient():
    def zamijeni(d):
        s = d.sections[1]
        s.page_width, s.page_height = s.page_height, s.page_width

    sadrzaj = _s_promjenom(zamijeni)
    assert model.procitaj(sadrzaj, PROFIL.uloge).sekcije[1].pejzazno
    assert _kljucevi_koji_padaju(sadrzaj) == {"R-MARGINE.pejzazno"}


def test_orient_landscape_s_uspravnim_dimenzijama_nije_pejzaz():
    from docx.enum.section import WD_ORIENTATION

    def samo_atribut(d):
        d.sections[1].orientation = WD_ORIENTATION.LANDSCAPE

    assert not model.procitaj(_s_promjenom(samo_atribut), PROFIL.uloge).sekcije[1].pejzazno


@pytest.mark.parametrize(("val", "zrcalne"), [("0", False), ("false", False), ("off", False), ("true", True), ("1", True)])
def test_zrcalne_margine_prema_vrijednosti(val, zrcalne):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def dodaj(d):
        element = OxmlElement("w:mirrorMargins")
        element.set(qn("w:val"), val)
        d.settings.element.append(element)

    assert model.procitaj(_s_promjenom(dodaj), PROFIL.uloge).zrcalne_margine is zrcalne


def test_margina_tik_izvan_tolerancije_ne_prolazi():
    from docx.shared import Twips

    tijelo = formula.margine(54, PROFIL.formula).u_twips()

    def pomakni(d):
        d.sections[1].right_margin = Twips(tijelo["desno"] + PROFIL.tolerancije.margine + 1)

    assert _kljucevi_koji_padaju(_s_promjenom(pomakni)) == {"R-MARGINE.sekcija_odstupa"}


def test_treca_sekcija_je_tijelo_s_individualnim_marginama():
    from docx.enum.section import WD_SECTION_START

    def dodaj_sekciju(d):
        d.add_section(WD_SECTION_START.NEW_PAGE)

    m = model.procitaj(_s_promjenom(dodaj_sekciju), PROFIL.uloge)
    assert [s.uloga for s in m.sekcije] == [Uloga.NASLOVNICA, Uloga.TIJELO, Uloga.TIJELO]
    ocekivane = formula.margine(54, PROFIL.formula).u_twips()
    assert {s: getattr(m.sekcije[2], s) for s in ocekivane} == ocekivane
    assert _kljucevi_koji_padaju(_s_promjenom(dodaj_sekciju)) == set()


def test_jedna_sekcija_daje_uputu_za_prijelom():
    izvjestaj = provjeri(VARIJANTE["jedna_sekcija"](54, PROFIL), PROFIL, KONTEKST)
    [nalaz] = [n for n in izvjestaj.nalazi if n.status is Status.NE_PROLAZI]
    assert "Izgled (Layout) → Prijelomi (Breaks) → Sljedeća stranica (Next Page)" in tekst_nalaza(nalaz)


def test_greska_citanja_postavki_ne_odbija_dokument(monkeypatch):
    def baca(*_):
        raise ValueError("neobičan atribut")

    monkeypatch.setattr(model, "_sekcija", baca)
    izvjestaj = provjeri(ispravan(54, PROFIL), PROFIL, KONTEKST)
    assert izvjestaj.odbijeno is None
    statusi = {n.pravilo_id: n.status for n in izvjestaj.nalazi}
    assert statusi["R-NAZIV"] is Status.PROSLO
    assert statusi["R-SEKCIJE"] is Status.NEPROVJERLJIVO
    assert statusi["R-MARGINE"] is Status.NEPROVJERLJIVO


def test_dokument_bez_sekcija_je_neprovjerljiv():
    prazan = model.DocModel()
    for pravilo_id in ("R-SEKCIJE", "R-MARGINE"):
        pravilo = REGISTAR[pravilo_id]
        [nalaz] = pravilo.funkcija(prazan, KONTEKST, PROFIL.pravila[pravilo_id], PROFIL)
        assert nalaz.status is Status.NEPROVJERLJIVO

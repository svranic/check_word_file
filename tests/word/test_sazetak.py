from pathlib import Path

from alati.generator import VARIJANTE, ispravan

from provjera.word.jezgra import profil
from provjera.word.jezgra.nalaz import KontekstProvjere
from provjera.word.jezgra.poruke import poruka
from provjera.word.jezgra.provjera import provjeri
from provjera.word.jezgra.sazetak import html_sazetka

KORIJEN = Path(__file__).resolve().parents[2]
PROFIL = profil.ucitaj((KORIJEN / "profili" / "word" / "vjezba_1.toml").read_bytes())
TAJNI_NAZIV = "Tajna_Studentica_GiG_OG_Vjezba_1.docx"


def _izvjestaj(sadrzaj: bytes, naziv: str = TAJNI_NAZIV):
    return provjeri(sadrzaj, PROFIL, KontekstProvjere(naziv, 54, None, None))


def test_spreman_rad():
    izvjestaj = _izvjestaj(ispravan(54, PROFIL))
    html = html_sazetka(izvjestaj, "Vježba 1", "12.10.2026. 21:30")
    assert html.startswith("<!doctype html>") and 'lang="hr"' in html and 'charset="utf-8"' in html
    for tekst in ("54", "Vježba 1", izvjestaj.profil_verzija, "12.10.2026. 21:30", poruka("sazetak.spremno")):
        assert tekst in html
    for pravilo_id in ("R-NAZIV", "R-SEKCIJE", "R-MARGINE"):
        assert f"<td>{poruka(f'pravilo.{pravilo_id}')}</td><td>{poruka('status.PROSLO')}</td>" in html


def test_nespreman_rad_navodi_status_po_pravilu():
    html = html_sazetka(_izvjestaj(VARIJANTE["jedna_sekcija"](54, PROFIL), "los naziv.docx"), "Vježba 1", "-")
    assert poruka("sazetak.nije_spremno") in html
    assert f"<td>{poruka('pravilo.R-SEKCIJE')}</td><td>{poruka('status.NE_PROLAZI')}</td>" in html
    assert f"<td>{poruka('pravilo.R-NAZIV')}</td><td>{poruka('status.NE_PROLAZI')}</td>" in html
    assert f"<td>{poruka('pravilo.R-MARGINE')}</td><td>{poruka('status.PROSLO')}</td>" in html


def test_sazetak_ne_sadrzi_naziv_datoteke_ni_vrijednosti():
    izvjestaj = _izvjestaj(VARIJANTE["krive_margine_tijela"](54, PROFIL), "Tajna Studentica.docx")
    html = html_sazetka(izvjestaj, "Vježba 1", "-")
    assert "Tajna" not in html
    assert "cm" not in html  # nema očekivanih ni pronađenih margina


def test_posebni_znakovi_su_escapirani():
    html = html_sazetka(_izvjestaj(ispravan(54, PROFIL)), "Vježba <1> & <script>", "-")
    assert "<script>" not in html
    assert "Vježba &lt;1&gt; &amp; &lt;script&gt;" in html


def test_nema_vanjskih_resursa():
    html = html_sazetka(_izvjestaj(ispravan(54, PROFIL)), "Vježba 1", "-")
    for oznaka in ("<link", "<script", "src=", "http"):
        assert oznaka not in html


def test_vrijednosti_i_isjecak_nisu_u_sazetku():
    from dataclasses import replace

    from provjera.word.jezgra.jedinice import Jedinica
    from provjera.word.jezgra.nalaz import Dio, Lokacija, Nalaz, Status, Vrijednost
    from provjera.word.jezgra.poruke import formatiraj

    izvjestaj = _izvjestaj(VARIJANTE["krive_margine_tijela"](54, PROFIL))
    s_isjeckom = Nalaz("R-NAZIV", Status.NE_PROLAZI, Lokacija(Dio.TIJELO, 2, 7, "TAJNI ISJEČAK"),
                       "R-NAZIV.ne_odgovara_obrascu", pronadeno=Vrijednost("x", Jedinica.TEKST))
    izvjestaj = replace(izvjestaj, nalazi=izvjestaj.nalazi + (s_isjeckom,))
    html = html_sazetka(izvjestaj, "Vježba 1", "-")
    assert "TAJNI ISJEČAK" not in html
    for nalaz in izvjestaj.nalazi:
        for vrijednost in [*nalaz.parametri.values(), nalaz.ocekivano, nalaz.pronadeno]:
            if isinstance(vrijednost, Vrijednost) and vrijednost.jedinica is Jedinica.TWIPS:
                assert formatiraj(vrijednost.iznos, vrijednost.jedinica) not in html


def test_neprovjerljivo_ima_prednost_u_sazetku():
    from dataclasses import replace

    from provjera.word.jezgra.nalaz import Dio, Lokacija, Nalaz, Status

    izvjestaj = _izvjestaj(VARIJANTE["jedna_sekcija"](54, PROFIL))
    neprovjerljivo = Nalaz("R-SEKCIJE", Status.NEPROVJERLJIVO, Lokacija(Dio.DOKUMENT), "R-SEKCIJE.bez_sekcija")
    html = html_sazetka(replace(izvjestaj, nalazi=izvjestaj.nalazi + (neprovjerljivo,)), "Vježba 1", "-")
    assert f"<td>{poruka('pravilo.R-SEKCIJE')}</td><td>{poruka('status.NEPROVJERLJIVO')}</td>" in html

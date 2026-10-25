"""Referentni skup (NFR-4): svaki primjer pada točno na pravilima iz ocekivano.toml."""

import base64
import random
import time
import tomllib
from pathlib import Path

import pytest
from alati.generator import MAPA, VARIJANTE, ispravan, zamijeni_u_zipu

from provjera.word.jezgra import profil
from provjera.word.jezgra.nalaz import KontekstProvjere, Status
from provjera.word.jezgra.pravila import REGISTAR
from provjera.word.jezgra.provjera import provjeri, spremnost, status_pravila
from provjera.zajednicko.ulaz import NAJVECA_VELICINA

KORIJEN = Path(__file__).resolve().parents[2]
OCEKIVANO = tomllib.loads((MAPA / "ocekivano.toml").read_text(encoding="utf-8"))
PROFIL = profil.ucitaj((KORIJEN / "profili" / "word" / "vjezba_1.toml").read_bytes())
UZORAK = KORIJEN / "samples" / "Lucija_Šimek_GiG_OG_Vjezba_1.docx"


def _padaju(sadrzaj: bytes, naziv: str = OCEKIVANO["naziv"]) -> set[str]:
    izvjestaj = provjeri(sadrzaj, PROFIL, KontekstProvjere(naziv, OCEKIVANO["rbr"], None, None))
    assert izvjestaj.odbijeno is None
    return {n.pravilo_id for n in izvjestaj.nalazi if n.status is not Status.PROSLO}


@pytest.mark.parametrize("ime", sorted(OCEKIVANO["primjeri"]))
def test_primjer_pada_tocno_na_ocekivanim_pravilima(ime):
    sadrzaj = (MAPA / f"{ime}.docx").read_bytes()
    assert _padaju(sadrzaj) == set(OCEKIVANO["primjeri"][ime]["padaju"])


@pytest.mark.parametrize("ime", sorted(VARIJANTE))
def test_generator_i_zapisani_primjeri_se_slazu(ime):
    """Svježe generiran primjer daje isti rezultat kao zapisani (generator nije zastario)."""
    sadrzaj = VARIJANTE[ime](OCEKIVANO["rbr"], PROFIL)
    assert _padaju(sadrzaj) == set(OCEKIVANO["primjeri"][ime]["padaju"])


def test_svaki_primjer_ima_zapis_i_datoteku():
    datoteke = {p.stem for p in MAPA.glob("*.docx")}
    assert datoteke == set(OCEKIVANO["primjeri"]) == set(VARIJANTE)


@pytest.mark.skipif(not UZORAK.exists(), reason="stvarni uzorak postoji samo lokalno")
def test_stvarni_uzorak_nema_naslovnicu_kao_sekciju():
    assert "R-SEKCIJE" in _padaju(UZORAK.read_bytes(), UZORAK.name)


@pytest.mark.skipif(not UZORAK.exists(), reason="stvarni uzorak postoji samo lokalno")
def test_stvarni_uzorak_prolazi_osnovni_tekst_unatoc_literaturi_u_list_paragraph():
    izvjestaj = provjeri(UZORAK.read_bytes(), PROFIL, KontekstProvjere(UZORAK.name, OCEKIVANO["rbr"], None, None))
    assert {n.status for n in izvjestaj.nalazi if n.pravilo_id == "R-TEKST"} == {Status.PROSLO}


# Pravila Vježbe 1 iz AD-4, redom izvođenja.
PRAVILA_AD4 = [
    "R-NAZIV", "R-SEKCIJE", "R-MARGINE", "R-TEKST", "R-NASLOVI", "R-SAZETAK",
    "R-LITERATURA", "R-STILOVI", "R-BROJ-STRANICE", "R-PROMJENE", "R-OKVIRI",
]


def test_ispravan_rad_prolazi_svih_11_pravila():
    assert list(REGISTAR) == PRAVILA_AD4
    izvjestaj = provjeri((MAPA / "ispravan.docx").read_bytes(), PROFIL,
                         KontekstProvjere(OCEKIVANO["naziv"], OCEKIVANO["rbr"], None, None))
    assert izvjestaj.odbijeno is None
    assert {n.pravilo_id for n in izvjestaj.nalazi} == set(PRAVILA_AD4)
    assert all(status_pravila(izvjestaj.nalazi, p) is Status.PROSLO for p in PRAVILA_AD4)
    assert spremnost(izvjestaj)


_ODLOMAK = '<w:p><w:r><w:t xml:space="preserve">{}</w:t></w:r></w:p>'


def _velik_dokument(cilj: int = int(9.6 * 1024 * 1024)) -> bytes:
    """Ispravan rad s oko 10 MB osnovnog teksta (NFR-1), sastavljen izravnim XML-om.

    Tekst je pseudoslučajan (base64 s razmacima), pa se sažima slično stvarnom tekstu.
    """
    slucajno = random.Random(20261014)
    # base64 se sažima na oko 3/4; mali višak pokriva XML oznake.
    znakova = int(cilj * 1.3)
    tekst = base64.b64encode(slucajno.randbytes(znakova * 3 // 4)).decode("ascii")
    tekst = tekst.translate(str.maketrans("+/", "  "))
    dijelovi = (tekst[i:i + 600] for i in range(0, len(tekst), 600))
    odlomci = "".join(_ODLOMAK.format(d) for d in dijelovi).encode("ascii")

    def umetni(xml: bytes) -> bytes:
        # Iza prvog odlomka osnovnog teksta (prvo pojavljivanje teksta poglavlja Uvod).
        sidro = xml.index(b"Ovo je osnovni tekst poglavlja")
        kraj = xml.index(b"</w:p>", sidro) + len(b"</w:p>")
        return xml[:kraj] + odlomci + xml[kraj:]

    return zamijeni_u_zipu(ispravan(OCEKIVANO["rbr"], PROFIL), {"word/document.xml": umetni})


def test_dokument_od_10_mb_provjerava_se_za_manje_od_10_s():
    sadrzaj = _velik_dokument()
    assert 9 * 1024 * 1024 < len(sadrzaj) <= NAJVECA_VELICINA
    pocetak = time.perf_counter()
    izvjestaj = provjeri(sadrzaj, PROFIL, KontekstProvjere(OCEKIVANO["naziv"], OCEKIVANO["rbr"], None, None))
    trajanje = time.perf_counter() - pocetak
    assert izvjestaj.odbijeno is None
    assert spremnost(izvjestaj)
    assert trajanje < 10, f"provjera je trajala {trajanje:.1f} s"

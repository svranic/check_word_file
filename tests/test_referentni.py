"""Referentni skup (NFR-4): svaki primjer pada točno na pravilima iz ocekivano.toml."""

import tomllib
from pathlib import Path

import pytest
from alati.generator import MAPA, VARIJANTE

from provjera.jezgra import profil
from provjera.jezgra.nalaz import KontekstProvjere, Status
from provjera.jezgra.provjera import provjeri

KORIJEN = Path(__file__).resolve().parents[1]
OCEKIVANO = tomllib.loads((MAPA / "ocekivano.toml").read_text(encoding="utf-8"))
PROFIL = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
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

"""Parsiranje .docx u DocModel i dodjela uloga (AD-3, AD-13).

Jedino mjesto u projektu koje dodiruje python-docx i lxml. Duljine su cijeli twipsi.
"""

import io
from dataclasses import dataclass
from enum import Enum

import docx
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.oxml.ns import qn

from provjera.jezgra.model.uloge import Uloga, uloge_sekcija

_EMU_PO_TWIPU = 635


class NeispravanDokument(Exception):
    """python-docx ne može otvoriti dokument koji je prošao ulaznu provjeru."""


class TipPocetka(Enum):
    SLJEDECA_STRANICA = "SLJEDECA_STRANICA"
    NEPREKINUTO = "NEPREKINUTO"
    PARNA = "PARNA"
    NEPARNA = "NEPARNA"
    NOVI_STUPAC = "NOVI_STUPAC"


_POCETAK = {
    WD_SECTION_START.NEW_PAGE: TipPocetka.SLJEDECA_STRANICA,
    WD_SECTION_START.CONTINUOUS: TipPocetka.NEPREKINUTO,
    WD_SECTION_START.EVEN_PAGE: TipPocetka.PARNA,
    WD_SECTION_START.ODD_PAGE: TipPocetka.NEPARNA,
    WD_SECTION_START.NEW_COLUMN: TipPocetka.NOVI_STUPAC,
}


@dataclass(frozen=True)
class Sekcija:
    """Postavke stranice jedne sekcije; ``None`` znači da vrijednost nije zapisana."""

    indeks: int
    uloga: Uloga
    gore: int | None
    dolje: int | None
    lijevo: int | None
    desno: int | None
    gutter: int | None
    sirina: int | None
    visina: int | None
    pejzazno: bool
    pocetak: TipPocetka


@dataclass(frozen=True)
class DocModel:
    sekcije: tuple[Sekcija, ...] = ()
    zrcalne_margine: bool = False


def _twips(duljina: int | None) -> int | None:
    return None if duljina is None else round(duljina / _EMU_PO_TWIPU)


def _sekcija(indeks: int, uloga: Uloga, s) -> Sekcija:
    sirina, visina = _twips(s.page_width), _twips(s.page_height)
    # Word raspoređuje stranicu po dimenzijama; w:orient vrijedi samo kad dimenzije nedostaju.
    if sirina is not None and visina is not None:
        pejzazno = sirina > visina
    else:
        pejzazno = s.orientation == WD_ORIENTATION.LANDSCAPE
    return Sekcija(
        indeks=indeks,
        uloga=uloga,
        gore=_twips(s.top_margin),
        dolje=_twips(s.bottom_margin),
        lijevo=_twips(s.left_margin),
        desno=_twips(s.right_margin),
        gutter=_twips(s.gutter),
        sirina=sirina,
        visina=visina,
        pejzazno=pejzazno,
        pocetak=_POCETAK.get(s.start_type, TipPocetka.SLJEDECA_STRANICA),
    )


def _zrcalne_margine(dokument) -> bool:
    element = dokument.settings.element.find(qn("w:mirrorMargins"))
    if element is None:
        return False
    return element.get(qn("w:val"), "true").lower() not in ("false", "0", "off")


def procitaj(sadrzaj: bytes) -> DocModel:
    """Parsira dokument točno jednom; ``sadrzaj`` je već prošao ``ulaz.provjeri_ulaz``."""
    # Samo neuspjelo otvaranje paketa znači oštećen dokument; greške pri čitanju
    # pojedinih postavki idu pozivatelju, koji pogođena pravila čini neprovjerljivima.
    try:
        dokument = docx.Document(io.BytesIO(sadrzaj))
    except MemoryError:
        raise
    except Exception as greska:  # noqa: BLE001 — python-docx baca razne tipove za nečitljiv paket
        raise NeispravanDokument(type(greska).__name__) from greska
    sekcije = list(dokument.sections)
    uloge = uloge_sekcija(len(sekcije))
    return DocModel(
        sekcije=tuple(
            _sekcija(i + 1, uloga, s) for i, (uloga, s) in enumerate(zip(uloge, sekcije))
        ),
        zrcalne_margine=_zrcalne_margine(dokument),
    )

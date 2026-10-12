"""Generator sintetskog referentnog skupa Vježbe 1: ispravan rad i pokvarene varijante.

Pokretanje: ``uv run python tests/alati/generator.py`` zapisuje .docx primjere u
``tests/referentni/vjezba_1/``. Imena u dokumentima su izmišljena.
"""

import io
from collections.abc import Callable
from pathlib import Path

import docx
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.oxml import OxmlElement
from docx.shared import Mm, Twips

from provjera.jezgra import formula
from provjera.jezgra.jedinice import mm_u_twips
from provjera.jezgra.profil import Profil, ucitaj

KORIJEN = Path(__file__).resolve().parents[2]
MAPA = KORIJEN / "tests" / "referentni" / "vjezba_1"


def _a4(sekcija) -> None:
    sekcija.orientation = WD_ORIENTATION.PORTRAIT
    sekcija.page_width = Mm(210)
    sekcija.page_height = Mm(297)
    sekcija.gutter = 0


def _margine(sekcija, gore: int, dolje: int, lijevo: int, desno: int) -> None:
    """Margine u twipsima, točno kako ih Word zapisuje."""
    sekcija.top_margin = Twips(gore)
    sekcija.bottom_margin = Twips(dolje)
    sekcija.left_margin = Twips(lijevo)
    sekcija.right_margin = Twips(desno)


def _spremi(dokument) -> bytes:
    spremnik = io.BytesIO()
    dokument.save(spremnik)
    return spremnik.getvalue()


def _tijelo(rbr: int, profil: Profil) -> dict[str, int]:
    return formula.margine(rbr, profil.formula).u_twips()


def _dokument(rbr: int, profil: Profil, jedna_sekcija: bool = False):
    dokument = docx.Document()
    naslovnica = dokument.sections[0]
    _a4(naslovnica)
    tijelo = _tijelo(rbr, profil)
    if jedna_sekcija:
        _margine(naslovnica, **tijelo)
        dokument.add_paragraph("Ana Horvat, 0000000000")
        dokument.add_paragraph("Uvod")
        return dokument
    _margine(naslovnica, *(mm_u_twips(profil.formula.naslovnica),) * 4)
    dokument.add_paragraph("Ana Horvat, 0000000000")
    sekcija = dokument.add_section(WD_SECTION_START.NEW_PAGE)
    _a4(sekcija)
    _margine(sekcija, **tijelo)
    dokument.add_paragraph("Uvod")
    return dokument


def ispravan(rbr: int, profil: Profil) -> bytes:
    return _spremi(_dokument(rbr, profil))


def _izmijeni(promjena: Callable) -> Callable[[int, Profil], bytes]:
    def varijanta(rbr: int, profil: Profil) -> bytes:
        dokument = _dokument(rbr, profil)
        promjena(dokument, rbr, profil)
        return _spremi(dokument)

    return varijanta


def _neprekinuto(dokument, rbr, profil):
    dokument.sections[1].start_type = WD_SECTION_START.CONTINUOUS


def _krive_margine_tijela(dokument, rbr, profil):
    dokument.sections[1].left_margin = Twips(_tijelo(rbr, profil)["lijevo"] + mm_u_twips(1))


def _krive_margine_naslovnice(dokument, rbr, profil):
    dokument.sections[0].top_margin = Mm(30)


def _unutar_tolerancije(dokument, rbr, profil):
    tolerancija = profil.tolerancije.margine
    dokument.sections[1].right_margin = Twips(_tijelo(rbr, profil)["desno"] + tolerancija)


def _letter(dokument, rbr, profil):
    for sekcija in dokument.sections:
        sekcija.page_width, sekcija.page_height = Mm(215.9), Mm(279.4)


def _pejzazno(dokument, rbr, profil):
    sekcija = dokument.sections[1]
    sekcija.orientation = WD_ORIENTATION.LANDSCAPE
    sekcija.page_width, sekcija.page_height = sekcija.page_height, sekcija.page_width


def _gutter(dokument, rbr, profil):
    dokument.sections[1].gutter = Mm(5)


def _zrcalne(dokument, rbr, profil):
    dokument.settings.element.append(OxmlElement("w:mirrorMargins"))


VARIJANTE: dict[str, Callable[[int, Profil], bytes]] = {
    "ispravan": ispravan,
    "jedna_sekcija": lambda rbr, profil: _spremi(_dokument(rbr, profil, jedna_sekcija=True)),
    "neprekinuti_prijelom": _izmijeni(_neprekinuto),
    "krive_margine_tijela": _izmijeni(_krive_margine_tijela),
    "krive_margine_naslovnice": _izmijeni(_krive_margine_naslovnice),
    "unutar_tolerancije": _izmijeni(_unutar_tolerancije),
    "letter": _izmijeni(_letter),
    "pejzazno": _izmijeni(_pejzazno),
    "gutter": _izmijeni(_gutter),
    "zrcalne": _izmijeni(_zrcalne),
}


def zapisi(rbr: int = 54) -> list[Path]:
    profil = ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
    MAPA.mkdir(parents=True, exist_ok=True)
    zapisane = []
    for ime, varijanta in VARIJANTE.items():
        putanja = MAPA / f"{ime}.docx"
        putanja.write_bytes(varijanta(rbr, profil))
        zapisane.append(putanja)
    return zapisane


if __name__ == "__main__":
    for putanja in zapisi():
        print(putanja.relative_to(KORIJEN).as_posix())

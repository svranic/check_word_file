"""Naziv datoteke (AD-7, FR-16): jedini izvor kanonskog naziva i obrasca."""

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

# Dio imena čine samo slova; isti uvjet koristi i obrazac naziva.
_SLOVA = r"[^\W\d_]+"


def nfc(tekst: str) -> str:
    return unicodedata.normalize("NFC", tekst)


def _spoji(tekst: str) -> str:
    """Dijelovi odvojeni bilo čim osim slova (razmak, spojnica, apostrof) spajaju se."""
    dijelovi = re.findall(_SLOVA, nfc(tekst))
    if not dijelovi:
        raise ValueError("ime i prezime moraju sadržavati barem jedno slovo")
    return "".join(
        d[0].upper() + (d[1:].lower() if d.isupper() else d[1:]) for d in dijelovi
    )


def kanonski(ime: str, prezime: str, profil: "Profil") -> str:
    """„Ana Marija“ + „Horvat-Kovač“ → ``AnaMarija_HorvatKovač<sufiks><nastavak>``."""
    nd = profil.naziv_datoteke
    return nfc(f"{_spoji(ime)}_{_spoji(prezime)}{nd.sufiks}{nd.nastavak}")


def odgovara_obrascu(naziv: str, profil: "Profil") -> bool:
    """Dva dijela samo od slova odvojena ``_``, zatim točno sufiks i nastavak."""
    nd = profil.naziv_datoteke
    obrazac = f"{_SLOVA}_{_SLOVA}" + re.escape(nfc(nd.sufiks + nd.nastavak))
    return re.fullmatch(obrazac, nfc(naziv)) is not None

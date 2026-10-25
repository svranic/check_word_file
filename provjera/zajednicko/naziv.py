"""Naziv datoteke (AD-7, FR-16): jedini izvor kanonskog naziva i obrasca."""

import re
import unicodedata
from typing import Protocol


class _NazivDatoteke(Protocol):
    sufiks: str
    nastavak: str


class Profil(Protocol):
    """Bilo koji profil vježbe (Word ili Excel) s odjeljkom ``naziv_datoteke``."""

    @property
    def naziv_datoteke(self) -> _NazivDatoteke: ...


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


def kanonski(ime: str, prezime: str, profil: Profil) -> str:
    """„Ana Marija“ + „Horvat-Kovač“ → ``AnaMarija_HorvatKovač<sufiks><nastavak>``."""
    nd = profil.naziv_datoteke
    return nfc(f"{_spoji(ime)}_{_spoji(prezime)}{nd.sufiks}{nd.nastavak}")


def odgovara_obrascu(naziv: str, profil: Profil) -> bool:
    """Dva dijela samo od slova odvojena ``_``, zatim točno sufiks i nastavak."""
    nd = profil.naziv_datoteke
    obrazac = f"{_SLOVA}_{_SLOVA}" + re.escape(nfc(nd.sufiks + nd.nastavak))
    return re.fullmatch(obrazac, nfc(naziv)) is not None


# Sufiks kopije koji dodaju preglednici i Windows: „rad (1).docx“.
_SUFIKS_KOPIJE = re.compile(r"(\s*\(\d+\))+$")
_NASTAVAK = re.compile(r"\.[^.\s]{1,5}$")


def bez_dijakritika(tekst: str) -> str:
    """„Đurđa Šćekić“ → „Durda Scekic“; ``đ`` se zamjenjuje ručno jer ga NFKD ne rastavlja."""
    rastavljeno = unicodedata.normalize("NFKD", tekst.replace("đ", "d").replace("Đ", "D"))
    return "".join(z for z in rastavljeno if not unicodedata.combining(z))


def kljuc_uparivanja(tekst: str) -> str:
    """Ključ koji zanemaruje nastavak, sufiks „ (1)“, dijakritike i velika i mala slova."""
    osnova = _SUFIKS_KOPIJE.sub("", _NASTAVAK.sub("", nfc(tekst).strip()))
    return bez_dijakritika(osnova).casefold()


def rijeci(tekst: str) -> tuple[str, ...]:
    """Riječi samo od slova, bez dijakritika i malim slovima (ime podmape, ime studenta)."""
    return tuple(r.casefold() for r in re.findall(_SLOVA, bez_dijakritika(nfc(tekst))))

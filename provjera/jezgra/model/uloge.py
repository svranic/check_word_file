"""Uloge (AD-13): jedino mjesto koje klasificira sekcije i odlomke; pravila samo filtriraju po ulozi."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Uloga(Enum):
    NASLOVNICA = "NASLOVNICA"
    TIJELO = "TIJELO"


class UlogaOdlomka(Enum):
    NASLOVNICA = "NASLOVNICA"
    NASLOV_SAZETKA = "NASLOV_SAZETKA"
    SAZETAK = "SAZETAK"
    NASLOV_POGLAVLJA = "NASLOV_POGLAVLJA"
    OSNOVNI_TEKST = "OSNOVNI_TEKST"
    NASLOV_LITERATURE = "NASLOV_LITERATURE"
    LITERATURA = "LITERATURA"
    PRAZNO = "PRAZNO"
    TABLICA = "TABLICA"
    OSTALO = "OSTALO"


class NaziviUloga(BaseModel):
    """Nazivi iz odjeljka ``[uloge]`` profila (npr. „Sažetak“, „Literatura“, poglavlja)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sazetak: str = Field(min_length=1)
    literatura: str = Field(min_length=1)
    poglavlja: tuple[str, ...] = Field(min_length=1)


@dataclass(frozen=True)
class ZnacajkeOdlomka:
    """Činjenice o odlomku koje model predaje klasifikaciji (bez XML-a)."""

    uloga_sekcije: Uloga
    kanonski_stil: str
    tekst: str
    u_tablici: bool = False
    u_sadrzaju: bool = False
    ima_sliku: bool = False
    numeriran: bool = False


def uloge_sekcija(broj: int) -> tuple[Uloga, ...]:
    """Uz barem dvije sekcije prva je naslovnica; jedina sekcija je tijelo."""
    if broj >= 2:
        return (Uloga.NASLOVNICA,) + (Uloga.TIJELO,) * (broj - 1)
    return (Uloga.TIJELO,) * broj


# Broj mora završiti točkom ili razmakom: „3D modeliranje“ nije ručni broj.
_RUCNI_BROJ = re.compile(r"^\s*\d+(?:\.\d+)*(?:\.\s*|\s+)")
_ZAVRSNA_INTERPUNKCIJA = re.compile(r"[\s.,:;!?…\-–—]+$")
_RAZMACI = re.compile(r"\s+")


def normaliziraj_naziv(tekst: str) -> str:
    """Usporedivi oblik naziva: bez velikih slova, dijakritika (i đ) i završne interpunkcije."""
    tekst = tekst.casefold().replace("đ", "d")
    tekst = "".join(
        z for z in unicodedata.normalize("NFKD", tekst) if not unicodedata.combining(z)
    )
    tekst = _RAZMACI.sub(" ", tekst).strip()
    return _ZAVRSNA_INTERPUNKCIJA.sub("", tekst)


def bez_rucnog_broja(tekst: str) -> str:
    """Tekst bez ručno upisanog broja na početku („1. Uvod“ → „Uvod“)."""
    return _RUCNI_BROJ.sub("", tekst, count=1)


def ima_rucni_broj(tekst: str) -> bool:
    """Počinje li tekst ručno upisanim brojem („1.“, „2.1“); isti regex kao za uloge."""
    return _RUCNI_BROJ.match(tekst) is not None


_TOC = re.compile(r"^TOC(?:\d|Heading$)")
_OPIS_SLIKE = {"Caption"}
_POPIS = {"ListParagraph"}
_NASLOV_POGLAVLJA = "Heading1"


def _je_ostalo(z: ZnacajkeOdlomka) -> bool:
    return (
        bool(_TOC.match(z.kanonski_stil))
        or z.u_sadrzaju
        or z.kanonski_stil in _OPIS_SLIKE
        or (z.ima_sliku and not z.tekst.strip())
    )


def uloge_odlomaka(
    znacajke: Sequence[ZnacajkeOdlomka], nazivi: NaziviUloga
) -> tuple[UlogaOdlomka, ...]:
    """Svakom odlomku točno jedna uloga, redom prednosti iz AD-13."""
    sazetak = normaliziraj_naziv(nazivi.sazetak)
    literatura = normaliziraj_naziv(nazivi.literatura)
    poglavlja = {normaliziraj_naziv(p) for p in nazivi.poglavlja} | {literatura}

    uloge: list[UlogaOdlomka] = []
    vidjeno_poglavlje = False
    u_literaturi = False
    for z in znacajke:
        naziv = normaliziraj_naziv(bez_rucnog_broja(z.tekst))
        if z.uloga_sekcije is Uloga.NASLOVNICA:
            uloga = UlogaOdlomka.NASLOVNICA
        elif z.u_tablici:
            uloga = UlogaOdlomka.TABLICA
        elif not z.tekst.strip() and not z.ima_sliku:
            uloga = UlogaOdlomka.PRAZNO
        elif _je_ostalo(z):
            uloga = UlogaOdlomka.OSTALO
        elif naziv == sazetak:
            # Ispred naslova poglavlja: „Sažetak“ u Heading 1 nije poglavlje.
            uloga = UlogaOdlomka.NASLOV_SAZETKA
        elif z.kanonski_stil == _NASLOV_POGLAVLJA or naziv in poglavlja:
            vidjeno_poglavlje = True
            u_literaturi = naziv == literatura
            uloga = UlogaOdlomka.NASLOV_LITERATURE if u_literaturi else UlogaOdlomka.NASLOV_POGLAVLJA
        elif not vidjeno_poglavlje:
            uloga = UlogaOdlomka.SAZETAK
        elif u_literaturi:
            uloga = UlogaOdlomka.LITERATURA
        elif z.numeriran or z.kanonski_stil in _POPIS:
            uloga = UlogaOdlomka.OSTALO
        else:
            uloga = UlogaOdlomka.OSNOVNI_TEKST
        uloge.append(uloga)
    return tuple(uloge)

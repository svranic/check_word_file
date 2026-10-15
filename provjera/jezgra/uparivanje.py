"""Povezivanje predane datoteke sa studentom (priča 4.2, FR26): čiste funkcije bez I/O-a.

Redoslijed: točan naziv → isti ključ uparivanja → ime podmape → JMBAG s naslovnice →
nepovezano. Korak s više kandidata ne odlučuje, nego ih predaje JMBAG-u.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath
from typing import Protocol

from provjera.jezgra import naziv
from provjera.jezgra.nalaz import NacinUparivanja
from provjera.jezgra.profil import Profil


class StudentPopisa(Protocol):
    rbr: int
    jmbag: str
    ime: str
    prezime: str
    aktivan: bool


# Bolji način ima manji broj: od više datoteka istog studenta ostaje najbolja.
REDOSLIJED = (
    NacinUparivanja.TOCAN,
    NacinUparivanja.PRIBLIZAN,
    NacinUparivanja.PODMAPA,
    NacinUparivanja.JMBAG,
)


class RazlogNepovezanosti(StrEnum):
    BEZ_PODUDARANJA = "bez_podudaranja"
    DVOSMISLENO = "dvosmisleno"
    JMBAG_NIJE_NA_POPISU = "jmbag_nije_na_popisu"
    VISE_JMBAGOVA = "vise_jmbagova"
    VISESTRUKO = "visestruko"
    NEAKTIVAN = "neaktivan"


@dataclass(frozen=True)
class Uparivanje:
    student: StudentPopisa
    nacin: NacinUparivanja
    ocekivani_naziv: str


@dataclass(frozen=True)
class Nepovezano:
    razlog: RazlogNepovezanosti
    kandidati: tuple[StudentPopisa, ...] = ()


Rezultat = Uparivanje | Nepovezano


def _jedan_ili_kandidati(
    pogoci: list[StudentPopisa],
) -> StudentPopisa | tuple[StudentPopisa, ...] | None:
    if len(pogoci) == 1:
        return pogoci[0]
    return tuple(pogoci) or None


def _po_podmapi(
    mape: Sequence[str], studenti: Sequence[StudentPopisa]
) -> StudentPopisa | tuple[StudentPopisa, ...] | None:
    """Najbliža mapa (od datoteke prema korijenu) čije riječi sadrže ime i prezime."""
    for mapa in reversed(mape):
        rijeci = set(naziv.rijeci(mapa))
        pogoci = [
            s for s in studenti
            if (trazene := naziv.rijeci(f"{s.ime} {s.prezime}")) and set(trazene) <= rijeci
        ]
        if pogoci:
            # „Ana Marija Horvat“ ima prednost pred „Ana Horvat“ kad mapa sadrži sve tri riječi.
            najvise = max(len(set(naziv.rijeci(f"{s.ime} {s.prezime}"))) for s in pogoci)
            return _jedan_ili_kandidati(
                [s for s in pogoci if len(set(naziv.rijeci(f"{s.ime} {s.prezime}"))) == najvise]
            )
    return None


def _po_jmbagu(
    brojevi: frozenset[str],
    studenti: Sequence[StudentPopisa],
    kandidati: tuple[StudentPopisa, ...] | None,
) -> StudentPopisa | Nepovezano:
    skup = kandidati if kandidati is not None else studenti
    na_popisu = [s for s in skup if s.jmbag in brojevi]
    if len(na_popisu) == 1:
        return na_popisu[0]
    if kandidati is not None:
        return Nepovezano(RazlogNepovezanosti.DVOSMISLENO, kandidati)
    if na_popisu:
        return Nepovezano(RazlogNepovezanosti.VISE_JMBAGOVA, tuple(na_popisu))
    if brojevi:
        return Nepovezano(RazlogNepovezanosti.JMBAG_NIJE_NA_POPISU)
    return Nepovezano(RazlogNepovezanosti.BEZ_PODUDARANJA)


def upari(
    naziv_datoteke: str,
    mape: Sequence[str],
    studenti: Sequence[StudentPopisa],
    profil: Profil,
    brojevi: Callable[[], frozenset[str]],
) -> Rezultat:
    """Povezuje datoteku sa studentom; ``mape`` su mape od korijena predaja do datoteke.

    ``brojevi`` vraća 10-znamenkaste brojeve s naslovnice i poziva se samo kad koraci
    1–3 nisu odlučili. Datoteka neaktivnog studenta je nepovezana.
    """
    kanonski: dict[int, str] = {}
    for s in studenti:
        try:
            kanonski[s.rbr] = naziv.kanonski(s.ime, s.prezime, profil)
        except ValueError:
            continue  # ime bez slova nema kanonski naziv; student se može naći po JMBAG-u
    imenovani = [s for s in studenti if s.rbr in kanonski]
    osnova = naziv.nfc(PurePath(naziv_datoteke).stem)
    nastavak = profil.naziv_datoteke.nastavak

    def bez_nastavka(tekst: str) -> str:
        return tekst[: -len(nastavak)] if tekst.endswith(nastavak) else tekst

    kljuc = naziv.kljuc_uparivanja(naziv_datoteke)
    tocni = [s for s in imenovani if bez_nastavka(kanonski[s.rbr]) == osnova]
    priblizni = [s for s in imenovani if naziv.kljuc_uparivanja(kanonski[s.rbr]) == kljuc]

    def povezan(student: StudentPopisa, nacin: NacinUparivanja) -> Rezultat:
        if not student.aktivan:
            return Nepovezano(RazlogNepovezanosti.NEAKTIVAN, (student,))
        # Student bez kanonskog naziva (nađen po JMBAG-u) ne može proći R-NAZIV.
        return Uparivanje(student, nacin, kanonski.get(student.rbr, ""))

    kandidati: tuple[StudentPopisa, ...] | None = None
    for nacin, pogoci in ((NacinUparivanja.TOCAN, tocni), (NacinUparivanja.PRIBLIZAN, priblizni)):
        if len(pogoci) == 1:
            return povezan(pogoci[0], nacin)
        if pogoci:
            kandidati = tuple(pogoci)
            break
    if kandidati is None:
        po_mapi = _po_podmapi(mape, studenti)
        if isinstance(po_mapi, tuple):
            kandidati = po_mapi
        elif po_mapi is not None:
            return povezan(po_mapi, NacinUparivanja.PODMAPA)
    po_jmbagu = _po_jmbagu(brojevi(), studenti, kandidati)
    if isinstance(po_jmbagu, Nepovezano):
        return po_jmbagu
    return povezan(po_jmbagu, NacinUparivanja.JMBAG)


def razrijesi_visestruke(
    rezultati: Sequence[Rezultat], docx: Sequence[bool] | None = None
) -> list[Rezultat]:
    """Studentu ostaje najbolja datoteka; ostale su višestruke.

    Prednost ima .docx (``docx[i]``) pred drugim formatom, zatim bolji način, pa prva po redu.
    """
    docx = [True] * len(rezultati) if docx is None else docx

    def rang(i: int) -> tuple[bool, int]:
        return (not docx[i], REDOSLIJED.index(rezultati[i].nacin))

    najbolji: dict[int, int] = {}
    for i, r in enumerate(rezultati):
        if not isinstance(r, Uparivanje):
            continue
        prethodni = najbolji.get(r.student.rbr)
        if prethodni is None or rang(i) < rang(prethodni):
            najbolji[r.student.rbr] = i
    return [
        Nepovezano(RazlogNepovezanosti.VISESTRUKO, (r.student,))
        if isinstance(r, Uparivanje) and najbolji[r.student.rbr] != i
        else r
        for i, r in enumerate(rezultati)
    ]

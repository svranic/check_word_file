"""Batch provjera (priče 4.1 i 4.2, FR25, FR26, AD-9): mapa predaja → povezivanje → ``provjeri()``.

Adapter samo čita datoteke i poziva jezgru; ništa ne piše u mapu predaja i ništa ne
šalje na mrežu. Logira se samo broj datoteka, nikad naziv ni ime.
"""

import logging
import os
import stat
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path

from provjera.adapteri.popis import GreskaIzdanog, Student, procitaj_izdano
from provjera.jezgra import formula, model, spremnost, ulaz, uparivanje
from provjera.jezgra.nalaz import KontekstProvjere, NacinUparivanja
from provjera.jezgra.predaje import RedakDatoteke, RezultatBatcha
from provjera.jezgra.profil import Profil, verzija
from provjera.jezgra.provjera import provjeri

log = logging.getLogger(__name__)

SISTEMSKE_DATOTEKE = frozenset({"thumbs.db", "desktop.ini"})
PREFIKSI_PRESKAKANJA = ("~$", ".")
_SKRIVENO = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 4)
# Spremnost za objavu traži i samoprovjeru; batch nakon roka ne (odluka 2026-10-15).
_PREFIKS_SAMOPROVJERE = "spremnost.samoprovjera_"

Napredak = Callable[[int, int], None]


class StanjeOtiska(Enum):
    ISTI = "ISTI"
    RAZLICIT = "RAZLICIT"
    NEMA_IZDANOG = "NEMA_IZDANOG"
    NECITLJIVO = "NECITLJIVO"


def stanje_otiska(profil: Profil, mapa_vjezbe: Path) -> StanjeOtiska:
    """Jesu li margine iste kao u izdanom PDF-u sa svojstvima (AD-9)."""
    try:
        izdano = procitaj_izdano(mapa_vjezbe)
    except (GreskaIzdanog, OSError):
        return StanjeOtiska.NECITLJIVO
    if izdano is None:
        return StanjeOtiska.NEMA_IZDANOG
    if izdano.formula_otisak != formula.otisak(profil.formula):
        return StanjeOtiska.RAZLICIT
    return StanjeOtiska.ISTI


def problemi_konfiguracije(
    profil: Profil, studenti: Sequence[Student] | None
) -> tuple[spremnost.Problem, ...]:
    """Problemi profila i zamrznutog popisa koji sprječavaju batch (FR5)."""
    rbrovi = None if studenti is None else [s.rbr for s in studenti]
    aktivnih = 0 if studenti is None else sum(s.aktivan for s in studenti)
    pregled = spremnost.pregled(profil, rbrovi, aktivnih, None)
    return tuple(p for p in pregled.problemi if not p.kljuc.startswith(_PREFIKS_SAMOPROVJERE))


def _preskace_se(unos: os.DirEntry) -> bool:
    ime = unos.name
    if ime.startswith(PREFIKSI_PRESKAKANJA) or ime.lower() in SISTEMSKE_DATOTEKE:
        return True
    if unos.is_symlink() or unos.is_junction():
        return True
    try:
        atributi = getattr(unos.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return False  # datoteka nestala ili zaključana: čitanje će je označiti neuspjelom
    return bool(atributi & _SKRIVENO)


def unutar(mapa: Path, druga: Path) -> bool:
    """Je li ``mapa`` jednaka mapi ``druga`` ili unutar nje."""
    return any(_isto(m, druga) for m in (mapa, *mapa.parents))


def _isto(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def pronadi_datoteke(mapa: Path, izuzeto: Path | None = None) -> tuple[Path, ...]:
    """Sve datoteke u mapi i podmapama, sortirano po relativnoj putanji.

    Preskaču se Wordove privremene, skrivene i sistemske datoteke i mape, simboličke
    poveznice i junctioni te mapa ``izuzeto`` (podatkovna mapa). Nečitljiva podmapa baca
    ``OSError``: bolje stati nego tiho izgubiti predaje.
    """
    if izuzeto is not None and unutar(mapa, izuzeto):
        return ()
    pronadene: list[Path] = []
    na_redu = [mapa]
    while na_redu:
        trenutna = na_redu.pop()
        with os.scandir(trenutna) as unosi:
            for unos in unosi:
                if _preskace_se(unos):
                    continue
                putanja = Path(unos.path)
                if unos.is_dir(follow_symlinks=False):
                    if izuzeto is None or not _isto(putanja, izuzeto):
                        na_redu.append(putanja)
                elif unos.is_file(follow_symlinks=False):
                    pronadene.append(putanja)
    return tuple(sorted(pronadene, key=lambda p: p.relative_to(mapa).parts))


def _procitaj(putanja: Path) -> bytes:
    """Najviše jedan bajt iznad granice, da jezgra sama odbije preveliku datoteku."""
    with open(putanja, "rb") as datoteka:
        return datoteka.read(ulaz.NAJVECA_VELICINA + 1)


def _obradi(
    putanja: Path, relativno: str, student: Student, nacin: NacinUparivanja,
    ocekivani: str, profil: Profil,
) -> RedakDatoteke:
    try:
        sadrzaj = _procitaj(putanja)
        kontekst = KontekstProvjere(putanja.name, student.rbr, ocekivani, nacin)
        izvjestaj = provjeri(sadrzaj, profil, kontekst)
    except Exception as greska:  # noqa: BLE001 — jedna datoteka ne smije zaustaviti ostale
        log.warning("batch: neuspjela obrada datoteke (%s)", type(greska).__name__)
        return RedakDatoteke(relativno, student, nacin, greska=type(greska).__name__)
    return RedakDatoteke(relativno, student, nacin, izvjestaj)


def _brojevi_naslovnice(putanja: Path, profil: Profil) -> frozenset[str]:
    """JMBAG-ovi s naslovnice; samo za .docx koji prolazi sigurnosnu provjeru ulaza.

    Nijedna greška ovdje ne zaustavlja batch: datoteka tada samo nema JMBAG.
    """
    try:
        sadrzaj = _procitaj(putanja)
        if ulaz.provjeri_ulaz(putanja.name, sadrzaj) is not None:
            return frozenset()
        return model.brojevi_naslovnice(sadrzaj, profil.uloge)
    except Exception as greska:  # noqa: BLE001 — provjera datoteke će prijaviti grešku
        log.warning("batch: naslovnica nije pročitana (%s)", type(greska).__name__)
        return frozenset()


def pokreni(
    mapa: Path,
    profil: Profil,
    studenti: Sequence[Student],
    napredak: Napredak | None = None,
    izuzeto: Path | None = None,
) -> RezultatBatcha:
    """Povezuje i provjerava sve datoteke u ``mapa``; validaciju i otisak radi pozivatelj."""
    datoteke = pronadi_datoteke(mapa, izuzeto)
    relativne = [p.relative_to(mapa) for p in datoteke]
    uparivanja = uparivanje.razrijesi_visestruke(
        [
            uparivanje.upari(
                p.name,
                [m.name for m in reversed(r.parents[:-1])],
                studenti,
                profil,
                lambda p=p: _brojevi_naslovnice(p, profil),
            )
            for p, r in zip(datoteke, relativne)
        ],
        [p.name.lower().endswith(".docx") for p in datoteke],
    )
    retci: list[RedakDatoteke] = []
    for i, (putanja, relativna, u) in enumerate(zip(datoteke, relativne, uparivanja), start=1):
        relativno = relativna.as_posix()
        if isinstance(u, uparivanje.Nepovezano):
            retci.append(RedakDatoteke(relativno, nepovezano=u.razlog, kandidati=u.kandidati))
        else:
            retci.append(_obradi(putanja, relativno, u.student, u.nacin, u.ocekivani_naziv, profil))
        if napredak is not None:
            napredak(i, len(datoteke))
    log.info("batch: obrađeno %d datoteka", len(datoteke))
    return RezultatBatcha(verzija(profil), tuple(studenti), tuple(retci))

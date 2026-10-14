"""ISVU popis studenata (AD-1): jedini čitač ISVU ``.xlsx`` izvoza (openpyxl).

``ucitaj_isvu`` sam pronalazi zaglavlje ispod metapodataka izvoza, normalizira
vrijednosti i vraća studente zajedno s potpunim popisom pogrešaka po retku.
Osobni podaci se ne zapisuju u log.
"""

import io
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import openpyxl

from provjera.jezgra import rbr as rbr_unos
from provjera.jezgra.naziv import nfc

log = logging.getLogger(__name__)

STUPAC_RBR = "Rbr."
STUPAC_JMBAG = "JMBAG"
STUPAC_IME = "Ime"
STUPAC_PREZIME = "Prezime"
STUPAC_STATUS = "Status upisa"
STUPCI = (STUPAC_RBR, STUPAC_JMBAG, STUPAC_IME, STUPAC_PREZIME, STUPAC_STATUS)
NAJVISE_REDAKA_DO_ZAGLAVLJA = 50
ZNAMENKE_JMBAG = 10
PREFIKS_ISPISAN = "ispisan"


@dataclass(frozen=True)
class Student:
    rbr: int
    jmbag: str
    ime: str
    prezime: str
    aktivan: bool


@dataclass(frozen=True)
class GreskaRetka:
    """Pogreška popisa; ``redak`` je broj retka u Excelu (1-bazirano) ili ``None`` za cijelu datoteku."""

    redak: int | None
    poruka_kljuc: str
    parametri: Mapping[str, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parametri", MappingProxyType(dict(self.parametri)))


@dataclass(frozen=True)
class UcitaniPopis:
    studenti: tuple[Student, ...]
    greske: tuple[GreskaRetka, ...]

    @property
    def moze_zamrznuti(self) -> bool:
        return not self.greske

    @property
    def broj_neaktivnih(self) -> int:
        return sum(not s.aktivan for s in self.studenti)


def _kljuc_stupca(vrijednost: object) -> str:
    return " ".join(nfc(str(vrijednost)).split()).casefold() if vrijednost is not None else ""


def _tekst(vrijednost: object) -> str:
    """Tekst ćelije bez rubnih i višestrukih razmaka, u NFC obliku."""
    if vrijednost is None:
        return ""
    return " ".join(nfc(str(vrijednost)).split())


def _cijeli_broj(vrijednost: object) -> int | None:
    """Brojčana ćelija s cijelim brojem (``78`` ili ``78.0``); inače ``None``."""
    if isinstance(vrijednost, bool):
        return None
    if isinstance(vrijednost, int):
        return vrijednost
    if isinstance(vrijednost, float) and vrijednost.is_integer():
        return int(vrijednost)
    return None


def _rbr(vrijednost: object) -> int | None:
    if isinstance(vrijednost, (int, float)) and not isinstance(vrijednost, bool):
        broj = _cijeli_broj(vrijednost)
        # Broj ide kroz isti tumač kao tekst, pa vrijede ista ograničenja (pozitivan, ≤ 9 znamenki).
        vrijednost = str(broj) if broj is not None else "-"
    rezultat = rbr_unos.parsiraj("" if vrijednost is None else str(vrijednost))
    return rezultat if isinstance(rezultat, int) else None


def _jmbag(vrijednost: object) -> str:
    """Tekst i broj normaliziraju se jednako: bez razmaka, samo znamenke nadopunjene do 10."""
    broj = _cijeli_broj(vrijednost)
    tekst = str(broj) if broj is not None else _tekst(vrijednost).replace(" ", "")
    if tekst.isascii() and tekst.isdigit():
        return tekst.zfill(ZNAMENKE_JMBAG)
    return tekst


def _jmbag_valjan(jmbag: str) -> bool:
    return len(jmbag) == ZNAMENKE_JMBAG and jmbag.isascii() and jmbag.isdigit()


def _ucitaj_listove(sadrzaj: bytes) -> list[list[tuple[object, ...]]] | None:
    """Retci svakog radnog lista, redom kojim su listovi u knjizi."""
    try:
        knjiga = openpyxl.load_workbook(io.BytesIO(sadrzaj), data_only=True)
        return [list(list_.iter_rows(values_only=True)) for list_ in knjiga.worksheets]
    except Exception:  # noqa: BLE001 — svaka pogreška čitanja znači nečitljivu datoteku
        log.info("ISVU izvoz nije čitljiv .xlsx")
        return None


def _pronadi_zaglavlje(
    retci: list[tuple[object, ...]],
) -> tuple[int, dict[str, int]] | tuple[None, tuple[str, ...]]:
    """Vraća (indeks retka, stupci) ili (None, stupci koji nedostaju u najboljem kandidatu)."""
    trazeni = {_kljuc_stupca(s): s for s in STUPCI}
    nedostaju = STUPCI
    for indeks, redak in enumerate(retci[:NAJVISE_REDAKA_DO_ZAGLAVLJA]):
        stupci: dict[str, int] = {}
        for polozaj, vrijednost in enumerate(redak):
            kljuc = _kljuc_stupca(vrijednost)
            if kljuc in trazeni and trazeni[kljuc] not in stupci:
                stupci[trazeni[kljuc]] = polozaj
        if len(stupci) == len(STUPCI):
            return indeks, stupci
        ovdje_nedostaju = tuple(s for s in STUPCI if s not in stupci)
        if len(ovdje_nedostaju) < len(nedostaju):
            nedostaju = ovdje_nedostaju
    return None, nedostaju


def ucitaj_isvu(sadrzaj: bytes) -> UcitaniPopis:
    """Čita ISVU ``.xlsx`` izvoz; vraća sve studente i sve pogreške (nikad ne baca)."""
    listovi = _ucitaj_listove(sadrzaj)
    if listovi is None:
        return UcitaniPopis((), (GreskaRetka(None, "popis.necitljiv"),))
    nedostaju = STUPCI
    for retci in listovi:  # prvi list sa zaglavljem
        indeks_zaglavlja, stupci = _pronadi_zaglavlje(retci)
        if indeks_zaglavlja is not None:
            break
        if len(stupci) < len(nedostaju):
            nedostaju = stupci
    else:
        parametri = {"stupci": ", ".join(nedostaju), "najvise": NAJVISE_REDAKA_DO_ZAGLAVLJA}
        return UcitaniPopis((), (GreskaRetka(None, "popis.bez_zaglavlja", parametri),))

    studenti: list[Student] = []
    greske: list[GreskaRetka] = []
    redak_rbr: dict[int, int] = {}
    redak_jmbag: dict[str, int] = {}
    for indeks in range(indeks_zaglavlja + 1, len(retci)):
        redak = retci[indeks]

        def celija(stupac: str) -> object:
            polozaj = stupci[stupac]
            return redak[polozaj] if polozaj < len(redak) else None

        # Prazan redak ili redak zbroja/podnožja s vrijednostima samo u drugim stupcima.
        if all(not _tekst(celija(s)) for s in STUPCI):
            continue
        broj_retka = indeks + 1  # Excel broji od 1

        greske_retka: list[GreskaRetka] = []
        broj = _rbr(celija(STUPAC_RBR))
        if broj is None:
            greske_retka.append(GreskaRetka(broj_retka, "popis.rbr_neispravan"))
        elif broj in redak_rbr:
            greske_retka.append(
                GreskaRetka(broj_retka, "popis.dupli_rbr", {"rbr": broj, "prvi": redak_rbr[broj]})
            )
        else:
            redak_rbr[broj] = broj_retka

        jmbag = _jmbag(celija(STUPAC_JMBAG))
        if not jmbag:
            greske_retka.append(GreskaRetka(broj_retka, "popis.prazan_jmbag"))
        elif not _jmbag_valjan(jmbag):
            greske_retka.append(GreskaRetka(broj_retka, "popis.jmbag_neispravan"))
        elif jmbag in redak_jmbag:
            greske_retka.append(
                GreskaRetka(broj_retka, "popis.dupli_jmbag", {"prvi": redak_jmbag[jmbag]})
            )
        else:
            redak_jmbag[jmbag] = broj_retka

        ime = _tekst(celija(STUPAC_IME))
        prezime = _tekst(celija(STUPAC_PREZIME))
        if not ime:
            greske_retka.append(GreskaRetka(broj_retka, "popis.prazno_ime"))
        if not prezime:
            greske_retka.append(GreskaRetka(broj_retka, "popis.prazno_prezime"))

        if greske_retka:
            greske += greske_retka
            continue
        status = _tekst(celija(STUPAC_STATUS)).casefold()
        studenti.append(
            Student(broj, jmbag, ime, prezime, aktivan=not status.startswith(PREFIKS_ISPISAN))
        )

    if not studenti and not greske:
        greske.append(GreskaRetka(None, "popis.bez_studenata"))
    log.info("ISVU izvoz: %d studenata, %d pogrešaka", len(studenti), len(greske))
    return UcitaniPopis(tuple(studenti), tuple(greske))

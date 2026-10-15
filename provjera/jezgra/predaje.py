"""Rezultat batch provjere (Epic 4): čisti oblici bez I/O-a.

Adapter ``batch`` ih puni, a zbirna tablica čita. Student je protokol, pa jezgra ne
ovisi o formatu zamrznutog popisa.
"""

from dataclasses import dataclass

from provjera.jezgra.nalaz import Izvjestaj, NacinUparivanja
from provjera.jezgra.poruke import poruka
from provjera.jezgra.provjera import UkupniStatus, ukupni_status
from provjera.jezgra.uparivanje import RazlogNepovezanosti, StudentPopisa


@dataclass(frozen=True)
class RedakDatoteke:
    """Jedna predana datoteka; ``relativno`` je putanja od mape predaja (s ``/``).

    Povezana datoteka ima ``student`` i ``nacin``. Nepovezana ima ``nepovezano`` (razlog)
    i ``kandidati``. ``izvjestaj`` je ``None`` kad datoteka nije provjerena (nepovezana)
    ili je provjera pukla; tada ``greska`` nosi ime iznimke.
    """

    relativno: str
    student: StudentPopisa | None = None
    nacin: NacinUparivanja | None = None
    izvjestaj: Izvjestaj | None = None
    greska: str | None = None
    nepovezano: RazlogNepovezanosti | None = None
    kandidati: tuple[StudentPopisa, ...] = ()

    @property
    def naziv(self) -> str:
        return self.relativno.rsplit("/", 1)[-1]

    @property
    def status(self) -> UkupniStatus | None:
        """Ukupni status povezane datoteke; nepovezana nema status."""
        if self.student is None:
            return None
        return ukupni_status(self.izvjestaj, True, self.student.aktivan)


@dataclass(frozen=True)
class RezultatBatcha:
    profil_verzija: str
    studenti: tuple[StudentPopisa, ...]
    datoteke: tuple[RedakDatoteke, ...]

    def datoteka_studenta(self, student: StudentPopisa) -> RedakDatoteke | None:
        return next(
            (d for d in self.datoteke if d.student is not None and d.student.rbr == student.rbr),
            None,
        )

    def status_studenta(self, student: StudentPopisa) -> UkupniStatus:
        datoteka = self.datoteka_studenta(student)
        if datoteka is None:
            return ukupni_status(None, False, student.aktivan)
        return ukupni_status(datoteka.izvjestaj, True, student.aktivan)


def opis_statusa(status: UkupniStatus, *, ikona: bool = True) -> str:
    tekst = poruka(f"ukupni_status.{status.value}")
    return f"{poruka(f'ukupni_status.ikona.{status.value}')} {tekst}" if ikona else tekst


def opis_razloga(redak: RedakDatoteke) -> str | None:
    """Zašto datoteka nije provjerena ili je odbijena; ``None`` ako je provjerena."""
    if redak.greska is not None:
        return poruka("batch.razlog_iznimka", greska=redak.greska)
    if redak.izvjestaj is not None and redak.izvjestaj.odbijeno is not None:
        return poruka(f"batch.odbijeno.{redak.izvjestaj.odbijeno.value}")
    if redak.nepovezano is not None:
        return poruka(f"uparivanje.{redak.nepovezano.value}")
    return None


def opis_studenta(student: StudentPopisa) -> str:
    return poruka("batch.student", rbr=student.rbr, ime=student.ime, prezime=student.prezime)


def opis_kandidata(redak: RedakDatoteke) -> str:
    return "; ".join(opis_studenta(s) for s in redak.kandidati)


def opis_nacina(redak: RedakDatoteke) -> str:
    return "" if redak.nacin is None else poruka(f"uparivanje.nacin.{redak.nacin.value}")

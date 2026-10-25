"""Samoprovjera profila na referentnom skupu (priča 3.4): čista usporedba primjera.

Primjer se uspoređuje kao skup ID-eva pravila koja padaju, pa kaskadni nalazi istog
pravila nisu pogreška. Primjer čije je ciljno pravilo isključeno u profilu preskače se.
Bez I/O-a: datoteke čita ``provjera.word.adapteri.samoprovjera``.
"""

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


class StatusPrimjera(Enum):
    PROLAZI = "prolazi"
    NE_PROLAZI = "ne_prolazi"
    PRESKOCENO = "preskoceno"


@dataclass(frozen=True)
class RezultatPrimjera:
    """Ishod jednog primjera.

    ``ocekivano`` je ``None`` kad datoteka nema zapis u ``ocekivano.toml``, a
    ``pronadeno`` je ``None`` kad dokument nije provjeren (tada ``razlog`` je ključ
    poruke ``samoprovjera.*`` s ``parametri``).
    """

    ime: str
    ocekivano: frozenset[str] | None
    pronadeno: frozenset[str] | None
    status: StatusPrimjera
    razlog: str | None = None
    parametri: Mapping[str, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parametri", MappingProxyType(dict(self.parametri)))

    def __eq__(self, drugi: object) -> bool:
        if not isinstance(drugi, RezultatPrimjera):
            return NotImplemented
        return self._kljuc() == drugi._kljuc()

    def __hash__(self) -> int:
        return hash(self._kljuc())

    def _kljuc(self) -> tuple:
        return (
            self.ime,
            self.ocekivano,
            self.pronadeno,
            self.status,
            self.razlog,
            tuple(sorted(self.parametri.items())),
        )


@dataclass(frozen=True)
class NemaSkupa:
    """Samoprovjera se nije mogla pokrenuti: referentni skup nedostaje ili je neispravan.

    ``poruka_kljuc`` i ``parametri`` opisuju razlog (ključ ``samoprovjera.*``).
    """

    poruka_kljuc: str
    parametri: Mapping[str, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parametri", MappingProxyType(dict(self.parametri)))


def usporedi(
    ime: str,
    ocekivano: Collection[str],
    pronadeno: Collection[str],
    ukljucena: Collection[str],
) -> RezultatPrimjera:
    """PRESKOCENO ako je neko očekivano pravilo isključeno; inače usporedba skupova."""
    ocekivano, pronadeno = frozenset(ocekivano), frozenset(pronadeno)
    if not ocekivano <= frozenset(ukljucena):
        status = StatusPrimjera.PRESKOCENO
    elif pronadeno == ocekivano:
        status = StatusPrimjera.PROLAZI
    else:
        status = StatusPrimjera.NE_PROLAZI
    return RezultatPrimjera(ime, ocekivano, pronadeno, status)


def neuspjeli(
    ime: str,
    ocekivano: Collection[str] | None,
    razlog: str,
    parametri: Mapping[str, str | int] | None = None,
) -> RezultatPrimjera:
    """Primjer koji se nije mogao usporediti (nema datoteke, nema zapisa, odbijen …)."""
    return RezultatPrimjera(
        ime,
        None if ocekivano is None else frozenset(ocekivano),
        None,
        StatusPrimjera.NE_PROLAZI,
        razlog,
        parametri or {},
    )


def _ima_ispravan(rezultati: Iterable[RezultatPrimjera]) -> bool:
    return any(
        r.ocekivano == frozenset() and r.status is not StatusPrimjera.PRESKOCENO
        for r in rezultati
    )


def ukupno(rezultati: Iterable[RezultatPrimjera]) -> bool:
    """Prolaz samo bez ijednog NE_PROLAZI i uz barem jedan neprekočen ispravan rad."""
    rezultati = tuple(rezultati)
    return _ima_ispravan(rezultati) and all(
        r.status is not StatusPrimjera.NE_PROLAZI for r in rezultati
    )


def broj_odstupanja(rezultati: Iterable[RezultatPrimjera]) -> int:
    """Broj primjera koji ne prolaze; nedostatak ispravnog rada broji se kao jedno odstupanje."""
    rezultati = tuple(rezultati)
    broj = sum(r.status is StatusPrimjera.NE_PROLAZI for r in rezultati)
    return broj + (0 if _ima_ispravan(rezultati) else 1)

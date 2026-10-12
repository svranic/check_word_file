"""Oblici nalaza, konteksta i izvještaja (AD-1, AD-5); svi su nepromjenjivi."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.ulaz import RazlogOdbijanja


class Status(Enum):
    PROSLO = "PROSLO"
    NE_PROLAZI = "NE_PROLAZI"
    NEPROVJERLJIVO = "NEPROVJERLJIVO"


class Dio(Enum):
    DOKUMENT = "DOKUMENT"
    NAZIV = "NAZIV"
    TIJELO = "TIJELO"
    PODNOZJE = "PODNOZJE"


@dataclass(frozen=True)
class Lokacija:
    """``sekcija`` i ``odlomak`` su 1-bazirani; ``isjecak`` (≤ 60 znakova) dodjeljuje model."""

    dio: Dio
    sekcija: int | None = None
    odlomak: int | None = None
    isjecak: str | None = None


@dataclass(frozen=True)
class Vrijednost:
    iznos: int | str | bool
    jedinica: Jedinica


class VrstaIzvora(Enum):
    ZADANO = "ZADANO"
    TEMA = "TEMA"
    STIL = "STIL"
    IZRAVNO = "IZRAVNO"
    SEKCIJA = "SEKCIJA"


@dataclass(frozen=True)
class Izvor:
    vrsta: VrstaIzvora
    stil: str | None = None


def _zamrzni(parametri: Mapping[str, str | int]) -> Mapping[str, str | int]:
    return MappingProxyType(dict(parametri))


@dataclass(frozen=True)
class Nalaz:
    pravilo_id: str
    status: Status
    lokacija: Lokacija
    poruka_kljuc: str
    ocekivano: Vrijednost | None = None
    pronadeno: Vrijednost | None = None
    izvor: Izvor | None = None
    parametri: Mapping[str, str | int] = field(default_factory=dict)
    pojave: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "parametri", _zamrzni(self.parametri))

    def __hash__(self) -> int:
        return hash(
            (self.pravilo_id, self.status, self.lokacija, self.poruka_kljuc,
             self.ocekivano, self.pronadeno, self.izvor,
             tuple(sorted(self.parametri.items())), self.pojave)
        )


class NacinUparivanja(Enum):
    TOCAN = "TOCAN"
    PRIBLIZAN = "PRIBLIZAN"
    PODMAPA = "PODMAPA"
    JMBAG = "JMBAG"


@dataclass(frozen=True)
class KontekstProvjere:
    """Web šalje ``None``/``None``; batch uvijek popunjava oba zadnja polja (AD-1)."""

    naziv_datoteke: str
    rbr: int
    ocekivani_naziv: str | None
    nacin_uparivanja: NacinUparivanja | None

    def __post_init__(self) -> None:
        if (self.ocekivani_naziv is None) != (self.nacin_uparivanja is None):
            raise ValueError("ocekivani_naziv i nacin_uparivanja zadaju se zajedno")


@dataclass(frozen=True)
class Izvjestaj:
    odbijeno: RazlogOdbijanja | None
    nalazi: tuple[Nalaz, ...]
    profil_verzija: str
    rbr: int

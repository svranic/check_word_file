"""Profil Excel vježbe: TOML datoteka validirana pydanticom (kao profil Word vježbe)."""

import tomllib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from provjera.excel.jezgra.zadaci import ZADACI


class GreskaProfila(Exception):
    pass


class _Odjeljak(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Vjezba(_Odjeljak):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    naziv: str = Field(min_length=1)
    # false: vježba se ne nudi u studentskoj aplikaciji (nacrt).
    objavljeno: bool = True


class NazivDatoteke(_Odjeljak):
    sufiks: str = Field(min_length=1)
    nastavak: str = Field(default=".xlsx", pattern=r"^\.xlsx$")

    @property
    def obrazac(self) -> str:
        return f"Ime_Prezime{self.sufiks}{self.nastavak}"


class Zadaci(_Odjeljak):
    # Svaki zadatak je zaseban list radne knjige, ovim redoslijedom.
    vrste: tuple[str, ...] = Field(min_length=1)
    # Novo sjeme daje nove osobne ulazne podatke za sljedeću generaciju.
    sjeme: int
    # true: predložak svakog studenta ima upisane i zaključane osobne ulazne podatke.
    osobni_podaci: bool = True
    # Lozinka zaštite lista (sprječava slučajno pomicanje ćelija, nije pravo zaključavanje).
    lozinka: str = ""
    # "svi": svaki student rješava sve zadatke; "redom": po redoslijedu popisa studenti
    # naizmjence dobivaju jedan zadatak iz ``vrste``; "nasumicno": jedan zadatak prema
    # JMBAG-u i sjemenu (ne ovisi o popisu).
    raspodjela: Literal["svi", "redom", "nasumicno"] = "svi"
    # Točnost mjerenja kutova u sekundama (1, 5, 10…): mjerene sekunde su višekratnici koraka.
    korak_mjerenja: int = Field(default=1, ge=1, le=60)

    @field_validator("vrste")
    @classmethod
    def _poznate(cls, vrste: tuple[str, ...]) -> tuple[str, ...]:
        nepoznate = [v for v in vrste if v not in ZADACI]
        if nepoznate:
            raise ValueError(f"nepoznat zadatak {nepoznate}; dopušteno: {sorted(ZADACI)}")
        if len(set(vrste)) != len(vrste):
            raise ValueError("zadatak se ponavlja")
        return vrste

    @field_validator("korak_mjerenja")
    @classmethod
    def _dijeli_minutu(cls, korak: int) -> int:
        if 60 % korak:
            raise ValueError("korak mjerenja mora dijeliti 60 sekundi (1, 2, 5, 10, 15, 20, 30…)")
        return korak


class ProfilExcel(_Odjeljak):
    vjezba: Vjezba
    naziv_datoteke: NazivDatoteke
    zadaci: Zadaci


def ucitaj(sadrzaj: bytes) -> ProfilExcel:
    try:
        return ProfilExcel.model_validate(tomllib.loads(sadrzaj.decode("utf-8")))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise GreskaProfila(f"profil nije ispravan TOML: {e}") from e
    except ValidationError as e:
        raise GreskaProfila(str(e)) from e

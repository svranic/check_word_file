"""Profil zadatka (AD-8): TOML datoteka validirana pydanticom; jedina konfiguracija vježbe."""

import hashlib
import json
import tomllib
from collections.abc import Callable, Iterable
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SerializeAsAny,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)

from provjera.jezgra import jedinice
from provjera.jezgra.pravila import REGISTAR, PostavkeBaza


class GreskaProfila(Exception):
    """Neispravan profil; ``greske`` sadrži sve pronađene greške."""

    def __init__(self, greske: tuple[str, ...]):
        super().__init__("\n".join(greske))
        self.greske = greske


def _mjera(pretvorba: Callable[[str], int]) -> Callable[[object], int]:
    def validiraj(vrijednost: object) -> int:
        if not isinstance(vrijednost, str):
            raise ValueError("mjera mora biti tekst s jedinicom, npr. '3 cm'")
        return pretvorba(vrijednost)

    return validiraj


# Gornja granica prostora formule margina (21⁴); štiti od preduge izgradnje tablice.
NAJVISE_KOMBINACIJA = 21**4

Duljina = Annotated[int, BeforeValidator(_mjera(jedinice.parsiraj_duljinu))]
DuljinaMm = Annotated[int, BeforeValidator(_mjera(jedinice.parsiraj_mm))]


class _Odjeljak(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Vjezba(_Odjeljak):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    naziv: str = Field(min_length=1)
    objavljeno: bool


class NazivDatoteke(_Odjeljak):
    sufiks: str = Field(min_length=1)
    nastavak: str = Field(pattern=r"^\.[a-z]+$")

    @property
    def obrazac(self) -> str:
        return f"Ime_Prezime{self.sufiks}{self.nastavak}"


class ParametriFormule(_Odjeljak):
    """Parametri formule margina; sve duljine u cijelim milimetrima."""

    osnovica_gore: DuljinaMm
    osnovica_dolje: DuljinaMm
    osnovica_lijevo: DuljinaMm
    osnovica_desno: DuljinaMm
    raspon: DuljinaMm
    korak: DuljinaMm
    naslovnica: DuljinaMm
    sjeme: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def _provjeri_odnose(self) -> "ParametriFormule":
        greske = []
        if self.korak <= 0:
            greske.append("korak mora biti veći od 0")
        elif self.raspon <= 0 or self.raspon % self.korak:
            greske.append("raspon mora biti pozitivan višekratnik koraka")
        elif (2 * (self.raspon // self.korak) + 1) ** 4 > NAJVISE_KOMBINACIJA:
            greske.append(f"raspon/korak daje više od {NAJVISE_KOMBINACIJA} kombinacija")
        for strana in ("gore", "dolje", "lijevo", "desno"):
            if getattr(self, f"osnovica_{strana}") - self.raspon <= 0:
                greske.append(f"osnovica_{strana} mora biti veća od raspona")
        if self.naslovnica <= 0:
            greske.append("naslovnica mora biti veća od 0")
        if greske:
            raise ValueError("; ".join(greske))
        return self


class Tolerancije(_Odjeljak):
    margine: Duljina


class Profil(_Odjeljak):
    vjezba: Vjezba
    naziv_datoteke: NazivDatoteke
    formula: ParametriFormule
    tolerancije: Tolerancije
    pravila: dict[str, SerializeAsAny[PostavkeBaza]] = Field(
        default_factory=dict, validate_default=True
    )

    @field_validator("pravila", mode="before")
    @classmethod
    def _postavke_iz_registra(cls, odjeljci: object) -> dict[str, PostavkeBaza]:
        """Svaki ``[pravila.<ID>]`` validira klasa iz registra; nedostajući dobiva zadane."""
        if not isinstance(odjeljci, dict):
            raise ValueError("pravila mora biti tablica [pravila.<ID>]")
        greske, rezultat = [], {}
        for pravilo_id, odjeljak in odjeljci.items():
            if pravilo_id not in REGISTAR:
                greske.append(f"{pravilo_id}: nepoznato pravilo")
                continue
            try:
                rezultat[pravilo_id] = REGISTAR[pravilo_id].postavke.model_validate(odjeljak)
            except ValidationError as greska:
                greske += [f"{pravilo_id}.{_opis_greske(g)}" for g in greska.errors()]
        if greske:
            raise ValueError("; ".join(greske))
        for pravilo_id, pravilo in REGISTAR.items():
            rezultat.setdefault(pravilo_id, pravilo.postavke())
        return rezultat

    @model_validator(mode="after")
    def _tolerancija_manja_od_pola_koraka(self) -> "Profil":
        if 2 * self.tolerancije.margine >= jedinice.mm_u_twips(self.formula.korak):
            raise ValueError("tolerancije.margine mora biti manja od pola koraka formule")
        return self


def _opis_greske(greska: dict) -> str:
    putanja = ".".join(str(dio) for dio in greska["loc"]) or "profil"
    return f"{putanja}: {greska['msg']}"


def ucitaj(sadrzaj: bytes) -> Profil:
    """Učitava i validira profil; svaka greška baca ``GreskaProfila`` sa svim greškama."""
    try:
        podaci = tomllib.loads(sadrzaj.decode("utf-8-sig"))  # Windows uređivači dodaju BOM
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as greska:
        raise GreskaProfila((f"TOML: {greska}",)) from greska
    try:
        return Profil.model_validate(podaci)
    except ValidationError as greska:
        raise GreskaProfila(tuple(_opis_greske(g) for g in greska.errors())) from greska


def objavljeni(sadrzaji: Iterable[bytes]) -> tuple[list[Profil], int]:
    """Vraća objavljene profile (redom kako su zadani) i broj neispravnih.

    Objavljeni profil s već viđenim ``vjezba.id`` broji se kao neispravan.
    """
    profili, neispravnih, ids = [], 0, set()
    for sadrzaj in sadrzaji:
        try:
            profil = ucitaj(sadrzaj)
        except GreskaProfila:
            neispravnih += 1
            continue
        if not profil.vjezba.objavljeno:
            continue
        if profil.vjezba.id in ids:
            neispravnih += 1
            continue
        ids.add(profil.vjezba.id)
        profili.append(profil)
    return profili, neispravnih


def kanonski_json(podaci: object) -> bytes:
    return json.dumps(
        podaci, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def verzija(profil: Profil) -> str:
    """Verzija iz sadržaja: ne mijenja se s redoslijedom ključeva ni komentarima."""
    return hashlib.sha256(kanonski_json(profil.model_dump(mode="json"))).hexdigest()[:8]

"""Profil zadatka (AD-8): TOML datoteka validirana pydanticom; jedina konfiguracija vježbe."""

import hashlib
import tomllib
from collections.abc import Iterable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    ValidationError,
    field_validator,
    model_validator,
)

from provjera.jezgra import jedinice
from provjera.jezgra.pravila import REGISTAR, PostavkeBaza
from provjera.jezgra.formula import ParametriFormule, kanonski_json
from provjera.jezgra.model.uloge import NaziviUloga
from provjera.jezgra.poruke import poruka
from provjera.jezgra.tipovi import Duljina


class GreskaProfila(Exception):
    """Neispravan profil; ``greske`` sadrži sve pronađene greške."""

    def __init__(self, greske: tuple[str, ...]):
        super().__init__("\n".join(greske))
        self.greske = greske


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


class Tolerancije(_Odjeljak):
    margine: Duljina
    stranica: Duljina


class Profil(_Odjeljak):
    vjezba: Vjezba
    naziv_datoteke: NazivDatoteke
    formula: ParametriFormule
    tolerancije: Tolerancije
    uloge: NaziviUloga
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
        for pravilo_id, pravilo in REGISTAR.items():
            if pravilo_id in rezultat or pravilo_id in odjeljci:
                continue
            try:
                rezultat[pravilo_id] = pravilo.postavke()
            except ValidationError:
                # Pravilo bez zadanih vrijednosti (npr. R-TEKST) traži svoj odjeljak u profilu.
                greske.append(f"{pravilo_id}: nedostaje odjeljak [pravila.{pravilo_id}]")
        if greske:
            raise ValueError("; ".join(greske))
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


def ucitaj_sve(
    imenovani_sadrzaji: Iterable[tuple[str, bytes]],
) -> list[tuple[str, Profil | GreskaProfila]]:
    """Za svaku imenovanu datoteku vraća profil ili ``GreskaProfila`` (nastavnička aplikacija).

    Kod dupliciranog ``vjezba.id`` ostaje jedini objavljeni profil; ako objavljenih nije
    točno jedan, ostaje prvi po redu. Ostali se vraćaju kao greška ključa ``vjezba.id``.
    """
    rezultat: list[tuple[str, Profil | GreskaProfila]] = []
    po_id: dict[str, list[tuple[str, Profil]]] = {}
    for ime, sadrzaj in imenovani_sadrzaji:
        try:
            profil = ucitaj(sadrzaj)
        except GreskaProfila as greska:
            rezultat.append((ime, greska))
            continue
        po_id.setdefault(profil.vjezba.id, []).append((ime, profil))
        rezultat.append((ime, profil))
    pobjednici = {}
    for id_vjezbe, kandidati in po_id.items():
        objavljeni_kandidati = [k for k in kandidati if k[1].vjezba.objavljeno]
        pobjednici[id_vjezbe] = (
            objavljeni_kandidati[0][0] if len(objavljeni_kandidati) == 1 else kandidati[0][0]
        )
    for i, (ime, ucitano) in enumerate(rezultat):
        if isinstance(ucitano, Profil) and pobjednici[ucitano.vjezba.id] != ime:
            greska = poruka("profil.dupli_id", datoteka=pobjednici[ucitano.vjezba.id])
            rezultat[i] = (ime, GreskaProfila((greska,)))
    return rezultat


def verzija(profil: Profil) -> str:
    """Verzija iz sadržaja: ne mijenja se s redoslijedom ključeva ni komentarima."""
    return hashlib.sha256(kanonski_json(profil.model_dump(mode="json"))).hexdigest()[:8]

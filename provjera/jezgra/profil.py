"""Profil zadatka (AD-8): TOML datoteka validirana pydanticom; jedina konfiguracija vježbe."""

import hashlib
import tomllib
from collections.abc import Iterable
from urllib.parse import urlsplit

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
    # Poveznica na web provjeru koja se objavljuje u PDF-u sa svojstvima.
    poveznica: str

    @field_validator("poveznica")
    @classmethod
    def _https(cls, vrijednost: str) -> str:
        try:
            dijelovi = urlsplit(vrijednost)
            dijelovi.port  # neispravan port („:abc“) baca ValueError
            ispravna = (
                dijelovi.scheme == "https"
                and bool(dijelovi.hostname)
                and not any(z.isspace() for z in vrijednost)
            )
        except ValueError:
            ispravna = False
        if not ispravna:
            raise ValueError("poveznica mora biti https adresa, npr. 'https://primjer.hr/'")
        return vrijednost


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
        # Uz fiksne margine nema koraka: svi studenti imaju iste margine tijela.
        if self.formula.fiksne_margine:
            return self
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


def _izricito_neobjavljen(sadrzaj: bytes) -> bool:
    try:
        podaci = tomllib.loads(sadrzaj.decode("utf-8-sig"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False
    vjezba = podaci.get("vjezba")
    return isinstance(vjezba, dict) and vjezba.get("objavljeno") is False


def objavljeni(sadrzaji: Iterable[bytes]) -> tuple[list[Profil], int]:
    """Vraća objavljene profile (redom kako su zadani) i broj neispravnih.

    Objavljeni profil s već viđenim ``vjezba.id`` broji se kao neispravan.
    """
    profili, neispravnih, ids = [], 0, set()
    for sadrzaj in sadrzaji:
        try:
            profil = ucitaj(sadrzaj)
        except GreskaProfila:
            # Neispravan nacrt s ``objavljeno = false`` studente se ne tiče.
            if not _izricito_neobjavljen(sadrzaj):
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
        # Prvi objavljeni, kao što ga dobivaju studenti (``objavljeni``); inače prvi.
        pobjednici[id_vjezbe] = (objavljeni_kandidati or kandidati)[0][0]
    for i, (ime, ucitano) in enumerate(rezultat):
        if isinstance(ucitano, Profil) and pobjednici[ucitano.vjezba.id] != ime:
            greska = poruka("profil.dupli_id", datoteka=pobjednici[ucitano.vjezba.id])
            rezultat[i] = (ime, GreskaProfila((greska,)))
    return rezultat


def verzija(profil: Profil) -> str:
    """Verzija iz sadržaja: ne mijenja se s redoslijedom ključeva ni komentarima."""
    return hashlib.sha256(kanonski_json(profil.model_dump(mode="json"))).hexdigest()[:8]

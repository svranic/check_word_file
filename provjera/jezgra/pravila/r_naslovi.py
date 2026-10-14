"""R-NASLOVI: naslovi poglavlja u stilu Heading 1, oblikovani po profilu i numerirani Wordovom numeracijom.

Pravilo samo filtrira po ulozi; normalizaciju naziva i prepoznavanje ručnog broja daje
``uloge.py``, a stvarnu oznaku numeracije („1.“) model. Nalazi su nesažeti po odlomku.
"""

from typing import TYPE_CHECKING

from pydantic import ConfigDict, field_validator, model_validator

from provjera.jezgra.jedinice import Jedinica, unutar_tolerancije
from provjera.jezgra.model import DocModel, Efektivno, Odlomak, Poravnanje
from provjera.jezgra.model.stilovi import kanonski_id
from provjera.jezgra.model.uloge import (
    UlogaOdlomka,
    bez_rucnog_broja,
    ima_rucni_broj,
    normaliziraj_naziv,
)
from provjera.jezgra.nalaz import (
    Dio,
    KontekstProvjere,
    Lokacija,
    Nalaz,
    Status,
    Vrijednost,
)
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.jezgra.pravila.runovi import nalazi_runova
from provjera.jezgra.tipovi import Duljina, VelicinaFonta

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-NASLOVI"
_TOLERANCIJA = 0
_NASLOVI = (UlogaOdlomka.NASLOV_POGLAVLJA, UlogaOdlomka.NASLOV_LITERATURE)


class Postavke(PostavkeBaza):
    """Ciljne vrijednosti dolaze isključivo iz ``[pravila.R-NASLOVI]`` u profilu.

    ``oznaka`` je predložak oznake numeracije s ``{n}`` za redni broj poglavlja (npr. ``"{n}."``).
    """

    model_config = ConfigDict(validate_default=True)

    stil: str | None = None
    font: str | None = None
    podebljano: bool | None = None
    velicina: VelicinaFonta | None = None
    poravnanje: Poravnanje | None = None
    razmak_ispred: Duljina | None = None
    razmak_iza: Duljina | None = None
    oznaka: str | None = None

    @field_validator("poravnanje")
    @classmethod
    def _bez_ostalo(cls, vrijednost: Poravnanje | None) -> Poravnanje | None:
        if vrijednost is Poravnanje.OSTALO:
            raise ValueError("poravnanje mora biti lijevo, sredina, desno ili obostrano")
        return vrijednost

    @field_validator("oznaka")
    @classmethod
    def _oznaka_s_brojem(cls, vrijednost: str | None) -> str | None:
        if vrijednost is not None:
            try:
                ispravna = vrijednost.format(n=1) != vrijednost.format(n=2)
            except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                ispravna = False
            if not ispravna:
                raise ValueError("oznaka mora sadržavati {n}, npr. \"{n}.\"")
        return vrijednost

    @model_validator(mode="after")
    def _ciljevi_kad_je_ukljuceno(self) -> "Postavke":
        if self.ukljuceno:
            nedostaju = [ime for ime in _CILJEVI if getattr(self, ime) is None]
            if nedostaju:
                raise ValueError(f"nedostaju ciljne vrijednosti: {', '.join(nedostaju)}")
        return self


_CILJEVI = ("stil", "font", "podebljano", "velicina", "poravnanje", "razmak_ispred", "razmak_iza", "oznaka")


def _lokacija(o: Odlomak) -> Lokacija:
    return Lokacija(Dio.TIJELO, sekcija=o.sekcija, odlomak=o.indeks, isjecak=o.isjecak)


def _nalaz(o: Odlomak, stil: str, kljuc: str, ocekivano: Vrijednost | None = None,
           pronadeno: Vrijednost | None = None, efektivno: Efektivno | None = None,
           status: Status = Status.NE_PROLAZI) -> Nalaz:
    return Nalaz(
        ID, status, _lokacija(o), f"{ID}.{kljuc}",
        ocekivano=ocekivano,
        pronadeno=pronadeno,
        izvor=efektivno.izvor if efektivno is not None else None,
        parametri={"stil": stil},
    )


def _numeracija(o: Odlomak, p: Postavke, redni: int) -> list[Nalaz]:
    numeracija = o.numeracija.vrijednost
    rucni = ima_rucni_broj(o.tekst)
    if numeracija is None:
        kljuc = "rucni_broj" if rucni else "bez_numeracije"
        return [_nalaz(o, p.stil, kljuc, pronadeno=Vrijednost(o.tekst.strip(), Jedinica.TEKST) if rucni else None)]
    nalazi = []
    if rucni:
        nalazi.append(_nalaz(o, p.stil, "rucni_broj_uz_numeraciju",
                             pronadeno=Vrijednost(o.tekst.strip(), Jedinica.TEKST)))
    ocekivano = p.oznaka.format(n=redni)
    # Stroga usporedba: „1“ (uzorak „%1“) nije „1.“.
    if numeracija.oznaka != ocekivano:
        nalazi.append(_nalaz(o, p.stil, "kriva_oznaka", Vrijednost(ocekivano, Jedinica.TEKST),
                             Vrijednost(numeracija.oznaka, Jedinica.TEKST), o.numeracija))
    return nalazi


def _oblik(o: Odlomak, p: Postavke) -> list[Nalaz]:
    nalazi = []
    if o.poravnanje.vrijednost is not p.poravnanje:
        nalazi.append(_nalaz(o, p.stil, "poravnanje", Vrijednost(p.poravnanje.value, Jedinica.PORAVNANJE),
                             Vrijednost(o.poravnanje.vrijednost.value, Jedinica.PORAVNANJE), o.poravnanje))
    for kljuc in ("razmak_ispred", "razmak_iza"):
        efektivno, ocekivano = getattr(o, kljuc), getattr(p, kljuc)
        if not unutar_tolerancije(efektivno.vrijednost, ocekivano, _TOLERANCIJA):
            nalazi.append(_nalaz(o, p.stil, kljuc, Vrijednost(ocekivano, Jedinica.TOCKE),
                                 Vrijednost(efektivno.vrijednost, Jedinica.TOCKE), efektivno))
    return nalazi + nalazi_runova(o, ID, p.font, p.velicina, {"stil": p.stil}, podebljano=p.podebljano)


def _u_stilu(o: Odlomak, p: Postavke) -> bool:
    return o.stil.kanonski_id.casefold() == kanonski_id(p.stil, p.stil, False).casefold()


def _naslov(o: Odlomak, p: Postavke, redni: int) -> list[Nalaz]:
    if not _u_stilu(o, p):
        # Primjena stila ispravlja i oblik i numeraciju; ostalo bi bila buka.
        nalazi = [_nalaz(o, p.stil, "drugi_stil", Vrijednost(p.stil, Jedinica.TEKST),
                         Vrijednost(o.stil.ime, Jedinica.TEKST))]
        if ima_rucni_broj(o.tekst):
            nalazi.append(_nalaz(o, p.stil, "rucni_broj", pronadeno=Vrijednost(o.tekst.strip(), Jedinica.TEKST)))
        return nalazi
    return _numeracija(o, p, redni) + _oblik(o, p)


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-NASLOVI.prolazi",
        "R-NASLOVI.nedostaje",
        "R-NASLOVI.drugi_stil",
        "R-NASLOVI.rucni_broj",
        "R-NASLOVI.rucni_broj_uz_numeraciju",
        "R-NASLOVI.bez_numeracije",
        "R-NASLOVI.kriva_oznaka",
        "R-NASLOVI.sazetak_numeriran",
        "R-NASLOVI.font",
        "R-NASLOVI.font_tema",
        "R-NASLOVI.font_nepoznat",
        "R-NASLOVI.podebljano",
        "R-NASLOVI.velicina",
        "R-NASLOVI.poravnanje",
        "R-NASLOVI.razmak_ispred",
        "R-NASLOVI.razmak_iza",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    poglavlja = [normaliziraj_naziv(p) for p in profil.uloge.poglavlja]
    nalazi: list[Nalaz] = []
    pronadeni: set[str] = set()
    # k broji numerirane odlomke u stilu iz profila redom u dokumentu, bez obzira na ulogu
    # (numerirani „Sažetak“ u tom stilu se broji, nenumerirani naslov ne), kao Word.
    redni = 0
    for o in model.odlomci:
        if _u_stilu(o, postavke) and o.numeracija.vrijednost is not None:
            redni += 1
        if o.uloga is UlogaOdlomka.NASLOV_SAZETKA:
            if o.numeracija.vrijednost is not None:
                nalazi.append(_nalaz(o, postavke.stil, "sazetak_numeriran",
                                     pronadeno=Vrijednost(o.numeracija.vrijednost.oznaka, Jedinica.TEKST),
                                     efektivno=o.numeracija))
            elif ima_rucni_broj(o.tekst):
                nalazi.append(_nalaz(o, postavke.stil, "sazetak_numeriran",
                                     pronadeno=Vrijednost(o.tekst.strip(), Jedinica.TEKST)))
        elif o.uloga in _NASLOVI:
            pronadeni.add(normaliziraj_naziv(bez_rucnog_broja(o.tekst)))
            nalazi += _naslov(o, postavke, redni)
    # Naslov u tekstnom okviru postoji; uvjet „u okviru“ prijavljuje samo R-OKVIRI.
    pronadeni |= {normaliziraj_naziv(bez_rucnog_broja(o.tekst))
                  for o in model.okviri if o.uloga in _NASLOVI}
    for naziv, normaliziran in zip(profil.uloge.poglavlja, poglavlja):
        if normaliziran not in pronadeni:
            nalazi.append(Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), f"{ID}.nedostaje",
                                parametri={"stil": postavke.stil, "naziv": naziv}))
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi",
                            parametri={"stil": postavke.stil})]

"""R-TEKST: osnovni tekst u stilu Normal, Calibri 12 pt, obostrano, razmak 6/6 pt, jednostruko.

Pravilo vraća nesažete nalaze po odlomku; pokretač ih sažima (``pojave``). Podebljanje i
kurziv se ne provjeravaju.
"""

from typing import TYPE_CHECKING

from pydantic import ConfigDict, field_validator, model_validator

from provjera.word.jezgra.jedinice import Jedinica, unutar_tolerancije
from provjera.word.jezgra.model import DocModel, Efektivno, Odlomak, Poravnanje, PraviloProreda
from provjera.word.jezgra.model.stilovi import kanonski_id
from provjera.word.jezgra.model.uloge import UlogaOdlomka
from provjera.word.jezgra.nalaz import (
    Dio,
    KontekstProvjere,
    Lokacija,
    Nalaz,
    Status,
    Vrijednost,
)
from provjera.word.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.word.jezgra.pravila.runovi import nalazi_runova
from provjera.word.jezgra.tipovi import Duljina, Retci, VelicinaFonta

if TYPE_CHECKING:
    from provjera.word.jezgra.profil import Profil

ID = "R-TEKST"
_TOLERANCIJA = 0


class Postavke(PostavkeBaza):
    """Ciljne vrijednosti dolaze isključivo iz ``[pravila.R-TEKST]`` u profilu.

    Obavezne su samo kad je pravilo uključeno, da se pravilo može isključiti bez njih.
    """

    model_config = ConfigDict(validate_default=True)

    stil: str | None = None
    font: str | None = None
    velicina: VelicinaFonta | None = None
    poravnanje: Poravnanje | None = None
    razmak_ispred: Duljina | None = None
    razmak_iza: Duljina | None = None
    prored: Retci | None = None

    @field_validator("poravnanje")
    @classmethod
    def _bez_ostalo(cls, vrijednost: Poravnanje | None) -> Poravnanje | None:
        if vrijednost is Poravnanje.OSTALO:
            raise ValueError("poravnanje mora biti lijevo, sredina, desno ili obostrano")
        return vrijednost

    @model_validator(mode="after")
    def _ciljevi_kad_je_ukljuceno(self) -> "Postavke":
        if self.ukljuceno:
            nedostaju = [ime for ime in _CILJEVI if getattr(self, ime) is None]
            if nedostaju:
                raise ValueError(f"nedostaju ciljne vrijednosti: {', '.join(nedostaju)}")
        return self


_CILJEVI = ("stil", "font", "velicina", "poravnanje", "razmak_ispred", "razmak_iza", "prored")


def _lokacija(o: Odlomak) -> Lokacija:
    return Lokacija(Dio.TIJELO, sekcija=o.sekcija, odlomak=o.indeks, isjecak=o.isjecak)


def _nalaz(o: Odlomak, stil: str, kljuc: str, ocekivano: Vrijednost, pronadeno: Vrijednost | None,
           efektivno: Efektivno | None, status: Status = Status.NE_PROLAZI) -> Nalaz:
    return Nalaz(
        ID, status, _lokacija(o), f"{ID}.{kljuc}",
        ocekivano=ocekivano,
        pronadeno=pronadeno,
        izvor=efektivno.izvor if efektivno is not None else None,
        parametri={"stil": stil},
    )


def _odlomak(o: Odlomak, p: Postavke) -> list[Nalaz]:
    nalazi = []
    if o.stil.kanonski_id.casefold() != kanonski_id(p.stil, p.stil, False).casefold():
        nalazi.append(_nalaz(o, p.stil, "drugi_stil", Vrijednost(p.stil, Jedinica.TEKST),
                             Vrijednost(o.stil.ime, Jedinica.TEKST), None))
    if o.poravnanje.vrijednost is not p.poravnanje:
        nalazi.append(_nalaz(o, p.stil, "poravnanje", Vrijednost(p.poravnanje.value, Jedinica.PORAVNANJE),
                             Vrijednost(o.poravnanje.vrijednost.value, Jedinica.PORAVNANJE), o.poravnanje))
    for kljuc in ("razmak_ispred", "razmak_iza"):
        efektivno, ocekivano = getattr(o, kljuc), getattr(p, kljuc)
        if not unutar_tolerancije(efektivno.vrijednost, ocekivano, _TOLERANCIJA):
            nalazi.append(_nalaz(o, p.stil, kljuc, Vrijednost(ocekivano, Jedinica.TOCKE),
                                 Vrijednost(efektivno.vrijednost, Jedinica.TOCKE), efektivno))
    prored = o.prored.vrijednost
    if prored.pravilo is not PraviloProreda.AUTO:
        # Točan ili najmanji prored zapisan je u twipsima, ne u retcima.
        nalazi.append(_nalaz(o, p.stil, "prored", Vrijednost(p.prored, Jedinica.RETCI),
                             Vrijednost(prored.iznos, Jedinica.TOCKE), o.prored))
    elif not unutar_tolerancije(prored.iznos, p.prored, _TOLERANCIJA):
        nalazi.append(_nalaz(o, p.stil, "prored", Vrijednost(p.prored, Jedinica.RETCI),
                             Vrijednost(prored.iznos, Jedinica.RETCI), o.prored))
    nalazi += nalazi_runova(o, ID, p.font, p.velicina, {"stil": p.stil})
    return nalazi


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-TEKST.prolazi",
        "R-TEKST.nema_teksta",
        "R-TEKST.drugi_stil",
        "R-TEKST.font",
        "R-TEKST.font_tema",
        "R-TEKST.font_nepoznat",
        "R-TEKST.velicina",
        "R-TEKST.poravnanje",
        "R-TEKST.razmak_ispred",
        "R-TEKST.razmak_iza",
        "R-TEKST.prored",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    odlomci = [o for o in model.odlomci if o.uloga is UlogaOdlomka.OSNOVNI_TEKST]
    parametri = {"stil": postavke.stil}
    # Osnovni tekst samo u tekstnom okviru prijavljuje R-OKVIRI, ne „nema teksta“.
    u_okviru = any(o.uloga is UlogaOdlomka.OSNOVNI_TEKST for o in model.okviri)
    if not odlomci and not u_okviru:
        return [Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), f"{ID}.nema_teksta", parametri=parametri)]
    nalazi = [n for o in odlomci for n in _odlomak(o, postavke)]
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi", parametri=parametri)]

"""R-SAZETAK: sažetak u fontu i veličini iz profila, poravnat i uvučen lijevo i desno.

Provjeravaju se samo efektivne vrijednosti: sažetak smije biti u stilu Normal s uvlakom ili
u vlastitom stilu. Uvlaka prvog retka, razmaci i prored se ne provjeravaju. Nalazi su
nesažeti po odlomku; pokretač ih sažima.
"""

from typing import TYPE_CHECKING

from pydantic import ConfigDict, field_validator, model_validator

from provjera.jezgra.jedinice import Jedinica, unutar_tolerancije
from provjera.jezgra.model import DocModel, Odlomak, Poravnanje
from provjera.jezgra.model.uloge import UlogaOdlomka
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status, Vrijednost
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.jezgra.pravila.runovi import nalaz_odlomka, nalazi_runova
from provjera.jezgra.tipovi import Duljina, VelicinaFonta

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-SAZETAK"


class Postavke(PostavkeBaza):
    """Ciljne vrijednosti dolaze isključivo iz ``[pravila.R-SAZETAK]`` u profilu.

    ``tolerancija`` vrijedi za uvlake: Word 3,5 cm zapisuje kao 1984 ili 1985 twipsa.
    """

    model_config = ConfigDict(validate_default=True)

    font: str | None = None
    velicina: VelicinaFonta | None = None
    poravnanje: Poravnanje | None = None
    uvlaka_lijevo: Duljina | None = None
    uvlaka_desno: Duljina | None = None
    tolerancija: Duljina | None = None

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


_CILJEVI = ("font", "velicina", "poravnanje", "uvlaka_lijevo", "uvlaka_desno", "tolerancija")


def _odlomak(o: Odlomak, p: Postavke) -> list[Nalaz]:
    nalazi = []
    if o.poravnanje.vrijednost is not p.poravnanje:
        nalazi.append(nalaz_odlomka(o, ID, "poravnanje", {}, Vrijednost(p.poravnanje.value, Jedinica.PORAVNANJE),
                                    Vrijednost(o.poravnanje.vrijednost.value, Jedinica.PORAVNANJE), o.poravnanje))
    for kljuc in ("uvlaka_lijevo", "uvlaka_desno"):
        efektivno, ocekivano = getattr(o, kljuc), getattr(p, kljuc)
        if not unutar_tolerancije(efektivno.vrijednost, ocekivano, p.tolerancija):
            nalazi.append(nalaz_odlomka(o, ID, kljuc, {}, Vrijednost(ocekivano, Jedinica.TWIPS),
                                        Vrijednost(efektivno.vrijednost, Jedinica.TWIPS), efektivno))
    return nalazi + nalazi_runova(o, ID, p.font, p.velicina, {})


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-SAZETAK.prolazi",
        "R-SAZETAK.nema_sazetka",
        "R-SAZETAK.nema_naslova",
        "R-SAZETAK.prazan_sazetak",
        "R-SAZETAK.krivo_mjesto",
        "R-SAZETAK.font",
        "R-SAZETAK.font_tema",
        "R-SAZETAK.font_nepoznat",
        "R-SAZETAK.velicina",
        "R-SAZETAK.poravnanje",
        "R-SAZETAK.uvlaka_lijevo",
        "R-SAZETAK.uvlaka_desno",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    naziv = {"naziv": profil.uloge.sazetak}

    def nalaz(kljuc: str) -> list[Nalaz]:
        return [Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), f"{ID}.{kljuc}", parametri=naziv)]

    def prvi(uloge: tuple[UlogaOdlomka, ...]) -> int | None:
        return next((i for i, o in enumerate(model.odlomci) if o.uloga in uloge), None)

    naslov = prvi((UlogaOdlomka.NASLOV_SAZETKA,))
    if naslov is None:
        # Bez naslova se ne zna što je sažetak (npr. naslovnica u jedinoj sekciji je
        # također ispred prvog poglavlja), pa se svojstva ne provjeravaju.
        ima_tekst = prvi((UlogaOdlomka.SAZETAK,)) is not None
        return nalaz("nema_naslova" if ima_tekst else "nema_sazetka")
    poglavlje = prvi((UlogaOdlomka.NASLOV_POGLAVLJA, UlogaOdlomka.NASLOV_LITERATURE))
    if poglavlje is not None and naslov > poglavlje:
        return nalaz("krivo_mjesto")
    # Sažetak su odlomci iza naslova; ispred njega je npr. naslovnica bez zasebne sekcije.
    odlomci = [o for o in model.odlomci[naslov:] if o.uloga is UlogaOdlomka.SAZETAK]
    if not odlomci:
        return nalaz("prazan_sazetak")
    nalazi = [n for o in odlomci for n in _odlomak(o, postavke)]
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi")]

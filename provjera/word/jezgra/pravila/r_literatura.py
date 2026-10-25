"""R-LITERATURA: stavke literature u fontu i veličini iz profila.

Provjerava se samo efektivni font i veličina runova; stavke smiju imati vlastiti stil
(npr. List Paragraph). Nalazi su nesažeti po odlomku; pokretač ih sažima.
"""

from typing import TYPE_CHECKING

from pydantic import ConfigDict, model_validator

from provjera.word.jezgra.model import DocModel
from provjera.word.jezgra.model.uloge import UlogaOdlomka
from provjera.word.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.word.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.word.jezgra.pravila.runovi import nalazi_runova
from provjera.word.jezgra.tipovi import VelicinaFonta

if TYPE_CHECKING:
    from provjera.word.jezgra.profil import Profil

ID = "R-LITERATURA"


class Postavke(PostavkeBaza):
    """Ciljne vrijednosti dolaze isključivo iz ``[pravila.R-LITERATURA]`` u profilu."""

    model_config = ConfigDict(validate_default=True)

    font: str | None = None
    velicina: VelicinaFonta | None = None

    @model_validator(mode="after")
    def _ciljevi_kad_je_ukljuceno(self) -> "Postavke":
        if self.ukljuceno:
            nedostaju = [ime for ime in _CILJEVI if getattr(self, ime) is None]
            if nedostaju:
                raise ValueError(f"nedostaju ciljne vrijednosti: {', '.join(nedostaju)}")
        return self


_CILJEVI = ("font", "velicina")


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-LITERATURA.prolazi",
        "R-LITERATURA.nema_stavki",
        "R-LITERATURA.font",
        "R-LITERATURA.font_tema",
        "R-LITERATURA.font_nepoznat",
        "R-LITERATURA.velicina",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    odlomci = [o for o in model.odlomci if o.uloga is UlogaOdlomka.LITERATURA]
    if not odlomci and any(o.uloga is UlogaOdlomka.NASLOV_LITERATURE for o in model.okviri):
        # Naslov u tekstnom okviru prijavljuje samo R-OKVIRI.
        return [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi")]
    if not odlomci:
        return [Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), f"{ID}.nema_stavki",
                      parametri={"naziv": profil.uloge.literatura})]
    nalazi = [n for o in odlomci for n in nalazi_runova(o, ID, postavke.font, postavke.velicina, {})]
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi")]

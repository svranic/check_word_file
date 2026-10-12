"""R-SEKCIJE (FR-17): naslovnica je zasebna sekcija; sljedeća počinje na novoj stranici."""

from typing import TYPE_CHECKING

from provjera.jezgra.model import DocModel, TipPocetka
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-SEKCIJE"


class Postavke(PostavkeBaza):
    pass


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-SEKCIJE.prolazi",
        "R-SEKCIJE.jedna_sekcija",
        "R-SEKCIJE.krivi_prijelom",
        "R-SEKCIJE.bez_sekcija",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    if not model.sekcije:
        return [Nalaz(ID, Status.NEPROVJERLJIVO, Lokacija(Dio.DOKUMENT), "R-SEKCIJE.bez_sekcija")]
    if len(model.sekcije) == 1:
        return [Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), "R-SEKCIJE.jedna_sekcija")]
    druga = model.sekcije[1]
    if druga.pocetak is not TipPocetka.SLJEDECA_STRANICA:
        return [
            Nalaz(
                ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT, sekcija=druga.indeks),
                "R-SEKCIJE.krivi_prijelom", parametri={"sekcija": druga.indeks},
            )
        ]
    return [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), "R-SEKCIJE.prolazi")]

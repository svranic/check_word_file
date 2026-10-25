"""R-PROMJENE: dokument bez praćenih promjena.

Model sva ostala pravila procjenjuje u prihvaćenom stanju; ovo pravilo samo javlja da
promjene postoje (jedan nalaz za cijeli dokument).
"""

from typing import TYPE_CHECKING

from provjera.word.jezgra.model import DocModel
from provjera.word.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.word.jezgra.pravila.osnova import PostavkeBaza, registriraj

if TYPE_CHECKING:
    from provjera.word.jezgra.profil import Profil

ID = "R-PROMJENE"


class Postavke(PostavkeBaza):
    """``[pravila.R-PROMJENE]`` ima samo ``ukljuceno``."""


@registriraj(ID, Postavke, poruke=(f"{ID}.prolazi", f"{ID}.prisutne"))
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    if model.pracene_promjene:
        return [Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), f"{ID}.prisutne")]
    return [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi")]

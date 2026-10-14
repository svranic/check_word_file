"""R-OKVIRI: naslovi (sažetka, poglavlja, literature) i osnovni tekst nisu u tekstnim okvirima ni oblicima.

Uloge odlomaka okvira dodjeljuje ``uloge.py``, a okvire na naslovnici, u podnožjima i u
zaglavljima model ne izdvaja. Samo ovo pravilo prijavljuje uvjet „u okviru“.
"""

from typing import TYPE_CHECKING

from provjera.jezgra.model import DocModel, OdlomakOkvira
from provjera.jezgra.model.uloge import UlogaOdlomka
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-OKVIRI"

_KLJUCEVI = {
    UlogaOdlomka.NASLOV_SAZETKA: "naslov_u_okviru",
    UlogaOdlomka.NASLOV_POGLAVLJA: "naslov_u_okviru",
    UlogaOdlomka.NASLOV_LITERATURE: "naslov_u_okviru",
    UlogaOdlomka.OSNOVNI_TEKST: "tekst_u_okviru",
}


class Postavke(PostavkeBaza):
    """``[pravila.R-OKVIRI]`` ima samo ``ukljuceno``."""


def _nalaz(o: OdlomakOkvira) -> Nalaz:
    lokacija = Lokacija(Dio.TIJELO, sekcija=o.sekcija, isjecak=o.isjecak)
    return Nalaz(ID, Status.NE_PROLAZI, lokacija, f"{ID}.{_KLJUCEVI[o.uloga]}")


@registriraj(ID, Postavke, poruke=(f"{ID}.prolazi", f"{ID}.naslov_u_okviru", f"{ID}.tekst_u_okviru"))
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    nalazi = [_nalaz(o) for o in model.okviri if o.uloga in _KLJUCEVI]
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.TIJELO), f"{ID}.prolazi")]

"""R-NAZIV (FR-16): web provjerava obrazac, batch točan naziv i način uparivanja."""

from typing import TYPE_CHECKING

from provjera.zajednicko import naziv
from provjera.word.jezgra.jedinice import Jedinica
from provjera.word.jezgra.nalaz import (
    Dio,
    KontekstProvjere,
    Lokacija,
    Nalaz,
    NacinUparivanja,
    Status,
    Vrijednost,
)
from provjera.word.jezgra.pravila.osnova import PostavkeBaza, registriraj

if TYPE_CHECKING:
    from provjera.word.jezgra.profil import Profil

ID = "R-NAZIV"


class Postavke(PostavkeBaza):
    pass


def _nalaz(status: Status, kljuc: str, ocekivano: str, pronadeno: str) -> Nalaz:
    return Nalaz(
        pravilo_id=ID,
        status=status,
        lokacija=Lokacija(Dio.NAZIV),
        poruka_kljuc=kljuc,
        ocekivano=Vrijednost(ocekivano, Jedinica.TEKST),
        pronadeno=Vrijednost(pronadeno, Jedinica.TEKST),
    )


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-NAZIV.prolazi",
        "R-NAZIV.ne_odgovara_obrascu",
        "R-NAZIV.ne_odgovara_ocekivanom",
        "R-NAZIV.nije_tocno_upareno",
    ),
)
def provjeri(model: object, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    pronadeno = naziv.nfc(kontekst.naziv_datoteke)
    if kontekst.ocekivani_naziv is None:
        obrazac = profil.naziv_datoteke.obrazac
        if naziv.odgovara_obrascu(pronadeno, profil):
            return [_nalaz(Status.PROSLO, "R-NAZIV.prolazi", obrazac, pronadeno)]
        return [_nalaz(Status.NE_PROLAZI, "R-NAZIV.ne_odgovara_obrascu", obrazac, pronadeno)]

    ocekivano = naziv.nfc(kontekst.ocekivani_naziv)
    if pronadeno != ocekivano:
        return [_nalaz(Status.NE_PROLAZI, "R-NAZIV.ne_odgovara_ocekivanom", ocekivano, pronadeno)]
    if kontekst.nacin_uparivanja is not NacinUparivanja.TOCAN:
        return [_nalaz(Status.NE_PROLAZI, "R-NAZIV.nije_tocno_upareno", ocekivano, pronadeno)]
    return [_nalaz(Status.PROSLO, "R-NAZIV.prolazi", ocekivano, pronadeno)]

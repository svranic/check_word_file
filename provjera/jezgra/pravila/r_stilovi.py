"""R-STILOVI: osnovni tekst i naslovi oblikuju se kroz stil, ne ručno.

Svojstvo s izvorom ``IZRAVNO`` (zapisano u ``w:pPr`` odlomka ili ``w:rPr`` runa) ne
prolazi ni kad je vrijednost ispravna. Provjeravaju se poravnanje, razmak ispred i iza,
prored i uvlake odlomka te font i veličina runova s vidljivim tekstom; podebljanje,
kurziv, podcrtavanje i ostala svojstva znaka su dopušteni. Ciljnih vrijednosti nema.
Nalazi su nesažeti po odlomku (najviše jedan po ključu i vrijednosti); pokretač ih sažima.
"""

from typing import TYPE_CHECKING

from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.model import DocModel, Efektivno, Odlomak, PraviloProreda
from provjera.jezgra.model.uloge import UlogaOdlomka
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status, Vrijednost, VrstaIzvora
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.jezgra.pravila.runovi import nalaz_odlomka

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-STILOVI"
_ULOGE = (UlogaOdlomka.OSNOVNI_TEKST, UlogaOdlomka.NASLOV_POGLAVLJA, UlogaOdlomka.NASLOV_LITERATURE)


class Postavke(PostavkeBaza):
    """``[pravila.R-STILOVI]`` ima samo ``ukljuceno``."""


def _izravno(efektivno: Efektivno) -> bool:
    return efektivno.izvor.vrsta is VrstaIzvora.IZRAVNO


def _prored(o: Odlomak) -> Vrijednost:
    prored = o.prored.vrijednost
    # Točan ili najmanji prored zapisan je u twipsima, ne u retcima (kao u R-TEKST).
    jedinica = Jedinica.RETCI if prored.pravilo is PraviloProreda.AUTO else Jedinica.TOCKE
    return Vrijednost(prored.iznos, jedinica)


def _odlomak(o: Odlomak) -> list[Nalaz]:
    nalazi: dict[tuple, Nalaz] = {}

    def dodaj(kljuc: str, pronadeno: Vrijednost | None, efektivno: Efektivno, strana: str | None = None) -> None:
        parametri = {"strana": strana} if strana else {}
        # Isti font napisan drukčijim slovima („Calibri“, „calibri“) je jedan nalaz.
        kljuc_iznosa = pronadeno.iznos.casefold() if pronadeno and isinstance(pronadeno.iznos, str) else pronadeno
        nalazi.setdefault((kljuc, kljuc_iznosa, strana),
                          nalaz_odlomka(o, ID, kljuc, parametri, None, pronadeno, efektivno))

    if _izravno(o.poravnanje):
        dodaj("izravno_poravnanje", Vrijednost(o.poravnanje.vrijednost.value, Jedinica.PORAVNANJE), o.poravnanje)
    for efektivno, strana in ((o.razmak_ispred, "ispred"), (o.razmak_iza, "iza")):
        if _izravno(efektivno):
            dodaj("izravni_razmak", Vrijednost(efektivno.vrijednost, Jedinica.TOCKE), efektivno, strana)
    if _izravno(o.prored):
        dodaj("izravni_prored", _prored(o), o.prored)
    for efektivno, strana in ((o.uvlaka_lijevo, "lijevo"), (o.uvlaka_desno, "desno"),
                              (o.uvlaka_prvi_red, "prvi redak")):
        if _izravno(efektivno):
            dodaj("izravna_uvlaka", Vrijednost(efektivno.vrijednost, Jedinica.TWIPS), efektivno, strana)
    for run in o.runovi:
        if not run.tekst.strip():
            continue
        if _izravno(run.font):
            # Font teme zadan izravno bez imena u temi: ručno oblikovanje, vrijednost nepoznata.
            font = run.font.vrijednost
            dodaj("izravni_font", Vrijednost(font, Jedinica.TEKST) if font is not None else None, run.font)
        if _izravno(run.velicina):
            dodaj("izravna_velicina", Vrijednost(run.velicina.vrijednost, Jedinica.POLUTOCKE), run.velicina)
    return list(nalazi.values())


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-STILOVI.prolazi",
        "R-STILOVI.izravni_font",
        "R-STILOVI.izravna_velicina",
        "R-STILOVI.izravno_poravnanje",
        "R-STILOVI.izravni_razmak",
        "R-STILOVI.izravni_prored",
        "R-STILOVI.izravna_uvlaka",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    # Bez odlomaka zadanih uloga nalaz je PROSLO: nedostatke javljaju R-TEKST i R-NASLOVI.
    nalazi = [n for o in model.odlomci if o.uloga in _ULOGE for n in _odlomak(o)]
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.DOKUMENT), f"{ID}.prolazi")]

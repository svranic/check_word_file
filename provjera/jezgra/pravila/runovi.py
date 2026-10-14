"""Zajednička provjera fonta, podebljanja i veličine runova odlomka.

Nije pravilo i ne registrira se: pravila se ne pozivaju međusobno (AD-4), pa R-TEKST,
R-NASLOVI, R-SAZETAK i R-LITERATURA dijele ovu funkciju. Svaki pozivatelj predaje svoj
``pravilo_id``, pa ključevi poruka ostaju ``<ID>.font``, ``<ID>.velicina`` itd.
"""

from collections.abc import Iterable, Mapping

from provjera.jezgra.jedinice import Jedinica, unutar_tolerancije
from provjera.jezgra.model import Efektivno, Odlomak, Run
from provjera.jezgra.nalaz import Dio, Lokacija, Nalaz, Parametar, Status, Vrijednost, VrstaIzvora

_TOLERANCIJA = 0


def lokacija_odlomka(o: Odlomak) -> Lokacija:
    return Lokacija(Dio.TIJELO, sekcija=o.sekcija, odlomak=o.indeks, isjecak=o.isjecak)


def nalaz_odlomka(o: Odlomak, pravilo_id: str, kljuc: str, parametri: Mapping[str, Parametar],
                  ocekivano: Vrijednost | None = None, pronadeno: Vrijednost | None = None,
                  efektivno: Efektivno | None = None, status: Status = Status.NE_PROLAZI) -> Nalaz:
    return nalaz_na(lokacija_odlomka(o), pravilo_id, kljuc, parametri, ocekivano, pronadeno, efektivno, status)


def nalaz_na(lokacija: Lokacija, pravilo_id: str, kljuc: str, parametri: Mapping[str, Parametar],
             ocekivano: Vrijednost | None = None, pronadeno: Vrijednost | None = None,
             efektivno: Efektivno | None = None, status: Status = Status.NE_PROLAZI) -> Nalaz:
    return Nalaz(
        pravilo_id, status, lokacija, f"{pravilo_id}.{kljuc}",
        ocekivano=ocekivano,
        pronadeno=pronadeno,
        izvor=efektivno.izvor if efektivno is not None else None,
        parametri=parametri,
    )


def nalazi_runova(o: Odlomak, pravilo_id: str, font: str, velicina: int,
                  parametri: Mapping[str, Parametar], podebljano: bool | None = None) -> list[Nalaz]:
    """Najviše jedan nalaz po vrsti odstupanja u odlomku, da pojave broje odlomke.

    Font bez vrijednosti (tema nije zapisana) daje ``font_nepoznat`` (neprovjerljivo), a
    font iz teme ``font_tema``. ``podebljano=None`` znači da se podebljanje ne provjerava.
    """
    return nalazi_runova_na(o.runovi, lokacija_odlomka(o), pravilo_id, font, velicina, parametri, podebljano)


def nalazi_runova_na(runovi: Iterable[Run], lokacija: Lokacija, pravilo_id: str, font: str, velicina: int,
                     parametri: Mapping[str, Parametar], podebljano: bool | None = None) -> list[Nalaz]:
    """Kao ``nalazi_runova``, za runove bilo kojeg dijela (npr. podnožja) s danom lokacijom."""
    nalazi: dict[tuple, Nalaz] = {}

    def dodaj(kljuc: str, ocekivano: Vrijednost, pronadeno: Vrijednost | None, efektivno: Efektivno,
              status: Status = Status.NE_PROLAZI) -> None:
        nalaz = nalaz_na(lokacija, pravilo_id, kljuc, parametri, ocekivano, pronadeno, efektivno, status)
        nalazi.setdefault((nalaz.poruka_kljuc, nalaz.pronadeno, nalaz.izvor), nalaz)

    for run in runovi:
        if not run.tekst.strip():
            continue
        if run.font.vrijednost is None:
            dodaj("font_nepoznat", Vrijednost(font, Jedinica.TEKST), None, run.font, Status.NEPROVJERLJIVO)
        elif run.font.vrijednost.casefold() != font.casefold():
            kljuc = "font_tema" if run.font.izvor.vrsta is VrstaIzvora.TEMA else "font"
            dodaj(kljuc, Vrijednost(font, Jedinica.TEKST), Vrijednost(run.font.vrijednost, Jedinica.TEKST), run.font)
        if podebljano is not None and run.podebljano.vrijednost is not podebljano:
            dodaj("podebljano", Vrijednost(podebljano, Jedinica.BOOL),
                  Vrijednost(run.podebljano.vrijednost, Jedinica.BOOL), run.podebljano)
        if not unutar_tolerancije(run.velicina.vrijednost, velicina, _TOLERANCIJA):
            dodaj("velicina", Vrijednost(velicina, Jedinica.POLUTOCKE),
                  Vrijednost(run.velicina.vrijednost, Jedinica.POLUTOCKE), run.velicina)
    return list(nalazi.values())

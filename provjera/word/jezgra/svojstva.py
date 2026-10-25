"""Sadržaj PDF-a sa svojstvima (priča 3.5): čiste funkcije bez I/O-a.

Adapter ``pdf_svojstva`` samo raspoređuje ovaj sadržaj na stranicu. Sve vrijednosti
dolaze iz jedinog izvora istine: margine iz ``formula.margine``, naziv iz
``naziv.kanonski``, a prikaz iz ``poruke.formatiraj`` (isto što student vidi na webu).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from provjera.word.jezgra import formula, jedinice
from provjera.zajednicko import naziv
from provjera.word.jezgra.jedinice import Jedinica
from provjera.word.jezgra.poruke import formatiraj, poruka
from provjera.word.jezgra.profil import Profil


class StudentPopisa(Protocol):
    """Ono što PDF smije znati o studentu (JMBAG se namjerno ne koristi)."""

    rbr: int
    ime: str
    prezime: str
    aktivan: bool


@dataclass(frozen=True)
class RedakSvojstava:
    rbr: int
    ime: str
    prezime: str
    naziv: str
    # Individualne margine; ``None`` uz fiksne margine (navode se u zajedničkim zahtjevima).
    gore: str | None = None
    dolje: str | None = None
    lijevo: str | None = None
    desno: str | None = None


def _margine_tijela(profil: Profil, rbr: int | None) -> dict[str, str]:
    twips = formula.margine(rbr, profil.formula).u_twips()
    return {strana: formatiraj(iznos, Jedinica.TWIPS) for strana, iznos in twips.items()}


def retci(profil: Profil, studenti: Iterable[StudentPopisa]) -> tuple[RedakSvojstava, ...]:
    """Jedan redak po aktivnom studentu, redom po Rbr.; neaktivni se izostavljaju.

    Uz fiksne margine redak nema margina: iste su za sve i idu u zajedničke zahtjeve.
    """
    fiksne = profil.formula.fiksne_margine
    rezultat = []
    for s in sorted((s for s in studenti if s.aktivan), key=lambda s: s.rbr):
        rezultat.append(
            RedakSvojstava(
                rbr=s.rbr,
                ime=s.ime,
                prezime=s.prezime,
                naziv=naziv.kanonski(s.ime, s.prezime, profil),
                **({} if fiksne else _margine_tijela(profil, s.rbr)),
            )
        )
    return tuple(rezultat)


# Svojstva pravila koja se navode u zajedničkim zahtjevima, redom i s jedinicom prikaza.
_SVOJSTVA: dict[str, tuple[tuple[str, Jedinica], ...]] = {
    "R-NAZIV": (),
    "R-SEKCIJE": (),
    "R-MARGINE": (),  # margine naslovnice (i tijela uz fiksne); individualne su u tablici
    "R-TEKST": (
        ("stil", Jedinica.TEKST),
        ("font", Jedinica.TEKST),
        ("velicina", Jedinica.POLUTOCKE),
        ("poravnanje", Jedinica.PORAVNANJE),
        ("razmak_ispred", Jedinica.TOCKE),
        ("razmak_iza", Jedinica.TOCKE),
        ("prored", Jedinica.RETCI),
    ),
    "R-NASLOVI": (
        ("stil", Jedinica.TEKST),
        ("font", Jedinica.TEKST),
        ("velicina", Jedinica.POLUTOCKE),
        ("podebljano", Jedinica.BOOL),
        ("poravnanje", Jedinica.PORAVNANJE),
        ("razmak_ispred", Jedinica.TOCKE),
        ("razmak_iza", Jedinica.TOCKE),
        ("oznaka", Jedinica.TEKST),
    ),
    "R-SAZETAK": (
        ("font", Jedinica.TEKST),
        ("velicina", Jedinica.POLUTOCKE),
        ("poravnanje", Jedinica.PORAVNANJE),
        ("uvlaka_lijevo", Jedinica.TWIPS),
        ("uvlaka_desno", Jedinica.TWIPS),
    ),
    "R-LITERATURA": (
        ("font", Jedinica.TEKST),
        ("velicina", Jedinica.POLUTOCKE),
    ),
    "R-BROJ-STRANICE": (
        ("font", Jedinica.TEKST),
        ("velicina", Jedinica.POLUTOCKE),
    ),
    "R-STILOVI": (),
    "R-PROMJENE": (),
    "R-OKVIRI": (),
}

# Pravila s opisom koji se navodi i kad nema ciljnih vrijednosti.
_OPIS = {
    "R-NAZIV": "pdf.opis.R-NAZIV",
    "R-SEKCIJE": "pdf.opis.R-SEKCIJE",
    "R-PROMJENE": "pdf.opis.R-PROMJENE",
    "R-OKVIRI": "pdf.opis.R-OKVIRI",
    "R-BROJ-STRANICE": "pdf.opis.R-BROJ-STRANICE",
    "R-STILOVI": "pdf.opis.R-STILOVI",
}


def _vrijednost(kljuc: str, iznos: object, jedinica: Jedinica) -> str:
    if isinstance(iznos, Enum):
        iznos = iznos.value
    if kljuc == "oznaka":
        # Predložak „{n}.“ prikazuje se primjerima prvih brojeva: „1., 2., …“.
        iznos = poruka("pdf.oznaka", prvi=iznos.replace("{n}", "1"), drugi=iznos.replace("{n}", "2"))
    return formatiraj(iznos, jedinica)


def _zahtjevi_margina(profil: Profil) -> list[str]:
    """Margine naslovnice (navode se samo uz uključen R-MARGINE)."""
    zahtjevi = []
    fiksne = profil.formula.fiksne_margine
    naslovnica = formatiraj(jedinice.mm_u_twips(profil.formula.naslovnica), Jedinica.TWIPS)
    opis = "pdf.opis.naslovnica_fiksne" if fiksne else "pdf.opis.naslovnica"
    zahtjevi.append(
        poruka(
            "pdf.zahtjev",
            naziv=poruka("pdf.naslovnica"),
            svojstva=poruka(opis, naslovnica=naslovnica),
        )
    )
    return zahtjevi


def zajednicki_zahtjevi(profil: Profil) -> tuple[str, ...]:
    """Zahtjevi isti za sve studente; isključena pravila (i ona bez vrijednosti) se ne navode.

    Uz fiksne margine margine tijela navode se uvijek, kao što ih tablica u individualnom
    načinu uvijek ima, neovisno o uključenosti R-MARGINE.
    """
    zahtjevi = []
    if profil.formula.fiksne_margine:
        zahtjevi.append(
            poruka(
                "pdf.zahtjev",
                naziv=poruka("pdf.margine_tijela"),
                svojstva=poruka("pdf.opis.margine_tijela", **_margine_tijela(profil, None)),
            )
        )
    for pravilo_id, svojstva in _SVOJSTVA.items():
        postavke = profil.pravila.get(pravilo_id)
        if postavke is None or not postavke.ukljuceno:
            continue
        if pravilo_id == "R-MARGINE":
            zahtjevi += _zahtjevi_margina(profil)
            continue
        dijelovi = (
            [poruka(_OPIS[pravilo_id], obrazac=profil.naziv_datoteke.obrazac)]
            if pravilo_id in _OPIS
            else []
        )
        for kljuc, jedinica in svojstva:
            iznos = getattr(postavke, kljuc, None)
            if iznos is not None:
                dijelovi.append(
                    poruka(f"pdf.svojstvo.{kljuc}", vrijednost=_vrijednost(kljuc, iznos, jedinica))
                )
        if dijelovi:
            zahtjevi.append(
                poruka(
                    "pdf.zahtjev",
                    naziv=poruka(f"pravilo.{pravilo_id}"),
                    svojstva=poruka("pdf.razdjelnik").join(dijelovi),
                )
            )
    return tuple(zahtjevi)

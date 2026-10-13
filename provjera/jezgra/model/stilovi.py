"""Razrješavanje stilova i teme (AD-3): jedini razrješavač efektivnih vrijednosti.

Lanac: docDefaults → tema → ``basedOn`` lanac → stil odlomka → stil znaka → izravno.
Svaka vrijednost nosi izvor (``Izvor``). Veličine su u polutočkama, razmaci i uvlake
u twipsima, prored u 240-inama retka (pravilo „auto“) ili twipsima (točno/najmanje).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

from docx.oxml.ns import qn

from provjera.jezgra.nalaz import Izvor, VrstaIzvora

T = TypeVar("T")

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_ISTINA = {"1", "true", "on"}
_NAJVECA_DUBINA = 64
# Word za „auto“ razmak (HTML) koristi 14 pt.
_AUTO_RAZMAK = 280

ZADANO = Izvor(VrstaIzvora.ZADANO)
TEMA = Izvor(VrstaIzvora.TEMA)
IZRAVNO = Izvor(VrstaIzvora.IZRAVNO)


class Poravnanje(Enum):
    LIJEVO = "lijevo"
    SREDINA = "sredina"
    DESNO = "desno"
    OBOSTRANO = "obostrano"
    OSTALO = "ostalo"


_PORAVNANJA = {
    "left": Poravnanje.LIJEVO,
    "start": Poravnanje.LIJEVO,
    "center": Poravnanje.SREDINA,
    "right": Poravnanje.DESNO,
    "end": Poravnanje.DESNO,
    "both": Poravnanje.OBOSTRANO,
}


class PraviloProreda(Enum):
    AUTO = "auto"
    TOCNO = "exact"
    NAJMANJE = "atLeast"


@dataclass(frozen=True)
class Prored:
    """``AUTO``: iznos u 240-inama retka (240 = jednostruko); inače u twipsima."""

    pravilo: PraviloProreda
    iznos: int


@dataclass(frozen=True)
class Efektivno(Generic[T]):
    """Efektivna vrijednost i odakle dolazi; ``None`` znači da je nije moguće odrediti."""

    vrijednost: T
    izvor: Izvor


@dataclass(frozen=True)
class Stil:
    kanonski_id: str
    ime: str


# Wordove zadane vrijednosti kad ih ne zapisuje ni docDefaults ni stil.
_WORD_PPR: dict[str, Any] = {
    "poravnanje": Poravnanje.LIJEVO,
    "razmak_ispred": 0,
    "razmak_iza": 0,
    "prored": Prored(PraviloProreda.AUTO, 240),
    "uvlaka_lijevo": 0,
    "uvlaka_desno": 0,
    "uvlaka_prvi_red": 0,
    "numeriran": False,
}
_WORD_RPR: dict[str, Any] = {"font": None, "velicina": 20}


def _je_istina(element, atribut: str = "w:val") -> bool:
    return element.get(qn(atribut), "true").lower() in _ISTINA


def _cijeli(element, atribut: str) -> int | None:
    vrijednost = element.get(qn(atribut))
    return None if vrijednost is None else int(vrijednost)


def iz_ppr(ppr) -> dict[str, Any]:
    """Svojstva odlomka zapisana u jednom ``w:pPr`` (bez nasljeđivanja)."""
    van: dict[str, Any] = {}
    if ppr is None:
        return van
    jc = ppr.find(qn("w:jc"))
    if jc is not None and jc.get(qn("w:val")):
        van["poravnanje"] = _PORAVNANJA.get(jc.get(qn("w:val")), Poravnanje.OSTALO)
    razmak = ppr.find(qn("w:spacing"))
    if razmak is not None:
        for kljuc, atribut in (("razmak_ispred", "before"), ("razmak_iza", "after")):
            auto = razmak.get(qn(f"w:{atribut}Autospacing"))
            if auto is not None and auto.lower() in _ISTINA:
                van[kljuc] = _AUTO_RAZMAK
            elif (iznos := _cijeli(razmak, f"w:{atribut}")) is not None:
                van[kljuc] = iznos
        if (redak := _cijeli(razmak, "w:line")) is not None:
            pravilo = razmak.get(qn("w:lineRule"), "auto")
            van["prored"] = Prored(PraviloProreda(pravilo) if pravilo in ("auto", "exact", "atLeast")
                                   else PraviloProreda.AUTO, redak)
    uvlaka = ppr.find(qn("w:ind"))
    if uvlaka is not None:
        for kljuc, atributi in (("uvlaka_lijevo", ("w:left", "w:start")), ("uvlaka_desno", ("w:right", "w:end"))):
            for atribut in atributi:
                if (iznos := _cijeli(uvlaka, atribut)) is not None:
                    van[kljuc] = iznos
                    break
        if (iznos := _cijeli(uvlaka, "w:hanging")) is not None:
            van["uvlaka_prvi_red"] = -iznos
        elif (iznos := _cijeli(uvlaka, "w:firstLine")) is not None:
            van["uvlaka_prvi_red"] = iznos
    numeracija = ppr.find(qn("w:numPr"))
    if numeracija is not None:
        broj = numeracija.find(qn("w:numId"))
        if broj is not None:
            van["numeriran"] = broj.get(qn("w:val"), "0") != "0"
    return van


def iz_rpr(rpr) -> dict[str, Any]:
    """Svojstva znaka zapisana u jednom ``w:rPr``; font je ``("tema", ref)`` ili ``("ime", font)``."""
    van: dict[str, Any] = {}
    if rpr is None:
        return van
    fontovi = rpr.find(qn("w:rFonts"))
    if fontovi is not None:
        # Atribut teme ima prednost pred imenom fonta u istom elementu.
        if tema := fontovi.get(qn("w:asciiTheme")):
            van["font"] = ("tema", tema)
        elif ime := fontovi.get(qn("w:ascii")):
            van["font"] = ("ime", ime)
    velicina = rpr.find(qn("w:sz"))
    if velicina is not None and (iznos := _cijeli(velicina, "w:val")) is not None:
        van["velicina"] = iznos
    return van


@dataclass(frozen=True)
class _Definicija:
    id: str
    tip: str
    ime: str
    kanonski_id: str
    osnova: str | None
    ppr: Any
    rpr: Any
    zadani: bool


def kanonski_id(style_id: str, ime: str | None, prilagoden: bool) -> str:
    """Ugrađeni stil po ugrađenom imenu neovisno o jeziku Worda; prilagođeni po ``styleId``."""
    if prilagoden or not ime:
        return style_id
    if pogodak := re.fullmatch(r"(?i)toc\s*(\d)", ime.strip()):
        return f"TOC{pogodak[1]}"
    if ime.strip().lower() == "toc heading":
        return "TOCHeading"
    rijeci = re.split(r"[^0-9A-Za-z]+", ime)
    return "".join(r[:1].upper() + r[1:] for r in rijeci if r) or style_id


def _definicije(styles) -> dict[str, _Definicija]:
    definicije = {}
    if styles is None:
        return definicije
    for stil in styles.iterchildren(qn("w:style")):
        style_id = stil.get(qn("w:styleId"))
        if not style_id:
            continue
        ime_el = stil.find(qn("w:name"))
        ime = ime_el.get(qn("w:val")) if ime_el is not None else None
        osnova_el = stil.find(qn("w:basedOn"))
        prilagoden = stil.get(qn("w:customStyle"), "0").lower() in _ISTINA
        definicije[style_id] = _Definicija(
            id=style_id,
            tip=stil.get(qn("w:type"), "paragraph"),
            ime=ime or style_id,
            kanonski_id=kanonski_id(style_id, ime, prilagoden),
            osnova=osnova_el.get(qn("w:val")) if osnova_el is not None else None,
            ppr=stil.find(qn("w:pPr")),
            rpr=stil.find(qn("w:rPr")),
            zadani=stil.get(qn("w:default"), "0").lower() in _ISTINA,
        )
    return definicije


def _fontovi_teme(tema) -> dict[str, str | None]:
    fontovi: dict[str, str | None] = {"minor": None, "major": None}
    if tema is None:
        return fontovi
    for vrsta in fontovi:
        latin = next(tema.iter(f"{_A}{vrsta}Font"), None)
        latin = latin.find(f"{_A}latin") if latin is not None else None
        if latin is not None and latin.get("typeface"):
            fontovi[vrsta] = latin.get("typeface")
    return fontovi


class Stilovi:
    """Razrješavač nad ``styles.xml`` i ``theme1.xml``, s predmemorijom po stilu."""

    def __init__(self, styles, tema) -> None:
        self._definicije = _definicije(styles)
        self._fontovi_teme = _fontovi_teme(tema)
        self.ima_temu = tema is not None
        zadani = styles.find(qn("w:docDefaults")) if styles is not None else None
        self._zadani_ppr = zadani.find(f"{qn('w:pPrDefault')}/{qn('w:pPr')}") if zadani is not None else None
        self._zadani_rpr = zadani.find(f"{qn('w:rPrDefault')}/{qn('w:rPr')}") if zadani is not None else None
        self._zadani_stil_odlomka = next(
            (d.id for d in self._definicije.values() if d.tip == "paragraph" and d.zadani), None
        )
        self._ppr_stila: dict[str | None, dict[str, Efektivno]] = {}
        self._rpr_stila: dict[tuple[str | None, str | None], dict[str, Efektivno]] = {}

    # --- stilovi ----------------------------------------------------------

    def id_stila_odlomka(self, style_id: str | None) -> str | None:
        definicija = self._definicije.get(style_id) if style_id else None
        if definicija is not None and definicija.tip == "paragraph":
            return definicija.id
        return self._zadani_stil_odlomka

    def stil(self, style_id: str | None) -> Stil:
        definicija = self._definicije.get(style_id) if style_id else None
        if definicija is None:
            # Dokument bez stilova: Word primjenjuje ugrađeni Normal.
            return Stil("Normal", "Normal")
        return Stil(definicija.kanonski_id, definicija.ime)

    def _lanac(self, style_id: str | None, tip: str) -> Iterator[_Definicija]:
        """Stilovi od korijena ``basedOn`` lanca do zadanog stila."""
        lanac, vidjeni = [], set()
        while style_id and style_id not in vidjeni and len(lanac) < _NAJVECA_DUBINA:
            definicija = self._definicije.get(style_id)
            if definicija is None or definicija.tip != tip:
                break
            vidjeni.add(style_id)
            lanac.append(definicija)
            style_id = definicija.osnova
        return reversed(lanac)

    # --- razrješavanje ----------------------------------------------------

    def _font(self, sirovo: Any, izvor: Izvor) -> Efektivno[str | None]:
        vrsta, ime = sirovo
        if vrsta == "ime":
            return Efektivno(ime, izvor)
        kljuc = "major" if ime.lower().startswith("major") else "minor"
        return Efektivno(self._fontovi_teme[kljuc], TEMA)

    def ppr_stila(self, style_id: str | None) -> dict[str, Efektivno]:
        if style_id not in self._ppr_stila:
            svojstva = {k: Efektivno(v, ZADANO) for k, v in _WORD_PPR.items()}
            for k, v in iz_ppr(self._zadani_ppr).items():
                svojstva[k] = Efektivno(v, ZADANO)
            for definicija in self._lanac(style_id, "paragraph"):
                izvor = Izvor(VrstaIzvora.STIL, definicija.ime)
                for k, v in iz_ppr(definicija.ppr).items():
                    svojstva[k] = Efektivno(v, izvor)
            self._ppr_stila[style_id] = svojstva
        return self._ppr_stila[style_id]

    def ppr_odlomka(self, style_id: str | None, ppr) -> dict[str, Efektivno]:
        svojstva = dict(self.ppr_stila(style_id))
        for k, v in iz_ppr(ppr).items():
            svojstva[k] = Efektivno(v, IZRAVNO)
        return svojstva

    def rpr_stila(self, stil_odlomka: str | None, stil_znaka: str | None) -> dict[str, Efektivno]:
        kljuc = (stil_odlomka, stil_znaka)
        if kljuc not in self._rpr_stila:
            svojstva: dict[str, Efektivno] = {k: Efektivno(v, ZADANO) for k, v in _WORD_RPR.items()}
            razine = [(ZADANO, self._zadani_rpr)]
            razine += [(Izvor(VrstaIzvora.STIL, d.ime), d.rpr) for d in self._lanac(stil_odlomka, "paragraph")]
            razine += [(Izvor(VrstaIzvora.STIL, d.ime), d.rpr) for d in self._lanac(stil_znaka, "character")]
            for izvor, rpr in razine:
                for k, v in iz_rpr(rpr).items():
                    svojstva[k] = self._font(v, izvor) if k == "font" else Efektivno(v, izvor)
            self._rpr_stila[kljuc] = svojstva
        return self._rpr_stila[kljuc]

    def rpr_runa(self, stil_odlomka: str | None, stil_znaka: str | None, rpr) -> dict[str, Efektivno]:
        svojstva = self.rpr_stila(stil_odlomka, stil_znaka)
        izravno = iz_rpr(rpr)
        if not izravno:
            return svojstva
        svojstva = dict(svojstva)
        for k, v in izravno.items():
            svojstva[k] = self._font(v, IZRAVNO) if k == "font" else Efektivno(v, IZRAVNO)
        return svojstva

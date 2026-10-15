"""Podnožja sekcija (priča 2.5): jedini razrješavač podnožja i polja broja stranice.

Vrste podnožja (zadano, prva, parna) čitaju se iz ``w:footerReference`` u ``w:sectPr``.
Vrsta bez reference nasljeđuje se od iste vrste prethodne sekcije; bez nje je podnožje
prazno. Dijelovi paketa samo se čitaju: python-docx ``_get_definition`` bi dodao novu
definiciju podnožja, pa se ne koristi.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from enum import Enum

from docx.oxml.ns import qn
from docx.oxml.parser import parse_xml

from provjera.jezgra.model.stilovi import Run, Stilovi

_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_ISTINA = {"1", "true", "on"}
_RIJECI = re.compile(r"[\s\\]+")
# Sadržaj koji se ne čita: svojstva (bez teksta i polja) i izbrisani tekst.
_PRESKOCI = {qn(t) for t in ("w:pPr", "w:rPr", "w:sdtPr", "w:del", "w:moveFrom", "w:sectPr")}
_TEKST_RUNA = {
    qn("w:t"): None,
    qn("w:tab"): "\t",
    qn("w:ptab"): "\t",  # pozicijski tabulator koji Word umeće u podnožja
    qn("w:br"): "\n",
    qn("w:cr"): "\n",
    qn("w:noBreakHyphen"): "-",
}


class VrstaPodnozja(Enum):
    ZADANO = "default"
    PRVA = "first"
    PARNA = "even"


@dataclass(frozen=True)
class PoljeStranice:
    """Polje ``PAGE``; ``runovi`` su runovi rezultata, a bez rezultata runovi s naredbom."""

    runovi: tuple[Run, ...]


@dataclass(frozen=True)
class Podnozje:
    polja_stranice: tuple[PoljeStranice, ...] = ()
    # Tekst koji nije ni u jednom polju (ni u rezultatu ni u naredbi).
    tekst_izvan_polja: str = ""
    # Isti tekst po odlomku podnožja (samostalni ručni broj traži se po odlomku).
    odlomci_izvan_polja: tuple[str, ...] = ()
    # Identitet dijela podnožja (ime dijela u paketu); sekcije povezane s prethodnom
    # dijele isti dio. ``None`` znači da podnožja nema.
    dio: str | None = None


PRAZNO = Podnozje()


@dataclass(frozen=True)
class PodnozjaSekcije:
    """Razriješena podnožja jedne sekcije po vrsti (s nasljeđivanjem)."""

    zadano: Podnozje = PRAZNO
    prva: Podnozje = PRAZNO
    parna: Podnozje = PRAZNO

    def po_vrsti(self, vrsta: VrstaPodnozja) -> Podnozje:
        return {VrstaPodnozja.ZADANO: self.zadano, VrstaPodnozja.PRVA: self.prva,
                VrstaPodnozja.PARNA: self.parna}[vrsta]


def je_istina(element) -> bool:
    """Uključeno svojstvo (``w:titlePg``, ``w:evenAndOddHeaders``); ``None`` je isključeno."""
    return element is not None and element.get(qn("w:val"), "true").lower() in _ISTINA


# --- polja ------------------------------------------------------------------------


@dataclass
class _Polje:
    naredba: list[str] = field(default_factory=list)
    runovi_naredbe: list[Run] = field(default_factory=list)
    runovi_rezultata: list[Run] = field(default_factory=list)
    u_rezultatu: bool = False

    def je_broj_stranice(self) -> bool:
        # Prva riječ naredbe; prekidač smije slijediti bez razmaka („PAGE\\* Arabic“).
        rijeci = _RIJECI.split("".join(self.naredba).strip())
        return rijeci[0].upper() == "PAGE"

    def zavrsi(self) -> PoljeStranice | None:
        if not self.je_broj_stranice():
            return None
        return PoljeStranice(tuple(self.runovi_rezultata or self.runovi_naredbe))


class _Citac:
    """Obilazi jedno podnožje redom dokumenta i prati složena polja kroz runove i odlomke."""

    def __init__(self, stilovi: Stilovi) -> None:
        self._stilovi = stilovi
        self._stog: list[_Polje] = []
        self.polja: list[PoljeStranice] = []
        self.izvan: list[str] = []
        # Tekst izvan polja po odlomku; stog jer tekstni okvir ima odlomke unutar odlomka.
        self._odlomci: list[list[str]] = []
        self.odlomci: list[str] = []

    def _run(self, tekst: str, stil_odlomka: str | None, r) -> Run:
        rpr = r.find(qn("w:rPr")) if r is not None else None
        rstyle = rpr.find(qn("w:rStyle")) if rpr is not None else None
        stil_znaka = rstyle.get(qn("w:val")) if rstyle is not None else None
        svojstva = self._stilovi.rpr_runa(stil_odlomka, stil_znaka, rpr)
        return Run(tekst, svojstva["font"], svojstva["velicina"], svojstva["podebljano"])

    def _zavrsi(self, polje: _Polje) -> None:
        if (polje_stranice := polje.zavrsi()) is not None:
            self.polja.append(polje_stranice)

    def _tekst(self, tekst: str, stil_odlomka: str | None, r) -> None:
        if not self._stog:
            self.izvan.append(tekst)
            if self._odlomci:
                self._odlomci[-1].append(tekst)
            return
        if not tekst.strip():
            return
        run = None
        for polje in self._stog:
            if polje.u_rezultatu:
                run = run or self._run(tekst, stil_odlomka, r)
                polje.runovi_rezultata.append(run)

    def _citaj_run(self, r, stil_odlomka: str | None) -> None:
        dijelovi: list[str] = []

        def isprazni() -> None:
            if dijelovi:
                self._tekst("".join(dijelovi), stil_odlomka, r)
                dijelovi.clear()

        for dijete in _djeca(r):
            oznaka = dijete.tag
            if oznaka == qn("w:fldChar"):
                isprazni()
                vrsta = dijete.get(qn("w:fldCharType"))
                if vrsta == "begin":
                    self._stog.append(_Polje())
                elif vrsta == "separate" and self._stog:
                    self._stog[-1].u_rezultatu = True
                elif vrsta == "end" and self._stog:
                    self._zavrsi(self._stog.pop())
            elif oznaka == qn("w:instrText"):
                isprazni()
                if self._stog and not self._stog[-1].u_rezultatu:
                    polje = self._stog[-1]
                    polje.naredba.append(dijete.text or "")
                    polje.runovi_naredbe.append(self._run(dijete.text or "", stil_odlomka, r))
            elif oznaka in _TEKST_RUNA:
                zamjena = _TEKST_RUNA[oznaka]
                dijelovi.append((dijete.text or "") if zamjena is None else zamjena)
            elif isinstance(oznaka, str) and oznaka not in _PRESKOCI:
                # Slika ili oblik u runu može sadržavati tekstni okvir (w:txbxContent).
                isprazni()
                self.citaj(dijete, stil_odlomka)
        isprazni()

    def _citaj_jednostavno(self, fld, stil_odlomka: str | None) -> None:
        naredba = fld.get(qn("w:instr")) or ""
        polje = _Polje(naredba=[naredba], u_rezultatu=True)
        # Bez runova rezultata polje preuzima oblikovanje odlomka.
        polje.runovi_naredbe.append(self._run(naredba, stil_odlomka, None))
        self._stog.append(polje)
        self.citaj(fld, stil_odlomka)
        self._zavrsi(self._stog.pop())

    def citaj(self, element, stil_odlomka: str | None) -> None:
        for dijete in _djeca(element):
            oznaka = dijete.tag
            if oznaka == qn("w:p"):
                ppr = dijete.find(qn("w:pPr"))
                pstyle = ppr.find(qn("w:pStyle")) if ppr is not None else None
                stil = self._stilovi.id_stila_odlomka(pstyle.get(qn("w:val")) if pstyle is not None else None)
                self._odlomci.append([])
                self.citaj(dijete, stil)
                self.odlomci.append("".join(self._odlomci.pop()))
            elif oznaka == qn("w:r"):
                self._citaj_run(dijete, stil_odlomka)
            elif oznaka == qn("w:fldSimple"):
                self._citaj_jednostavno(dijete, stil_odlomka)
            elif isinstance(oznaka, str) and oznaka not in _PRESKOCI:
                # sdt, sdtContent, tablice, hiperveze, txbxContent i ostali spremnici.
                self.citaj(dijete, stil_odlomka)

    def podnozje(self) -> Podnozje:
        # Nezatvorena polja (oštećeno podnožje) završavaju na kraju dijela.
        while self._stog:
            self._zavrsi(self._stog.pop())
        return Podnozje(tuple(self.polja), "".join(self.izvan), tuple(self.odlomci))


def _djeca(element) -> Iterator:
    """Djeca elementa; od ``mc:AlternateContent`` samo prva grana, da se okvir ne broji dvaput."""
    for dijete in element.iterchildren():
        if dijete.tag == f"{_MC}AlternateContent":
            grana = dijete.find(f"{_MC}Choice")
            if grana is None:
                grana = dijete.find(f"{_MC}Fallback")
            if grana is not None:
                yield from _djeca(grana)
        else:
            yield dijete


def procitaj_podnozje(korijen, stilovi: Stilovi, dio: str | None = None) -> Podnozje:
    """Polja ``PAGE`` i tekst izvan polja jednog ``w:ftr``; ``dio`` je identitet dijela."""
    citac = _Citac(stilovi)
    citac.citaj(korijen, None)
    return replace(citac.podnozje(), dio=dio)


# --- sekcije ----------------------------------------------------------------------


def _korijen_dijela(dio):
    """Korijen dijela; ``None`` ako se XML ne može parsirati."""
    element = getattr(dio, "element", None)
    if element is not None:
        return element
    try:
        return parse_xml(dio.blob)
    except Exception:  # noqa: BLE001 — nečitljivo podnožje ne smije srušiti cijeli model
        return None


def _reference(sectpr) -> dict[VrstaPodnozja, str]:
    reference = {}
    for ref in sectpr.iterchildren(qn("w:footerReference")):
        try:
            vrsta = VrstaPodnozja(ref.get(qn("w:type"), "default"))
        except ValueError:
            continue
        if (r_id := ref.get(_R_ID)) is not None:
            reference[vrsta] = r_id
    return reference


def podnozja_sekcija(dokument_dio, sectpr_sekcija: list, stilovi: Stilovi) -> list[PodnozjaSekcije]:
    """Razriješena podnožja po sekciji; ``dokument_dio`` je glavni dio dokumenta.

    Referenca na nepostojeći dio daje prazno podnožje (Word takav dokument ne otvara).
    """
    procitana: dict[str, Podnozje] = {}

    def podnozje(r_id: str) -> Podnozje:
        if r_id not in procitana:
            dio = dokument_dio.related_parts.get(r_id)
            procitana[r_id] = (
                PRAZNO if (korijen := None if dio is None else _korijen_dijela(dio)) is None
                else procitaj_podnozje(korijen, stilovi, str(dio.partname))
            )
        return procitana[r_id]

    rezultat, prethodna = [], {v: PRAZNO for v in VrstaPodnozja}
    for sectpr in sectpr_sekcija:
        reference = _reference(sectpr)
        trenutna = {v: podnozje(reference[v]) if v in reference else prethodna[v] for v in VrstaPodnozja}
        rezultat.append(PodnozjaSekcije(
            zadano=trenutna[VrstaPodnozja.ZADANO],
            prva=trenutna[VrstaPodnozja.PRVA],
            parna=trenutna[VrstaPodnozja.PARNA],
        ))
        prethodna = trenutna
    return rezultat


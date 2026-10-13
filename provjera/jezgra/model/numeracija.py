"""Numeracija (AD-3): jedini razrješavač ``numbering.xml`` u stvarne oznake odlomaka.

Brojači se vode po ``abstractNum`` i razini, redom dokumenta: dublje razine se
resetiraju, a ``startOverride`` se primjenjuje pri prvoj upotrebi ``numId``.
``numId="0"``, nepostojeći ``numId`` i ``numFmt="none"`` znače da odlomak nema numeraciju.
"""

import re
from dataclasses import dataclass

from docx.oxml.ns import qn

_RAZINA = re.compile(r"%([1-9])")
_RIMSKI = (
    (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
    (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
)


@dataclass(frozen=True)
class Numeracija:
    """Razina (0-bazirana), format (``numFmt``), uzorak (``lvlText``) i stvarna oznaka („1.“)."""

    razina: int
    format: str
    uzorak: str
    oznaka: str


@dataclass(frozen=True)
class _Razina:
    start: int
    format: str
    uzorak: str
    stil: str | None


def _val(element, oznaka: str) -> str | None:
    cilj = element.find(qn(oznaka)) if element is not None else None
    return cilj.get(qn("w:val")) if cilj is not None else None


def _cijeli(tekst: str | None, zadano: int | None = None) -> int | None:
    try:
        return int(tekst) if tekst is not None else zadano
    except ValueError:
        return zadano


def _razina(lvl, osnova: _Razina | None = None) -> _Razina:
    """``w:lvl``; nezapisana svojstva uzima iz ``osnova`` (za ``lvlOverride``)."""
    start = _cijeli(_val(lvl, "w:start"))
    oblik = _val(lvl, "w:numFmt")
    uzorak = _val(lvl, "w:lvlText")
    stil = _val(lvl, "w:pStyle")
    return _Razina(
        start=start if start is not None else (osnova.start if osnova else 0),
        format=oblik if oblik is not None else (osnova.format if osnova else "decimal"),
        uzorak=uzorak if uzorak is not None else (osnova.uzorak if osnova else ""),
        stil=stil if stil is not None else (osnova.stil if osnova else None),
    )


def _razine(element) -> dict[int, _Razina]:
    razine = {}
    for lvl in element.iterchildren(qn("w:lvl")):
        ilvl = _cijeli(lvl.get(qn("w:ilvl")))
        if ilvl is not None and 0 <= ilvl <= 8:
            razine[ilvl] = _razina(lvl)
    return razine


def _rimski(broj: int) -> str:
    van = []
    for vrijednost, znak in _RIMSKI:
        while broj >= vrijednost:
            van.append(znak)
            broj -= vrijednost
    return "".join(van)


def _slovo(broj: int) -> str:
    # Word nakon „z“ ponavlja slovo: aa, bb, …
    if broj <= 0:
        return str(broj)
    return chr(ord("a") + (broj - 1) % 26) * ((broj - 1) // 26 + 1)


def formatiraj_broj(broj: int, oblik: str) -> str:
    """Redni broj u formatu razine; nepoznati formati prikazuju se kao decimalni."""
    if oblik == "lowerLetter":
        return _slovo(broj)
    if oblik == "upperLetter":
        return _slovo(broj).upper()
    if oblik == "lowerRoman":
        return _rimski(broj) if broj > 0 else str(broj)
    if oblik == "decimalZero":
        return f"{broj:02d}"
    if oblik == "upperRoman":
        return _rimski(broj).upper() if broj > 0 else str(broj)
    return str(broj)


@dataclass(frozen=True)
class _Num:
    apstraktni: str
    razine: dict[int, _Razina]
    pocetci: dict[int, int]


class Brojaci:
    """Razrješava numeraciju odlomaka; ``sljedeca`` se poziva redom dokumenta."""

    def __init__(self, numbering) -> None:
        apstraktni: dict[str, dict[int, _Razina]] = {}
        self._num: dict[str, _Num] = {}
        if numbering is None:
            return
        po_stilu: dict[str, str] = {}
        poveznice: dict[str, str] = {}
        brojac: dict[str, str] = {}
        for element in numbering.iterchildren(qn("w:abstractNum")):
            if (id_ := element.get(qn("w:abstractNumId"))) is not None:
                apstraktni[id_] = _razine(element)
                if (stil := _val(element, "w:styleLink")) is not None:
                    po_stilu[stil] = id_
                if (stil := _val(element, "w:numStyleLink")) is not None:
                    poveznice[id_] = stil
        # numStyleLink: razine su u abstractNum čiji styleLink ima isto ime stila numeracije.
        for id_, stil in poveznice.items():
            if not apstraktni[id_] and (cilj := po_stilu.get(stil)) is not None:
                apstraktni[id_] = apstraktni[cilj]
                brojac[id_] = cilj  # povezani popisi dijele brojače
        for element in numbering.iterchildren(qn("w:num")):
            num_id, apstraktni_id = element.get(qn("w:numId")), _val(element, "w:abstractNumId")
            if num_id is None or apstraktni_id not in apstraktni:
                continue
            razine, pocetci = dict(apstraktni[apstraktni_id]), {}
            for nadjacavanje in element.iterchildren(qn("w:lvlOverride")):
                ilvl = _cijeli(nadjacavanje.get(qn("w:ilvl")))
                if ilvl is None or not 0 <= ilvl <= 8:
                    continue
                if (lvl := nadjacavanje.find(qn("w:lvl"))) is not None:
                    razine[ilvl] = _razina(lvl, razine.get(ilvl))
                if (pocetak := _cijeli(_val(nadjacavanje, "w:startOverride"))) is not None:
                    pocetci[ilvl] = pocetak
            self._num[num_id] = _Num(brojac.get(apstraktni_id, apstraktni_id), razine, pocetci)
        self._brojaci: dict[str, list[int | None]] = {}
        self._koristeni: set[str] = set()

    def sljedeca(self, num_id: str | None, ilvl: int | None, stil_id: str | None) -> Numeracija | None:
        """Numeracija sljedećeg odlomka; ``None`` znači da odlomak nije numeriran."""
        if not num_id or num_id == "0" or num_id not in self._num:
            return None
        num = self._num[num_id]
        if ilvl is None:
            # Bez ilvl Word uzima razinu povezanu sa stilom odlomka, inače prvu.
            ilvl = next((i for i, r in sorted(num.razine.items()) if stil_id and r.stil == stil_id), 0)
        razina = num.razine.get(ilvl)
        if razina is None or razina.format == "none":
            return None
        brojaci = self._brojaci.setdefault(num.apstraktni, [None] * 9)
        if num_id not in self._koristeni:
            self._koristeni.add(num_id)
            for i, pocetak in num.pocetci.items():
                brojaci[i] = pocetak - 1
        trenutni = brojaci[ilvl]
        brojaci[ilvl] = razina.start if trenutni is None else trenutni + 1
        for dublja in range(ilvl + 1, 9):
            brojaci[dublja] = None

        def zamijeni(pogodak: re.Match) -> str:
            i = int(pogodak[1]) - 1
            r = num.razine.get(i)
            if r is None:
                return ""
            broj = brojaci[i] if brojaci[i] is not None else r.start
            return formatiraj_broj(broj, r.format)

        return Numeracija(ilvl, razina.format, razina.uzorak, _RAZINA.sub(zamijeni, razina.uzorak))

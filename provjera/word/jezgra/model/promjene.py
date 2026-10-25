"""Praćene promjene i tekstni okviri (priča 2.6).

Model gradi prihvaćeno stanje: sadržaj iz ``w:ins``/``w:moveTo`` se čita, iz
``w:del``/``w:moveFrom`` ne, a svojstva se čitaju iz trenutnog ``pPr``/``rPr`` (nikad
iz ``*PrChange``). Ovdje se samo broje elementi promjena (za R-PROMJENE) i pronalaze
odlomci tekstnih okvira i oblika (za R-OKVIRI).
"""

from collections.abc import Iterator

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.oxml.parser import parse_xml

_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

# Elementi praćenih promjena: sadržaj, premještanje, svojstva i ćelije tablica.
OZNAKE_PROMJENA = tuple(
    qn(t)
    for t in (
        "w:ins",
        "w:del",
        "w:moveFrom",
        "w:moveTo",
        "w:pPrChange",
        "w:rPrChange",
        "w:sectPrChange",
        "w:tblPrChange",
        "w:tblPrExChange",
        "w:tblGridChange",
        "w:trPrChange",
        "w:tcPrChange",
        "w:numberingChange",
        "w:cellIns",
        "w:cellDel",
        "w:cellMerge",
    )
)

# Dijelovi uz tijelo u kojima se broje promjene.
_DIJELOVI = (RT.HEADER, RT.FOOTER, RT.FOOTNOTES, RT.ENDNOTES)
_TXBX = qn("w:txbxContent")
# Sadržaj koji se ne obilazi pri traženju okvira: svojstva i izbrisani sadržaj.
_PRESKOCI = {qn(t) for t in ("w:pPr", "w:rPr", "w:sdtPr", "w:del", "w:moveFrom")}
_IZBRISANA_OZNAKA = (
    f"{qn('w:pPr')}/{qn('w:rPr')}/{qn('w:del')}",
    f"{qn('w:pPr')}/{qn('w:rPr')}/{qn('w:moveFrom')}",
)


def _korijen(dio):
    element = getattr(dio, "element", None)
    return element if element is not None else parse_xml(dio.blob)


def _broj(element) -> int:
    return sum(1 for _ in element.iter(*OZNAKE_PROMJENA))


def pracene_promjene(dokument) -> int:
    """Broj elemenata praćenih promjena u tijelu, zaglavljima, podnožjima, fusnotama i endnotama."""
    ukupno = _broj(dokument.element)
    vidjeni: set[str] = set()
    for rel in dokument.part.rels.values():
        if rel.is_external or rel.reltype not in _DIJELOVI:
            continue
        dio = rel.target_part
        if str(dio.partname) in vidjeni:
            continue
        vidjeni.add(str(dio.partname))
        try:
            korijen = _korijen(dio)
        except Exception:  # noqa: BLE001 — nečitljiv dio ne smije srušiti cijeli model
            continue
        ukupno += _broj(korijen)
    return ukupno


def izbrisana_oznaka(p) -> bool:
    """Je li oznaka odlomka izbrisana (``w:pPr/w:rPr/w:del``) ili premještena odande."""
    return any(p.find(put) is not None for put in _IZBRISANA_OZNAKA)


def okviri_odlomka(p) -> Iterator:
    """Odlomci (``w:p``) tekstnih okvira usidrenih u odlomku ``p``, redom, s ugniježđenima.

    Od ``mc:AlternateContent`` čita se samo prva grana (``Choice``, inače ``Fallback``),
    pa se okvir zapisan u obje inačice broji jednom. Okvir u izbrisanom sadržaju ne postoji.
    """
    # Brza provjera u lxml-u: većina odlomaka nema okvir.
    if next(p.iter(_TXBX), None) is None:
        return
    yield from _okviri(p)


def _okviri(element) -> Iterator:
    for dijete in element.iterchildren():
        oznaka = dijete.tag
        if not isinstance(oznaka, str) or oznaka in _PRESKOCI:
            continue
        if oznaka == f"{_MC}AlternateContent":
            grana = dijete.find(f"{_MC}Choice")
            if grana is None:
                grana = dijete.find(f"{_MC}Fallback")
            if grana is not None:
                yield from _okviri(grana)
        elif oznaka == _TXBX:
            yield from _odlomci_okvira(dijete)
        else:
            yield from _okviri(dijete)


def _odlomci_okvira(element) -> Iterator:
    for dijete in element.iterchildren():
        oznaka = dijete.tag
        if oznaka == qn("w:p"):
            yield dijete
            yield from okviri_odlomka(dijete)
        elif isinstance(oznaka, str) and oznaka not in _PRESKOCI:
            # Tablice, kontrole sadržaja i ostali spremnici unutar okvira.
            yield from _odlomci_okvira(dijete)

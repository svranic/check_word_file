"""Čitač .xlsx paketa bez openpyxla (AD-1): ćelije, formule, spremljene vrijednosti i svojstva.

Čita se samo ono što provjera treba. Dijeljene formule (``t="shared"``) se razvijaju
u formulu svake ćelije pomakom relativnih adresa, kao što to radi Excel.
Ulaz mora prije proći ``provjera.zajednicko.ulaz.provjeri_ulaz(..., EXCEL)``.
"""

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "op": "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
}
_NAJVECI_DIO = 20 * 1024 * 1024

_ADRESA = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")


class GreskaPaketa(Exception):
    """Paket nije čitljiva Excel radna knjiga."""


def stupac_u_broj(slova: str) -> int:
    broj = 0
    for z in slova:
        broj = broj * 26 + (ord(z) - 64)
    return broj


def broj_u_stupac(broj: int) -> str:
    slova = ""
    while broj:
        broj, ostatak = divmod(broj - 1, 26)
        slova = chr(65 + ostatak) + slova
    return slova


def rastavi_adresu(adresa: str) -> tuple[int, int]:
    """``"$B$12"`` → ``(12, 2)`` (redak, stupac)."""
    pogodak = _ADRESA.match(adresa.upper())
    if not pogodak:
        raise ValueError(f"neispravna adresa ćelije: {adresa!r}")
    return int(pogodak.group(2)), stupac_u_broj(pogodak.group(1))


def adresa(redak: int, stupac: int) -> str:
    return f"{broj_u_stupac(stupac)}{redak}"


Vrijednost = float | str | bool | None


@dataclass(frozen=True)
class Celija:
    """``formula`` je bez početnog ``=``; ``vrijednost`` je ono što je Excel zadnje spremio."""

    formula: str | None
    vrijednost: Vrijednost
    greska: str | None = None  # npr. "#DIV/0!" kao spremljena vrijednost


@dataclass(frozen=True)
class Svojstva:
    autor: str = ""
    zadnji_izmijenio: str = ""
    stvoreno: str = ""
    izmijenjeno: str = ""
    prilagodena: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RadnaKnjiga:
    listovi: dict[str, dict[str, Celija]]  # ime lista → adresa ("A1") → ćelija
    svojstva: Svojstva
    redoslijed: tuple[str, ...]

    def list(self, ime: str | None = None) -> dict[str, Celija]:
        if ime is None:
            return self.listovi[self.redoslijed[0]]
        return self.listovi[ime]


def _procitaj(arhiva: zipfile.ZipFile, ime: str) -> bytes | None:
    imena = {i.filename.lower(): i for i in arhiva.infolist()}
    stavka = imena.get(ime.lower())
    if stavka is None:
        return None
    if stavka.file_size > _NAJVECI_DIO:
        raise GreskaPaketa(f"dio {ime} je prevelik")
    return arhiva.read(stavka)


def _xml(arhiva: zipfile.ZipFile, ime: str) -> ET.Element | None:
    sadrzaj = _procitaj(arhiva, ime)
    if sadrzaj is None:
        return None
    try:
        return ET.fromstring(sadrzaj)
    except ET.ParseError as e:
        raise GreskaPaketa(f"neispravan XML u {ime}") from e


def _tekst_elementa(element: ET.Element) -> str:
    """Tekst ``<si>``/``<is>``: spojeni ``<t>`` bez fonetskih ``<rPh>`` dijelova."""
    tekstovi = element.findall("m:t", _NS) + element.findall("m:r/m:t", _NS)
    return "".join(t.text or "" for t in tekstovi)


def _putanje_listova(arhiva: zipfile.ZipFile) -> list[tuple[str, str]]:
    knjiga = _xml(arhiva, "xl/workbook.xml")
    veze = _xml(arhiva, "xl/_rels/workbook.xml.rels")
    if knjiga is None or veze is None:
        raise GreskaPaketa("nedostaje workbook.xml ili njegove veze")
    ciljevi = {v.get("Id"): v.get("Target", "") for v in veze.findall("rel:Relationship", _NS)}
    listovi = []
    for sheet in knjiga.findall("m:sheets/m:sheet", _NS):
        cilj = ciljevi.get(sheet.get(f"{{{_NS['r']}}}id"))
        if not cilj:
            continue
        putanja = cilj.lstrip("/") if cilj.startswith("/") else posixpath.normpath(posixpath.join("xl", cilj))
        listovi.append((sheet.get("name", ""), putanja))
    return listovi


# Referenca u formuli koju treba pomaknuti pri razvijanju dijeljene formule.
_REF_U_FORMULI = re.compile(
    r"(\"[^\"]*\")"  # tekstualni literal se ne dira
    r"|(?<![A-Za-z0-9_.])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])"
)


def pomakni_formulu(formula: str, d_redak: int, d_stupac: int) -> str:
    """Pomiče relativne adrese (bez ``$``) kao Excel pri kopiranju formule."""

    def zamjena(p: re.Match[str]) -> str:
        if p.group(1):
            return p.group(1)
        aps_st, slova, aps_r, broj = p.group(2), p.group(3), p.group(4), p.group(5)
        stupac = stupac_u_broj(slova) + (0 if aps_st else d_stupac)
        redak = int(broj) + (0 if aps_r else d_redak)
        if stupac < 1 or redak < 1:
            return "#REF!"
        return f"{aps_st}{broj_u_stupac(stupac)}{aps_r}{redak}"

    return _REF_U_FORMULI.sub(zamjena, formula)


def _citaj_list(korijen: ET.Element, dijeljeni: list[str]) -> dict[str, Celija]:
    celije: dict[str, Celija] = {}
    glavne: dict[str, tuple[str, str]] = {}  # si → (adresa glavne ćelije, formula)
    for c in korijen.iterfind("m:sheetData/m:row/m:c", _NS):
        adr = c.get("r")
        if not adr:
            continue
        tip = c.get("t", "n")
        f = c.find("m:f", _NS)
        v = c.find("m:v", _NS)
        formula = None
        if f is not None:
            if f.get("t") == "shared" and f.get("si") is not None:
                si = f.get("si", "")
                if f.text:
                    glavne[si] = (adr, f.text)
                    formula = f.text
                elif si in glavne:
                    izvor, tekst = glavne[si]
                    (r0, s0), (r1, s1) = rastavi_adresu(izvor), rastavi_adresu(adr)
                    formula = pomakni_formulu(tekst, r1 - r0, s1 - s0)
            else:
                formula = f.text or ""
        vrijednost: Vrijednost = None
        greska = None
        if tip == "inlineStr":
            unutra = c.find("m:is", _NS)
            vrijednost = _tekst_elementa(unutra) if unutra is not None else ""
        elif v is not None and v.text is not None:
            if tip == "s":
                try:
                    vrijednost = dijeljeni[int(v.text)]
                except (ValueError, IndexError):
                    vrijednost = None
            elif tip == "b":
                vrijednost = v.text == "1"
            elif tip == "e":
                greska = v.text
            elif tip == "str":
                vrijednost = v.text
            else:
                try:
                    vrijednost = float(v.text)
                except ValueError:
                    vrijednost = None
        if formula is None and vrijednost is None and greska is None:
            continue
        celije[adr.upper()] = Celija(formula=formula, vrijednost=vrijednost, greska=greska)
    return celije


def _svojstva(arhiva: zipfile.ZipFile) -> Svojstva:
    core = _xml(arhiva, "docProps/core.xml")
    custom = _xml(arhiva, "docProps/custom.xml")

    def tekst(putanja: str) -> str:
        if core is None:
            return ""
        el = core.find(putanja, _NS)
        return (el.text or "").strip() if el is not None else ""

    prilagodena: dict[str, str] = {}
    if custom is not None:
        for p in custom.findall("op:property", _NS):
            vrijednost = next(iter(p), None)
            prilagodena[p.get("name", "")] = (vrijednost.text or "") if vrijednost is not None else ""
    return Svojstva(
        autor=tekst("dc:creator"),
        zadnji_izmijenio=tekst("cp:lastModifiedBy"),
        stvoreno=tekst("dcterms:created"),
        izmijenjeno=tekst("dcterms:modified"),
        prilagodena=prilagodena,
    )


def ucitaj(sadrzaj: bytes) -> RadnaKnjiga:
    try:
        with zipfile.ZipFile(io.BytesIO(sadrzaj)) as arhiva:
            dijeljeni: list[str] = []
            sst = _xml(arhiva, "xl/sharedStrings.xml")
            if sst is not None:
                dijeljeni = [_tekst_elementa(si) for si in sst.findall("m:si", _NS)]
            listovi: dict[str, dict[str, Celija]] = {}
            for ime, putanja in _putanje_listova(arhiva):
                korijen = _xml(arhiva, putanja)
                if korijen is not None:
                    listovi[ime] = _citaj_list(korijen, dijeljeni)
            if not listovi:
                raise GreskaPaketa("radna knjiga nema listova")
            return RadnaKnjiga(listovi=listovi, svojstva=_svojstva(arhiva), redoslijed=tuple(listovi))
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        raise GreskaPaketa(str(e)) from e

"""Parsiranje .docx u DocModel i dodjela uloga (AD-3, AD-13).

Jedino mjesto u projektu koje dodiruje python-docx i lxml. Duljine su cijeli twipsi,
veličine fonta polutočke, prored 240-ine retka.
"""

import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

import docx
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.oxml.parser import parse_xml

from provjera.jezgra.model.numeracija import Brojaci, Numeracija
from provjera.jezgra.model.promjene import izbrisana_oznaka, okviri_odlomka, pracene_promjene
from provjera.jezgra.model.podnozja import (
    Podnozje,
    PodnozjaSekcije,
    PoljeStranice,
    VrstaPodnozja,
    je_istina,
    podnozja_sekcija,
)
from provjera.jezgra.model.stilovi import (
    Efektivno,
    Poravnanje,
    PraviloProreda,
    Prored,
    Run,
    Stil,
    Stilovi,
)
from provjera.jezgra.model.uloge import (
    NaziviUloga,
    Uloga,
    UlogaOdlomka,
    ZnacajkeOdlomka,
    uloga_okvira,
    uloge_odlomaka,
    uloge_sekcija,
)

__all__ = [
    "DocModel",
    "Efektivno",
    "NeispravanDokument",
    "NepodrzaniDokument",
    "Numeracija",
    "Odlomak",
    "OdlomakOkvira",
    "Podnozje",
    "PodnozjaSekcije",
    "PoljeStranice",
    "Poravnanje",
    "PraviloProreda",
    "Prored",
    "Run",
    "Sekcija",
    "Stil",
    "TipPocetka",
    "VrstaPodnozja",
    "procitaj",
]

_EMU_PO_TWIPU = 635


class NeispravanDokument(Exception):
    """python-docx ne može otvoriti dokument koji je prošao ulaznu provjeru."""


class NepodrzaniDokument(Exception):
    """Ispravan paket koji model ne podržava (npr. Strict OOXML); poruka je razlog."""


class TipPocetka(Enum):
    SLJEDECA_STRANICA = "SLJEDECA_STRANICA"
    NEPREKINUTO = "NEPREKINUTO"
    PARNA = "PARNA"
    NEPARNA = "NEPARNA"
    NOVI_STUPAC = "NOVI_STUPAC"


_POCETAK = {
    WD_SECTION_START.NEW_PAGE: TipPocetka.SLJEDECA_STRANICA,
    WD_SECTION_START.CONTINUOUS: TipPocetka.NEPREKINUTO,
    WD_SECTION_START.EVEN_PAGE: TipPocetka.PARNA,
    WD_SECTION_START.ODD_PAGE: TipPocetka.NEPARNA,
    WD_SECTION_START.NEW_COLUMN: TipPocetka.NOVI_STUPAC,
}


@dataclass(frozen=True)
class Sekcija:
    """Postavke stranice jedne sekcije; ``None`` znači da vrijednost nije zapisana."""

    indeks: int
    uloga: Uloga
    gore: int | None
    dolje: int | None
    lijevo: int | None
    desno: int | None
    gutter: int | None
    sirina: int | None
    visina: int | None
    pejzazno: bool
    pocetak: TipPocetka
    # w:titlePg: drukčija prva stranica (Different First Page).
    prva_stranica: bool = False
    # Podnožja po vrsti, s nasljeđivanjem od prethodne sekcije.
    podnozja: PodnozjaSekcije = PodnozjaSekcije()


@dataclass(frozen=True)
class Odlomak:
    """Odlomak tijela s efektivnim vrijednostima; ``indeks`` je globalni i 1-baziran."""

    indeks: int
    sekcija: int
    stil: Stil
    tekst: str
    isjecak: str | None
    uloga: UlogaOdlomka
    u_tablici: bool
    poravnanje: Efektivno[Poravnanje]
    razmak_ispred: Efektivno[int]
    razmak_iza: Efektivno[int]
    prored: Efektivno[Prored]
    uvlaka_lijevo: Efektivno[int]
    uvlaka_desno: Efektivno[int]
    uvlaka_prvi_red: Efektivno[int]
    # Vrijednost None znači da odlomak nije numeriran; izvor je izvor numId.
    numeracija: Efektivno[Numeracija | None]
    runovi: tuple[Run, ...] = ()


@dataclass(frozen=True)
class OdlomakOkvira:
    """Odlomak tekstnog okvira ili oblika (``w:txbxContent``) u sekciji tijela.

    Okviri nisu u ``DocModel.odlomci``: njihov sadržaj prijavljuje samo R-OKVIRI.
    """

    sekcija: int
    tekst: str
    isjecak: str | None
    kanonski_stil: str
    # Naslov (sažetka, poglavlja, literature), OSNOVNI_TEKST ili OSTALO (``uloge.uloga_okvira``).
    uloga: UlogaOdlomka


@dataclass(frozen=True)
class DocModel:
    sekcije: tuple[Sekcija, ...] = ()
    zrcalne_margine: bool = False
    odlomci: tuple[Odlomak, ...] = ()
    # w:evenAndOddHeaders u postavkama: drukčije parne i neparne stranice.
    parna_neparna: bool = False
    # Broj elemenata praćenih promjena (w:ins, w:del, w:moveFrom, w:moveTo, *PrChange …)
    # u tijelu, zaglavljima, podnožjima, fusnotama i endnotama. Sve ostalo u modelu je prihvaćeno stanje.
    pracene_promjene: int = 0
    # Odlomci tekstnih okvira i oblika u sekcijama tijela (naslovnica se ne provjerava).
    okviri: tuple[OdlomakOkvira, ...] = ()


def _twips(duljina: int | None) -> int | None:
    return None if duljina is None else round(duljina / _EMU_PO_TWIPU)


def _sekcija(indeks: int, uloga: Uloga, s, podnozja: PodnozjaSekcije = PodnozjaSekcije()) -> Sekcija:
    sirina, visina = _twips(s.page_width), _twips(s.page_height)
    # Word raspoređuje stranicu po dimenzijama; w:orient vrijedi samo kad dimenzije nedostaju.
    if sirina is not None and visina is not None:
        pejzazno = sirina > visina
    else:
        pejzazno = s.orientation == WD_ORIENTATION.LANDSCAPE
    return Sekcija(
        indeks=indeks,
        uloga=uloga,
        gore=_twips(s.top_margin),
        dolje=_twips(s.bottom_margin),
        lijevo=_twips(s.left_margin),
        desno=_twips(s.right_margin),
        gutter=_twips(s.gutter),
        sirina=sirina,
        visina=visina,
        pejzazno=pejzazno,
        pocetak=_POCETAK.get(s.start_type, TipPocetka.SLJEDECA_STRANICA),
        prva_stranica=je_istina(s._sectPr.find(qn("w:titlePg"))),
        podnozja=podnozja,
    )


def _zrcalne_margine(dokument) -> bool:
    element = dokument.settings.element.find(qn("w:mirrorMargins"))
    if element is None:
        return False
    return element.get(qn("w:val"), "true").lower() not in ("false", "0", "off")


def _parna_neparna(dokument) -> bool:
    # Ne preko dokument.settings: python-docx bi dokumentu bez postavki dodao dio paketa.
    dio = _dio(dokument, RT.SETTINGS)
    if dio is None:
        return False
    element = getattr(dio, "element", None)
    element = element if element is not None else parse_xml(dio.blob)
    return je_istina(element.find(qn("w:evenAndOddHeaders")))


# --- odlomci -------------------------------------------------------------------

_NAJVECI_ISJECAK = 60
_STRICT = b"purl.oclc.org/ooxml"
# Spremnici kroz koje se traže odlomci (tablice, kontrole sadržaja, customXml).
_SPREMNICI = {qn(t) for t in ("w:tbl", "w:tr", "w:tc", "w:customXml")}
# Sadržaj odlomka koji se ne čita: svojstva, izbrisani tekst i tekstni okviri.
_PRESKOCI_U_ODLOMKU = {qn(t) for t in ("w:pPr", "w:del", "w:moveFrom", "w:txbxContent", "w:sdtPr")}
_SLIKE = {
    qn("w:drawing"),
    qn("w:pict"),
    qn("w:object"),
    "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent",
}
_TEKST_RUNA = {
    qn("w:t"): None,
    qn("w:tab"): "\t",
    qn("w:br"): "\n",
    qn("w:cr"): "\n",
    qn("w:noBreakHyphen"): "-",
}


def _je_strict(sadrzaj: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(sadrzaj)) as arhiva:
            return _STRICT in arhiva.read("_rels/.rels")
    except MemoryError:
        raise
    except Exception:  # noqa: BLE001 — nečitljiv paket prosuđuje python-docx (OSTECENA)
        return False


def _je_sadrzaj(sdt) -> bool:
    galerija = sdt.find(f"{qn('w:sdtPr')}/{qn('w:docPartObj')}/{qn('w:docPartGallery')}")
    return galerija is not None and galerija.get(qn("w:val"), "").lower() == "table of contents"


def _odlomci_spremnika(spremnik, u_tablici: bool, u_sadrzaju: bool) -> Iterator[tuple]:
    """(w:p, u_tablici, u_sadrzaju) redom dokumenta."""
    for dijete in spremnik.iterchildren():
        oznaka = dijete.tag
        if oznaka == qn("w:p"):
            yield dijete, u_tablici, u_sadrzaju
        elif oznaka == qn("w:sdt"):
            sadrzaj = dijete.find(qn("w:sdtContent"))
            if sadrzaj is not None:
                yield from _odlomci_spremnika(sadrzaj, u_tablici, u_sadrzaju or _je_sadrzaj(dijete))
        elif oznaka in _SPREMNICI:
            yield from _odlomci_spremnika(dijete, u_tablici or oznaka == qn("w:tbl"), u_sadrzaju)


def _runovi(element) -> Iterator:
    for dijete in element.iterchildren():
        if dijete.tag == qn("w:r"):
            yield dijete
        elif isinstance(dijete.tag, str) and dijete.tag not in _PRESKOCI_U_ODLOMKU:
            yield from _runovi(dijete)


def _tekst_runa(r) -> tuple[str, bool]:
    dijelovi, slika = [], False
    for dijete in r.iterchildren():
        if dijete.tag in _TEKST_RUNA:
            zamjena = _TEKST_RUNA[dijete.tag]
            dijelovi.append((dijete.text or "") if zamjena is None else zamjena)
        elif dijete.tag in _SLIKE:
            slika = True
    return "".join(dijelovi), slika


def _val(element, oznaka: str) -> str | None:
    cilj = element.find(oznaka) if element is not None else None
    return cilj.get(qn("w:val")) if cilj is not None else None


@dataclass(frozen=True)
class _Sirovi:
    sekcija: int
    stil_id: str | None
    tekst: str
    u_tablici: bool
    u_sadrzaju: bool
    ima_sliku: bool
    svojstva: dict
    runovi: tuple[Run, ...]


def _odlomak(p, sekcija: int, u_tablici: bool, u_sadrzaju: bool, stilovi: Stilovi) -> _Sirovi:
    ppr = p.find(qn("w:pPr"))
    stil_id = stilovi.id_stila_odlomka(_val(ppr, qn("w:pStyle")))
    runovi, slika = [], False
    for r in _runovi(p):
        tekst, ima_sliku = _tekst_runa(r)
        slika = slika or ima_sliku
        if not tekst:
            continue
        rpr = r.find(qn("w:rPr"))
        svojstva = stilovi.rpr_runa(stil_id, _val(rpr, qn("w:rStyle")), rpr)
        runovi.append(Run(tekst, svojstva["font"], svojstva["velicina"], svojstva["podebljano"]))
    return _Sirovi(
        sekcija=sekcija,
        stil_id=stil_id,
        tekst="".join(r.tekst for r in runovi),
        u_tablici=u_tablici,
        u_sadrzaju=u_sadrzaju,
        ima_sliku=slika,
        svojstva=stilovi.ppr_odlomka(stil_id, ppr),
        runovi=tuple(runovi),
    )


def _dio(dokument, tip: str):
    try:
        return dokument.part.part_related_by(tip)
    except KeyError:
        return None


def _stilovi(dokument) -> Stilovi:
    # Ne preko dokument.styles: python-docx bi dokumentu bez stilova podmetnuo svoje.
    dio_stilova = _dio(dokument, RT.STYLES)
    dio_teme = _dio(dokument, RT.THEME)
    tema = parse_xml(dio_teme.blob) if dio_teme is not None else None
    return Stilovi(dio_stilova.element if dio_stilova is not None else None, tema)


def _brojaci(dokument) -> Brojaci:
    dio = _dio(dokument, RT.NUMBERING)
    if dio is None:
        return Brojaci(None)
    element = getattr(dio, "element", None)
    return Brojaci(element if element is not None else parse_xml(dio.blob))


def _numeracije(sirovi: list[_Sirovi], brojaci: Brojaci) -> list[Efektivno[Numeracija | None]]:
    """Brojači teku redom dokumenta preko svih odlomaka (i u tablicama i na naslovnici)."""
    return [
        Efektivno(
            brojaci.sljedeca(s.svojstva["num_id"].vrijednost, s.svojstva["ilvl"].vrijednost, s.stil_id),
            s.svojstva["num_id"].izvor,
        )
        for s in sirovi
    ]


def _ne_postoji(p, s: _Sirovi) -> bool:
    """Prihvaćeno stanje: odlomak s izbrisanom oznakom bez neizbrisanog teksta i slike ne postoji.

    Spajanje takvog odlomka sa sljedećim se ne modelira.
    """
    return not s.tekst.strip() and not s.ima_sliku and izbrisana_oznaka(p)


def _okviri(p, sekcija: int, stilovi: Stilovi, nazivi: NaziviUloga) -> Iterator[OdlomakOkvira]:
    for unutarnji in okviri_odlomka(p):
        s = _odlomak(unutarnji, sekcija, False, False, stilovi)
        if _ne_postoji(unutarnji, s):
            continue
        kanonski = stilovi.stil(s.stil_id).kanonski_id
        yield OdlomakOkvira(
            sekcija=sekcija,
            tekst=s.tekst,
            isjecak=s.tekst.strip()[:_NAJVECI_ISJECAK] or None,
            kanonski_stil=kanonski,
            uloga=uloga_okvira(kanonski, s.tekst, nazivi),
        )


def _odlomci(
    dokument, uloge_sek: tuple[Uloga, ...], nazivi: NaziviUloga, stilovi: Stilovi
) -> tuple[tuple[Odlomak, ...], tuple[OdlomakOkvira, ...]]:
    tijelo = dokument.element.body
    zadnja = max(len(uloge_sek), 1)
    sirovi, okviri, sekcija = [], [], 1
    for p, u_tablici, u_sadrzaju in _odlomci_spremnika(tijelo, False, False):
        trenutna = min(sekcija, zadnja)
        s = _odlomak(p, trenutna, u_tablici, u_sadrzaju, stilovi)
        if not _ne_postoji(p, s):
            sirovi.append(s)
        # Okviri na naslovnici se ne provjeravaju.
        if (uloge_sek[trenutna - 1] if uloge_sek else Uloga.TIJELO) is Uloga.TIJELO:
            okviri += _okviri(p, trenutna, stilovi, nazivi)
        # Sekciju završava odlomak tijela s w:sectPr (kao dokument.sections u python-docx).
        if p.getparent() is tijelo and p.find(f"{qn('w:pPr')}/{qn('w:sectPr')}") is not None:
            sekcija += 1
    znacajke = [
        ZnacajkeOdlomka(
            uloga_sekcije=uloge_sek[s.sekcija - 1] if uloge_sek else Uloga.TIJELO,
            kanonski_stil=stilovi.stil(s.stil_id).kanonski_id,
            tekst=s.tekst,
            u_tablici=s.u_tablici,
            u_sadrzaju=s.u_sadrzaju,
            ima_sliku=s.ima_sliku,
            numeriran=bool(s.svojstva["numeriran"].vrijednost),
        )
        for s in sirovi
    ]
    uloge = uloge_odlomaka(znacajke, nazivi)
    numeracije = _numeracije(sirovi, _brojaci(dokument))
    odlomci = tuple(
        Odlomak(
            indeks=i + 1,
            sekcija=s.sekcija,
            stil=stilovi.stil(s.stil_id),
            tekst=s.tekst,
            isjecak=s.tekst.strip()[:_NAJVECI_ISJECAK] or None,
            uloga=uloga,
            u_tablici=s.u_tablici,
            poravnanje=s.svojstva["poravnanje"],
            razmak_ispred=s.svojstva["razmak_ispred"],
            razmak_iza=s.svojstva["razmak_iza"],
            prored=s.svojstva["prored"],
            uvlaka_lijevo=s.svojstva["uvlaka_lijevo"],
            uvlaka_desno=s.svojstva["uvlaka_desno"],
            uvlaka_prvi_red=s.svojstva["uvlaka_prvi_red"],
            numeracija=numeracija,
            runovi=s.runovi,
        )
        for i, (s, uloga, numeracija) in enumerate(zip(sirovi, uloge, numeracije))
    )
    return odlomci, tuple(okviri)


def procitaj(sadrzaj: bytes, nazivi: NaziviUloga) -> DocModel:
    """Parsira dokument točno jednom; ``sadrzaj`` je već prošao ``ulaz.provjeri_ulaz``.

    ``nazivi`` su nazivi uloga iz odjeljka ``[uloge]`` profila.
    """
    if _je_strict(sadrzaj):
        raise NepodrzaniDokument("Strict OOXML")
    # Samo neuspjelo otvaranje paketa znači oštećen dokument; greške pri čitanju
    # pojedinih postavki idu pozivatelju, koji pogođena pravila čini neprovjerljivima.
    try:
        dokument = docx.Document(io.BytesIO(sadrzaj))
    except MemoryError:
        raise
    except Exception as greska:  # noqa: BLE001 — python-docx baca razne tipove za nečitljiv paket
        raise NeispravanDokument(type(greska).__name__) from greska
    sekcije = list(dokument.sections)
    uloge = uloge_sekcija(len(sekcije))
    stilovi = _stilovi(dokument)
    podnozja = podnozja_sekcija(dokument.part, [s._sectPr for s in sekcije], stilovi)
    odlomci, okviri = _odlomci(dokument, uloge, nazivi, stilovi)
    return DocModel(
        sekcije=tuple(
            _sekcija(i + 1, uloga, s, p) for i, (uloga, s, p) in enumerate(zip(uloge, sekcije, podnozja))
        ),
        zrcalne_margine=_zrcalne_margine(dokument),
        odlomci=odlomci,
        parna_neparna=_parna_neparna(dokument),
        pracene_promjene=pracene_promjene(dokument),
        okviri=okviri,
    )

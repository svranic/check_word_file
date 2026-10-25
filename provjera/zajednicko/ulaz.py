"""Sigurni ulaz (FR-10, AD-12): provjera bajtova prije bilo kakvog parsiranja dokumenta."""

import io
import lzma
import zipfile
import zlib
from dataclasses import dataclass
from enum import StrEnum

NAJVECA_VELICINA_MB = 10
NAJVECA_RASPAKIRANA_MB = 100
NAJVECA_VELICINA = NAJVECA_VELICINA_MB * 1024 * 1024
NAJVECA_RASPAKIRANA = NAJVECA_RASPAKIRANA_MB * 1024 * 1024
_NAJVECI_CONTENT_TYPES = 1024 * 1024
_NAJVISE_STAVKI = 10_000

_ZIP_POTPIS = b"PK\x03\x04"
_OLE_POTPIS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# Šifrirani OOXML je OLE spremnik s tokom „EncryptionInfo“ (ime u UTF-16LE).
_OLE_SIFRIRANO = "EncryptionInfo".encode("utf-16-le")


class RazlogOdbijanja(StrEnum):
    PRAZNA = "prazna"
    NEISPRAVAN_FORMAT = "neispravan_format"
    STARI_DOC = "stari_doc"
    MAKRO = "makro"
    SIFRIRANA = "sifrirana"
    PREVELIKA = "prevelika"
    ZIP_BOMBA = "zip_bomba"
    OSTECENA = "ostecena"


@dataclass(frozen=True)
class FormatPaketa:
    """OOXML paket koji se prihvaća: nastavci i dijelovi paketa (imena malim slovima)."""

    nastavak: str
    stari_nastavak: str
    makro_nastavak: str
    glavni_dio: str
    makro_dio: str


WORD = FormatPaketa(".docx", ".doc", ".docm", "word/document.xml", "word/vbaproject.bin")
EXCEL = FormatPaketa(".xlsx", ".xls", ".xlsm", "xl/workbook.xml", "xl/vbaproject.bin")


def _razlog_nastavka(naziv: str, fmt: FormatPaketa) -> RazlogOdbijanja | None:
    malim = naziv.lower()
    if malim.endswith(fmt.nastavak):
        return None
    if malim.endswith(fmt.stari_nastavak):
        return RazlogOdbijanja.STARI_DOC
    if malim.endswith(fmt.makro_nastavak):
        return RazlogOdbijanja.MAKRO
    return RazlogOdbijanja.NEISPRAVAN_FORMAT


def _razlog_zipa(sadrzaj: bytes, fmt: FormatPaketa) -> RazlogOdbijanja | None:
    try:
        with zipfile.ZipFile(io.BytesIO(sadrzaj)) as arhiva:
            stavke = arhiva.infolist()
            # Deklarirane veličine; parser modela mora i sam ograničiti stvarno čitanje.
            if len(stavke) > _NAJVISE_STAVKI or sum(s.file_size for s in stavke) > NAJVECA_RASPAKIRANA:
                return RazlogOdbijanja.ZIP_BOMBA
            # Imena dijelova paketa (OPC) ne ovise o velikim i malim slovima.
            imena = {s.filename.lower(): s for s in stavke}
            content_types = imena.get("[content_types].xml")
            if content_types is None or fmt.glavni_dio not in imena:
                return RazlogOdbijanja.OSTECENA
            if content_types.file_size > _NAJVECI_CONTENT_TYPES:
                return RazlogOdbijanja.OSTECENA
            tipovi = arhiva.read(content_types).lower()
            if fmt.makro_dio in imena or b"macroenabled" in tipovi or b"vbaproject" in tipovi:
                return RazlogOdbijanja.MAKRO
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
        RuntimeError,  # šifrirana stavka ZIP-a
        NotImplementedError,
        ValueError,
        OSError,
        EOFError,
        lzma.LZMAError,  # oštećena stavka komprimirana LZMA-om
    ):
        return RazlogOdbijanja.OSTECENA
    return None


def provjeri_ulaz(
    naziv: str, sadrzaj: bytes, fmt: FormatPaketa = WORD
) -> RazlogOdbijanja | None:
    """Vraća razlog odbijanja ili ``None`` ako je datoteka prihvatljiv paket formata ``fmt``.

    ``STARI_DOC`` znači i stari .xls kad se provjerava Excel.
    """
    if not sadrzaj:
        return RazlogOdbijanja.PRAZNA
    razlog = _razlog_nastavka(naziv, fmt)
    if razlog:
        return razlog
    if len(sadrzaj) > NAJVECA_VELICINA:
        return RazlogOdbijanja.PREVELIKA
    if sadrzaj.startswith(_OLE_POTPIS):
        if _OLE_SIFRIRANO in sadrzaj:
            return RazlogOdbijanja.SIFRIRANA
        return RazlogOdbijanja.STARI_DOC
    if not sadrzaj.startswith(_ZIP_POTPIS):
        return RazlogOdbijanja.NEISPRAVAN_FORMAT
    return _razlog_zipa(sadrzaj, fmt)

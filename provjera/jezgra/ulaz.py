"""Sigurni ulaz (FR-10, AD-12): provjera bajtova prije bilo kakvog parsiranja dokumenta."""

import io
import zipfile
import zlib
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


def _razlog_nastavka(naziv: str) -> RazlogOdbijanja | None:
    malim = naziv.lower()
    if malim.endswith(".docx"):
        return None
    if malim.endswith(".doc"):
        return RazlogOdbijanja.STARI_DOC
    if malim.endswith(".docm"):
        return RazlogOdbijanja.MAKRO
    return RazlogOdbijanja.NEISPRAVAN_FORMAT


def _razlog_zipa(sadrzaj: bytes) -> RazlogOdbijanja | None:
    try:
        with zipfile.ZipFile(io.BytesIO(sadrzaj)) as arhiva:
            stavke = arhiva.infolist()
            # Deklarirane veličine; parser modela mora i sam ograničiti stvarno čitanje.
            if len(stavke) > _NAJVISE_STAVKI or sum(s.file_size for s in stavke) > NAJVECA_RASPAKIRANA:
                return RazlogOdbijanja.ZIP_BOMBA
            imena = {s.filename: s for s in stavke}
            content_types = imena.get("[Content_Types].xml")
            if content_types is None or "word/document.xml" not in imena:
                return RazlogOdbijanja.OSTECENA
            if content_types.file_size > _NAJVECI_CONTENT_TYPES:
                return RazlogOdbijanja.OSTECENA
            if "word/vbaProject.bin" in imena or b"macroEnabled" in arhiva.read(content_types):
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
    ):
        return RazlogOdbijanja.OSTECENA
    return None


def provjeri_ulaz(naziv: str, sadrzaj: bytes) -> RazlogOdbijanja | None:
    """Vraća razlog odbijanja ili ``None`` ako je datoteka prihvatljiv .docx."""
    if not sadrzaj:
        return RazlogOdbijanja.PRAZNA
    razlog = _razlog_nastavka(naziv)
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
    return _razlog_zipa(sadrzaj)

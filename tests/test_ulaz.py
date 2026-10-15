import io
import zipfile

import docx
import pytest

from provjera.jezgra import ulaz
from provjera.jezgra.poruke import KATALOG
from provjera.jezgra.ulaz import RazlogOdbijanja as R

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def valjani_docx() -> bytes:
    spremnik = io.BytesIO()
    docx.Document().save(spremnik)
    return spremnik.getvalue()


def zip_s(datoteke: dict[str, bytes]) -> bytes:
    spremnik = io.BytesIO()
    with zipfile.ZipFile(spremnik, "w", zipfile.ZIP_DEFLATED) as arhiva:
        for ime, sadrzaj in datoteke.items():
            arhiva.writestr(ime, sadrzaj)
    return spremnik.getvalue()


@pytest.mark.parametrize("naziv", ["Rad.docx", "RAD.DOCX", "Lucija_Šimek_GiG_OG_Vjezba_1.Docx"])
def test_valjani_docx_prolazi(naziv):
    assert ulaz.provjeri_ulaz(naziv, valjani_docx()) is None


@pytest.mark.parametrize(
    ("naziv", "sadrzaj", "razlog"),
    [
        ("rad.docx", b"", R.PRAZNA),
        ("rad.doc", OLE + b"\0" * 100, R.STARI_DOC),
        ("rad.docx", OLE + b"\0" * 100, R.STARI_DOC),
        ("rad.docx", OLE + "EncryptionInfo".encode("utf-16-le"), R.SIFRIRANA),
        ("rad.docm", b"PK\x03\x04", R.MAKRO),
        ("rad.pdf", b"%PDF-1.7", R.NEISPRAVAN_FORMAT),
        ("rad.txt", b"tekst", R.NEISPRAVAN_FORMAT),
        ("rad", b"PK\x03\x04", R.NEISPRAVAN_FORMAT),
        ("rad.docx", b"%PDF-1.7 preimenovan", R.NEISPRAVAN_FORMAT),
        ("rad.docx", b"PK\x03\x04skraceno", R.OSTECENA),
    ],
)
def test_odbijanje(naziv, sadrzaj, razlog):
    assert ulaz.provjeri_ulaz(naziv, sadrzaj) is razlog


def test_valjani_docx_skracen_je_ostecen():
    sadrzaj = valjani_docx()
    assert ulaz.provjeri_ulaz("rad.docx", sadrzaj[: len(sadrzaj) // 2]) is R.OSTECENA


def test_zip_bez_dokumenta_je_ostecen():
    assert ulaz.provjeri_ulaz("rad.docx", zip_s({"[Content_Types].xml": b"<Types/>"})) is R.OSTECENA


def test_makro_docx_preimenovan():
    sadrzaj = zip_s(
        {
            "[Content_Types].xml": b'<Types><Override ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/></Types>',
            "word/document.xml": b"<w:document/>",
        }
    )
    assert ulaz.provjeri_ulaz("rad.docx", sadrzaj) is R.MAKRO


def test_prevelika():
    sadrzaj = b"PK\x03\x04" + b"\0" * ulaz.NAJVECA_VELICINA
    assert ulaz.provjeri_ulaz("rad.docx", sadrzaj) is R.PREVELIKA


def test_zip_bomba():
    sadrzaj = zip_s(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"<w:document/>",
            "word/media/bomba.bin": b"\0" * (ulaz.NAJVECA_RASPAKIRANA + 1),
        }
    )
    assert len(sadrzaj) < ulaz.NAJVECA_VELICINA
    assert ulaz.provjeri_ulaz("rad.docx", sadrzaj) is R.ZIP_BOMBA


def test_svaki_razlog_ima_poruku():
    for razlog in R:
        assert f"ulaz.{razlog}" in KATALOG


def _osnovni(content_types: bytes = b"<Types/>") -> dict[str, bytes]:
    return {"[Content_Types].xml": content_types, "word/document.xml": b"<w:document/>"}


def test_osteceni_deflate_u_content_types():
    sadrzaj = bytearray(zip_s(_osnovni(b"<Types>" + b"x" * 5000 + b"</Types>")))
    pocetak = sadrzaj.index(b"[Content_Types].xml") + len("[Content_Types].xml")
    for i in range(pocetak, pocetak + 10):
        sadrzaj[i] ^= 0xFF
    assert ulaz.provjeri_ulaz("rad.docx", bytes(sadrzaj)) is R.OSTECENA


def test_sifrirana_stavka_zipa():
    sadrzaj = bytearray(zip_s(_osnovni()))
    for potpis, pomak in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = sadrzaj.index(potpis)  # prva stavka je [Content_Types].xml
        sadrzaj[i + pomak] |= 0x01
    assert ulaz.provjeri_ulaz("rad.docx", bytes(sadrzaj)) is R.OSTECENA


def test_bez_content_types_je_ostecen():
    assert ulaz.provjeri_ulaz("rad.docx", zip_s({"word/document.xml": b"<w:document/>"})) is R.OSTECENA


def test_prevelik_content_types_je_ostecen():
    velik = b"<Types>" + b" " * (1024 * 1024) + b"</Types>"
    assert ulaz.provjeri_ulaz("rad.docx", zip_s(_osnovni(velik))) is R.OSTECENA


def test_vba_projekt_je_makro():
    datoteke = _osnovni() | {"word/vbaProject.bin": b"\0"}
    assert ulaz.provjeri_ulaz("rad.docx", zip_s(datoteke)) is R.MAKRO


def test_previse_stavki_je_zip_bomba():
    datoteke = _osnovni() | {f"word/media/{i}.bin": b"" for i in range(10_001)}
    assert ulaz.provjeri_ulaz("rad.docx", zip_s(datoteke)) is R.ZIP_BOMBA


@pytest.mark.parametrize(("naziv", "razlog"), [("RAD.DOC", R.STARI_DOC), ("Rad.DOCM", R.MAKRO), ("rad.docx.pdf", R.NEISPRAVAN_FORMAT)])
def test_nastavak_velikim_slovima_i_dvostruki(naziv, razlog):
    assert ulaz.provjeri_ulaz(naziv, valjani_docx()) is razlog


def test_granica_velicine_je_ukljucena():
    sadrzaj = b"PK\x03\x04" + b"\0" * (ulaz.NAJVECA_VELICINA - 4)
    assert ulaz.provjeri_ulaz("rad.docx", sadrzaj) is not R.PREVELIKA


def test_ostecen_lzma_zip_je_ostecen():
    import lzma  # noqa: F401 — ZIP_LZMA treba modul lzma

    spremnik = io.BytesIO()
    with zipfile.ZipFile(spremnik, "w", zipfile.ZIP_LZMA) as arhiva:
        arhiva.writestr("[Content_Types].xml", "<Types>" + "x" * 5000 + "</Types>")
        arhiva.writestr("word/document.xml", "<w/>")
    podaci = bytearray(spremnik.getvalue())
    pocetak = podaci.find(b"[Content_Types].xml") + len("[Content_Types].xml") + 20
    for i in range(pocetak, pocetak + 40):
        podaci[i] ^= 0xFF
    assert ulaz.provjeri_ulaz("rad.docx", bytes(podaci)) is R.OSTECENA


@pytest.mark.parametrize(
    "datoteke",
    [
        {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w/>", "Word/VBAProject.bin": b"x"},
        {
            "[content_types].xml": b'<Types><Override ContentType="application/vnd.ms-word.document.MACROENABLED.main+xml"/></Types>',
            "word/document.xml": b"<w/>",
        },
        {
            "[Content_Types].xml": b'<Types><Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>',
            "word/document.xml": b"<w/>",
            "word/makro.bin": b"x",
        },
    ],
)
def test_makro_bez_obzira_na_slova_i_putanju(datoteke):
    assert ulaz.provjeri_ulaz("rad.docx", zip_s(datoteke)) is R.MAKRO

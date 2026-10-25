import io
import zipfile

import pytest

from provjera.excel.jezgra import xlsx

_GLAVA = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
)


def paket(list_xml: str, dijeljeni: list[str] = ()) -> bytes:
    spremnik = io.BytesIO()
    with zipfile.ZipFile(spremnik, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="List1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet1.xml", _GLAVA + list_xml + "</sheetData></worksheet>")
        if dijeljeni:
            z.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + "".join(f"<si><t>{t}</t></si>" for t in dijeljeni) + "</sst>",
            )
    return spremnik.getvalue()


def test_vrijednosti_formule_i_tekst():
    knjiga = xlsx.ucitaj(paket(
        '<row r="1"><c r="A1"><v>1.5</v></c><c r="B1" t="s"><v>0</v></c>'
        '<c r="C1"><f>A1*2</f><v>3</v></c><c r="D1" t="e"><f>1/0</f><v>#DIV/0!</v></c>'
        '<c r="E1" t="inlineStr"><is><t>α</t></is></c></row>',
        ["oznaka"],
    ))
    celije = knjiga.list()
    assert celije["A1"] == xlsx.Celija(None, 1.5)
    assert celije["B1"].vrijednost == "oznaka"
    assert celije["C1"] == xlsx.Celija("A1*2", 3.0)
    assert celije["D1"].greska == "#DIV/0!"
    assert celije["E1"].vrijednost == "α"


def test_dijeljena_formula_se_razvija():
    knjiga = xlsx.ucitaj(paket(
        '<row r="1"><c r="B1"><f t="shared" ref="B1:B3" si="0">A1*$C$1+A$1</f><v>1</v></c></row>'
        '<row r="2"><c r="B2"><f t="shared" si="0"/><v>2</v></c></row>'
        '<row r="3"><c r="C3"><f t="shared" si="0"/><v>3</v></c></row>'
    ))
    celije = knjiga.list()
    assert celije["B2"].formula == "A2*$C$1+A$1"
    assert celije["C3"].formula == "B3*$C$1+B$1"


@pytest.mark.parametrize(
    ("formula", "pomak", "ocekivano"),
    [
        ('A1&"B2"', (1, 1), 'B2&"B2"'),  # tekst se ne dira
        ("SUM(A1:A3)", (2, 0), "SUM(A3:A5)"),
        ("LOG10(A1)", (1, 0), "LOG10(A2)"),  # ime funkcije nije adresa
        ("A1", (-1, 0), "#REF!"),
    ],
)
def test_pomakni_formulu(formula, pomak, ocekivano):
    assert xlsx.pomakni_formulu(formula, *pomak) == ocekivano


def test_adrese():
    assert xlsx.rastavi_adresu("$AB$12") == (12, 28)
    assert xlsx.adresa(12, 28) == "AB12"


def test_neispravan_paket():
    with pytest.raises(xlsx.GreskaPaketa):
        xlsx.ucitaj(b"nije zip")

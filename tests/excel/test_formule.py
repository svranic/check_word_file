import math

import pytest

from provjera.excel.jezgra import formule
from provjera.excel.jezgra.formule import ExcelGreska, Nepodrzano, Racunalo
from provjera.excel.jezgra.xlsx import Celija


def izracunaj(formula: str, celije: dict[str, object] | None = None):
    listovi = {"L": {a: Celija(None, v) for a, v in (celije or {}).items()}}
    listovi["L"]["Z1"] = Celija(formula.lstrip("="), None)
    return Racunalo(listovi, "L").celija("Z1")


@pytest.mark.parametrize(
    ("formula", "ocekivano"),
    [
        ("=1+2*3", 7.0),
        ("=(1+2)*3", 9.0),
        ("=-2^2", 4.0),  # unarni minus veže jače od ^, kao u Excelu
        ("=2^3^2", 64.0),  # ^ je lijevo asocijativan
        ("=10-2-3", 5.0),
        ("=50%", 0.5),
        ("=MOD(-7,3)", 2.0),  # predznak djelitelja
        ("=MOD(7,-3)", -2.0),
        ("=INT(-2.5)", -3.0),
        ("=TRUNC(-2.5)", -2.0),
        ("=ROUND(2.5,0)", 3.0),
        ("=ROUND(-2.5,0)", -3.0),
        ("=ROUND(1.005,2)", 1.01),
        ("=ROUNDDOWN(1.239,2)", 1.23),
        ("=QUOTIENT(-7,2)", -3.0),
        ("=DEGREES(PI())", 180.0),
        ("=SUM(1,2,3)", 6.0),
        ("=_xlfn.UNICHAR(931)", "Σ"),
        ('="a"&"b"&1', "ab1"),
        ("=IF(1>2,\"da\",\"ne\")", "ne"),
        ("=1=1", True),
        ("=SQRT(16)", 4.0),
        ("=POWER(2,10)", 1024.0),
    ],
)
def test_izracun(formula, ocekivano):
    dobiveno = izracunaj(formula)
    if isinstance(ocekivano, float):
        assert dobiveno == pytest.approx(ocekivano)
    else:
        assert dobiveno == ocekivano


def test_atan2_ima_excelov_redoslijed_argumenata():
    # Excel: ATAN2(x; y) = kut točke (x, y)
    assert izracunaj("=ATAN2(0,1)") == pytest.approx(math.pi / 2)


def test_reference_rasponi_i_dolar():
    celije = {"A1": 1.0, "A2": 2.0, "A3": "tekst", "B1": 10.0}
    assert izracunaj("=SUM(A1:A3)+$B$1", celije) == 13.0
    assert izracunaj("=A1+A3", {"A1": 1.0, "A3": "2,5"}) == 3.5
    assert izracunaj("=A9+1", celije) == 1.0  # prazna ćelija je 0


def test_lanac_formula_i_zamjene():
    listovi = {"L": {"A1": Celija(None, 30.0), "B1": Celija("SIN(RADIANS(A1))", None), "C1": Celija("B1*2", None)}}
    assert Racunalo(listovi, "L").celija("C1") == pytest.approx(1.0)
    assert Racunalo(listovi, "L", {("L", "A1"): 90.0}).celija("C1") == pytest.approx(2.0)


def test_referenca_na_drugi_list():
    listovi = {"Prvi": {"A1": Celija(None, 4.0)}, "Drugi list": {"A1": Celija("'Prvi'!A1*2", None)}}
    assert Racunalo(listovi, "Drugi list").celija("A1") == 8.0


@pytest.mark.parametrize(("formula", "kod"), [("=1/0", "#DIV/0!"), ("=SQRT(-1)", "#NUM!"),
                                              ("=ACOS(2)", "#NUM!"), ('="a"+1', "#VALUE!")])
def test_excelove_greske(formula, kod):
    with pytest.raises(ExcelGreska) as e:
        izracunaj(formula)
    assert e.value.kod == kod


def test_kruzna_referenca():
    listovi = {"L": {"A1": Celija("B1", None), "B1": Celija("A1", None)}}
    with pytest.raises(ExcelGreska):
        Racunalo(listovi, "L").celija("A1")


@pytest.mark.parametrize("formula", ["=VLOOKUP(1,A1:B2,2)", "=imenovano*2", "=1+"])
def test_nepodrzano(formula):
    with pytest.raises(Nepodrzano):
        izracunaj(formula)


def test_brojevi_i_reference_iz_stabla():
    stablo = formule.parsiraj("=175.23/SIN(RADIANS(N8))+$A$1+SUM(B1:B3)")
    assert formule.brojevi(stablo) == [175.23]
    assert {f for f in formule.funkcije(stablo)} == {"SIN", "RADIANS", "SUM"}
    assert len(formule.reference(stablo)) == 3


def test_ime_funkcije_nije_adresa():
    # LOG10( i ATAN2( izgledaju kao adrese ćelija (LOG10, ATAN2), ali su funkcije.
    assert izracunaj("=LOG10(100)+ATAN2(1,0)") == pytest.approx(2.0)

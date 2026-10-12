import pytest

from provjera.jezgra import jedinice
from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.poruke import formatiraj


@pytest.mark.parametrize(
    ("tekst", "twips"),
    [("3 cm", 1701), ("2,5 cm", 1417), ("2.5cm", 1417), ("25 mm", 1417), ("12 pt", 240), ("0,03 cm", 17)],
)
def test_parsiraj_duljinu(tekst, twips):
    assert jedinice.parsiraj_duljinu(tekst) == twips


@pytest.mark.parametrize("tekst", ["3 inch", "-1 cm", "3", "", 3])
def test_parsiraj_duljinu_odbija(tekst):
    with pytest.raises(ValueError):
        jedinice.parsiraj_duljinu(tekst)


@pytest.mark.parametrize(("tekst", "mm"), [("3 cm", 30), ("0,1 cm", 1), ("25 mm", 25)])
def test_parsiraj_mm(tekst, mm):
    assert jedinice.parsiraj_mm(tekst) == mm


@pytest.mark.parametrize("tekst", ["0,15 cm", "12 pt", "3 inch", "3", "-1 cm", "", "cm"])
def test_parsiraj_mm_odbija(tekst):
    with pytest.raises(ValueError):
        jedinice.parsiraj_mm(tekst)


def test_parsiraj_velicinu_fonta():
    assert jedinice.parsiraj_velicinu_fonta("12 pt") == 24
    assert jedinice.parsiraj_velicinu_fonta("10,5 pt") == 21
    for neispravno in ("12 cm", "10,25 pt"):
        with pytest.raises(ValueError):
            jedinice.parsiraj_velicinu_fonta(neispravno)


def test_mm_u_twips_i_tolerancija():
    assert jedinice.mm_u_twips(32) == 1814
    assert jedinice.unutar_tolerancije(1814, 1831, 17)
    assert not jedinice.unutar_tolerancije(1814, 1832, 17)


@pytest.mark.parametrize(
    ("iznos", "jedinica", "tekst"),
    [
        (1814, Jedinica.TWIPS, "3,2 cm"),
        (1417, Jedinica.TWIPS, "2,5 cm"),
        (1701, Jedinica.TWIPS, "3 cm"),
        (1797, Jedinica.TWIPS, "3,17 cm"),
        (24, Jedinica.POLUTOCKE, "12 pt"),
        (21, Jedinica.POLUTOCKE, "10,5 pt"),
        (True, Jedinica.BOOL, "da"),
        (False, Jedinica.BOOL, "ne"),
        ("Normal", Jedinica.TEKST, "Normal"),
    ],
)
def test_formatiraj(iznos, jedinica, tekst):
    assert formatiraj(iznos, jedinica) == tekst

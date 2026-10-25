import pytest

from provjera.word.jezgra import rbr
from provjera.word.jezgra.poruke import KATALOG


@pytest.mark.parametrize("unos", ["54", "54.", " 054", "054 ", "\t54.\n"])
def test_ispravan_unos(unos):
    assert rbr.parsiraj(unos) == 54


@pytest.mark.parametrize(
    ("unos", "greska"),
    [
        ("", rbr.PRAZNO),
        ("   ", rbr.PRAZNO),
        ("0", rbr.NEISPRAVNO),
        ("-3", rbr.NEISPRAVNO),
        ("5,5", rbr.NEISPRAVNO),
        ("5.5", rbr.NEISPRAVNO),
        ("abc", rbr.NEISPRAVNO),
        ("54..", rbr.NEISPRAVNO),
        ("+5", rbr.NEISPRAVNO),
        ("1" * 10, rbr.NEISPRAVNO),
        ("9" * 5000, rbr.NEISPRAVNO),
    ],
)
def test_neispravan_unos(unos, greska):
    assert rbr.parsiraj(unos) == greska


def test_kljucevi_gresaka_postoje_u_katalogu():
    for greska in (rbr.PRAZNO, rbr.NEISPRAVNO):
        assert greska.poruka_kljuc in KATALOG

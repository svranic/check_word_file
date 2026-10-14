"""Pregled spremnosti vježbe (priča 3.3): čista funkcija jezgre."""

from pathlib import Path

import pytest

from provjera.jezgra import formula, profil, spremnost
from provjera.jezgra.poruke import KATALOG, poruka
from provjera.jezgra.spremnost import Problem

KORIJEN = Path(__file__).resolve().parents[1]
VJEZBA_1 = KORIJEN / "profili" / "vjezba_1.toml"


@pytest.fixture(scope="module")
def vjezba():
    return profil.ucitaj(VJEZBA_1.read_bytes())


def _bez_pravila(p: profil.Profil) -> profil.Profil:
    pravila = {
        pid: postavke.model_copy(update={"ukljuceno": False})
        for pid, postavke in p.pravila.items()
    }
    return p.model_copy(update={"pravila": pravila})


def test_spremno(vjezba):
    rezultat = spremnost.pregled(vjezba, list(range(1, 79)), 78)
    assert rezultat.spremno
    assert rezultat.problemi == ()
    assert rezultat.naziv == "Vježba 1"
    assert rezultat.verzija == profil.verzija(vjezba)
    assert rezultat.broj_aktivnih == 78
    assert rezultat.broj_ukljucenih_pravila == sum(p.ukljuceno for p in vjezba.pravila.values())
    assert rezultat.broj_ukljucenih_pravila > 0
    assert rezultat.margine_jedinstvene is True


def test_bez_popisa(vjezba):
    rezultat = spremnost.pregled(vjezba, None, 0)
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.nema_popisa"),)
    assert rezultat.margine_jedinstvene is None


def test_prevelik_rbr(vjezba):
    najveci = formula.najveci_rbr(vjezba.formula)
    rezultat = spremnost.pregled(vjezba, [1, 2, najveci + 1], 3)
    assert not rezultat.spremno
    assert rezultat.problemi == (
        Problem(
            "spremnost.rbr_izvan_raspona", {"rbrovi": str(najveci + 1), "najveci": najveci}
        ),
    )
    # Rbr. izvan raspona preskače se u provjeri jedinstvenosti (ne baca ValueError).
    assert rezultat.margine_jedinstvene is True
    tekst = poruka(rezultat.problemi[0].kljuc, **rezultat.problemi[0].parametri)
    assert str(najveci + 1) in tekst and str(najveci) in tekst


def test_formula_podrzava_barem_500(vjezba):
    assert spremnost.pregled(vjezba, list(range(1, 501)), 500).spremno


def test_bez_aktivnih(vjezba):
    rezultat = spremnost.pregled(vjezba, [1, 2, 3], 0)
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.nema_aktivnih"),)


def test_sva_pravila_iskljucena(vjezba):
    rezultat = spremnost.pregled(_bez_pravila(vjezba), [1, 2], 2)
    assert not rezultat.spremno
    assert rezultat.broj_ukljucenih_pravila == 0
    assert rezultat.problemi == (Problem("spremnost.nema_pravila"),)


def test_iste_margine_navode_oba_rbr(vjezba, monkeypatch):
    # Formula po konstrukciji daje različite margine; provjera ostaje obrambena.
    prava = formula.margine

    def margine(rbr, parametri):
        return prava(1 if rbr == 3 else rbr, parametri)

    monkeypatch.setattr(formula, "margine", margine)
    rezultat = spremnost.pregled(vjezba, [1, 2, 3], 3)
    assert rezultat.margine_jedinstvene is False
    assert rezultat.problemi == (Problem("spremnost.iste_margine", {"prvi": 1, "drugi": 3}),)


def test_vise_problema_odjednom(vjezba):
    najveci = formula.najveci_rbr(vjezba.formula)
    rezultat = spremnost.pregled(_bez_pravila(vjezba), [najveci + 2, najveci + 1], 0)
    assert [p.kljuc for p in rezultat.problemi] == [
        "spremnost.nema_aktivnih",
        "spremnost.rbr_izvan_raspona",
        "spremnost.nema_pravila",
    ]
    assert rezultat.problemi[1].parametri["rbrovi"] == f"{najveci + 1}, {najveci + 2}"


def test_svi_kljucevi_problema_u_katalogu():
    for kljuc in (
        "spremnost.nema_popisa",
        "spremnost.nema_aktivnih",
        "spremnost.rbr_izvan_raspona",
        "spremnost.iste_margine",
        "spremnost.nema_pravila",
    ):
        assert kljuc in KATALOG


def test_dupli_rbr_se_prijavljuje(vjezba):
    rezultat = spremnost.pregled(vjezba, [1, 2, 2, 3, 3, 3], 6)
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.dupli_rbr", {"rbrovi": "2, 3"}),)
    assert "dupli_rbr" in rezultat.problemi[0].kljuc
    assert "spremnost.dupli_rbr" in KATALOG


def test_problem_je_nepromjenjiv_i_hashabilan():
    izvorni = {"rbrovi": "1"}
    problem = Problem("spremnost.dupli_rbr", izvorni)
    izvorni["rbrovi"] = "2"
    assert problem.parametri["rbrovi"] == "1"
    with pytest.raises(TypeError):
        problem.parametri["rbrovi"] = "3"
    assert problem == Problem("spremnost.dupli_rbr", {"rbrovi": "1"})
    assert hash(problem) == hash(Problem("spremnost.dupli_rbr", {"rbrovi": "1"}))
    assert {problem, Problem("spremnost.dupli_rbr", {"rbrovi": "1"})} == {problem}

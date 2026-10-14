"""Pregled spremnosti vježbe (priča 3.3): čista funkcija jezgre."""

from pathlib import Path

import pytest

from provjera.jezgra import formula, profil, spremnost
from provjera.jezgra.poruke import KATALOG, poruka
from provjera.jezgra.samoprovjera import NemaSkupa, RezultatPrimjera, StatusPrimjera, usporedi
from provjera.jezgra.spremnost import Problem

KORIJEN = Path(__file__).resolve().parents[1]
VJEZBA_1 = KORIJEN / "profili" / "vjezba_1.toml"


@pytest.fixture(scope="module")
def vjezba():
    return profil.ucitaj(VJEZBA_1.read_bytes())


# Samoprovjera koja prolazi: ispravan rad i jedna pokvarena varijanta.
PROLAZ = (
    usporedi("ispravan", set(), set(), {"R-MARGINE"}),
    usporedi("krive_margine_tijela", {"R-MARGINE"}, {"R-MARGINE"}, {"R-MARGINE"}),
)


def _pregled(p, rbrovi, aktivnih, samoprovjera=PROLAZ):
    return spremnost.pregled(p, rbrovi, aktivnih, samoprovjera)


def _bez_pravila(p: profil.Profil) -> profil.Profil:
    pravila = {
        pid: postavke.model_copy(update={"ukljuceno": False})
        for pid, postavke in p.pravila.items()
    }
    return p.model_copy(update={"pravila": pravila})


def test_spremno(vjezba):
    rezultat = _pregled(vjezba, list(range(1, 79)), 78)
    assert rezultat.spremno
    assert rezultat.problemi == ()
    assert rezultat.naziv == "Vježba 1"
    assert rezultat.verzija == profil.verzija(vjezba)
    assert rezultat.broj_aktivnih == 78
    assert rezultat.broj_ukljucenih_pravila == sum(p.ukljuceno for p in vjezba.pravila.values())
    assert rezultat.broj_ukljucenih_pravila > 0
    assert rezultat.margine_jedinstvene is True


def test_bez_popisa(vjezba):
    rezultat = _pregled(vjezba, None, 0)
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.nema_popisa"),)
    assert rezultat.margine_jedinstvene is None


def test_prevelik_rbr(vjezba):
    najveci = formula.najveci_rbr(vjezba.formula)
    rezultat = _pregled(vjezba, [1, 2, najveci + 1], 3)
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
    assert _pregled(vjezba, list(range(1, 501)), 500).spremno


def test_bez_aktivnih(vjezba):
    rezultat = _pregled(vjezba, [1, 2, 3], 0)
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.nema_aktivnih"),)


def test_sva_pravila_iskljucena(vjezba):
    rezultat = _pregled(_bez_pravila(vjezba), [1, 2], 2)
    assert not rezultat.spremno
    assert rezultat.broj_ukljucenih_pravila == 0
    assert rezultat.problemi == (Problem("spremnost.nema_pravila"),)


def test_iste_margine_navode_oba_rbr(vjezba, monkeypatch):
    # Formula po konstrukciji daje različite margine; provjera ostaje obrambena.
    prava = formula.margine

    def margine(rbr, parametri):
        return prava(1 if rbr == 3 else rbr, parametri)

    monkeypatch.setattr(formula, "margine", margine)
    rezultat = _pregled(vjezba, [1, 2, 3], 3)
    assert rezultat.margine_jedinstvene is False
    assert rezultat.problemi == (Problem("spremnost.iste_margine", {"prvi": 1, "drugi": 3}),)


def test_vise_problema_odjednom(vjezba):
    najveci = formula.najveci_rbr(vjezba.formula)
    rezultat = _pregled(_bez_pravila(vjezba), [najveci + 2, najveci + 1], 0)
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
    rezultat = _pregled(vjezba, [1, 2, 2, 3, 3, 3], 6)
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


# --- Samoprovjera u spremnosti (priča 3.4) -------------------------------------


def test_samoprovjera_nije_pokrenuta(vjezba):
    rezultat = _pregled(vjezba, list(range(1, 79)), 78, None)
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.samoprovjera_nije_pokrenuta"),)


def test_samoprovjera_ne_prolazi_navodi_broj_odstupanja(vjezba):
    odstupanje = usporedi("krive_margine_tijela", {"R-MARGINE"}, set(), {"R-MARGINE"})
    rezultat = _pregled(vjezba, list(range(1, 79)), 78, (PROLAZ[0], odstupanje))
    assert not rezultat.spremno
    assert rezultat.problemi == (Problem("spremnost.samoprovjera_ne_prolazi", {"broj": 1}),)
    tekst = poruka(rezultat.problemi[0].kljuc, **rezultat.problemi[0].parametri)
    assert "1" in tekst


def test_samoprovjera_bez_skupa_ne_prolazi(vjezba):
    """Aplikacija za ``GreskaReferentnog`` predaje ``NemaSkupa`` s porukom greške."""
    nema = NemaSkupa("samoprovjera.nema_skupa", {"mapa": "x/vjezba_9"})
    rezultat = _pregled(vjezba, list(range(1, 79)), 78, nema)
    razlog = poruka("samoprovjera.nema_skupa", mapa="x/vjezba_9")
    assert rezultat.problemi == (
        Problem("spremnost.samoprovjera_nema_skupa", {"poruka": razlog}),
    )
    assert "x/vjezba_9" in poruka(rezultat.problemi[0].kljuc, **rezultat.problemi[0].parametri)


def test_samoprovjera_prolazi_bez_problema(vjezba):
    assert _pregled(vjezba, list(range(1, 79)), 78, PROLAZ).spremno


def test_samoprovjera_kljucevi_u_katalogu():
    assert "spremnost.samoprovjera_nije_pokrenuta" in KATALOG
    assert "spremnost.samoprovjera_ne_prolazi" in KATALOG
    assert "spremnost.samoprovjera_nema_skupa" in KATALOG
    assert PROLAZ[0] == RezultatPrimjera("ispravan", frozenset(), frozenset(), StatusPrimjera.PROLAZI)

import json
from pathlib import Path

import pytest

from provjera.jezgra import formula, profil

KORIJEN = Path(__file__).resolve().parents[1]
SNAPSHOT = KORIJEN / "tests" / "snapshot" / "formula_vjezba_1.json"


@pytest.fixture(scope="module")
def parametri():
    return profil.ucitaj((KORIJEN / "tests" / "fixtures" / "vjezba_1_baseline.toml").read_bytes()).formula


def _sve(parametri, do=500):
    return [formula.margine(r, parametri) for r in range(1, do + 1)]


def test_kombinacije_su_jedinstvene(parametri):
    margine = _sve(parametri)
    assert len(set(margine)) == 500


def test_svaka_margina_unutar_raspona_u_koraku(parametri):
    osnovice = (parametri.osnovica_gore, parametri.osnovica_dolje, parametri.osnovica_lijevo, parametri.osnovica_desno)
    for m in _sve(parametri):
        for vrijednost, osnovica in zip((m.gore, m.dolje, m.lijevo, m.desno), osnovice):
            pomak = vrijednost - osnovica
            assert abs(pomak) <= parametri.raspon
            assert pomak % parametri.korak == 0


def test_barem_dvije_pomaknute_i_nikad_naslovnica(parametri):
    osnovice = (parametri.osnovica_gore, parametri.osnovica_dolje, parametri.osnovica_lijevo, parametri.osnovica_desno)
    for m in _sve(parametri):
        vrijednosti = (m.gore, m.dolje, m.lijevo, m.desno)
        assert sum(v != o for v, o in zip(vrijednosti, osnovice)) >= 2
        assert vrijednosti != (parametri.naslovnica,) * 4


def test_iskljucene_kombinacije_ne_postoje_ni_na_cijelom_prostoru(parametri):
    # 11^4 kombinacija − 1 bez pomaka − 4·10 s jednom pomaknutom marginom.
    assert formula.najveci_rbr(parametri) == 11**4 - 1 - 40


def test_naslovnica_iskljucena_i_kad_je_inace_dopustena(parametri):
    # Naslovnica 3 cm: kombinacija 3/3/3/3 ima tri pomaknute margine pa bi inače bila dopuštena.
    p = parametri.model_copy(update={"naslovnica": 30})
    assert all((m.gore, m.dolje, m.lijevo, m.desno) != (30, 30, 30, 30) for m in formula._dopustene(p))
    assert formula.najveci_rbr(p) == formula.najveci_rbr(parametri) - 1


def test_drugo_sjeme_daje_drukciji_raspored(parametri):
    drugo = parametri.model_copy(update={"sjeme": parametri.sjeme + 1})
    assert _sve(parametri, 50) != _sve(drugo, 50)


def test_rbr_izvan_raspona_baca_value_error(parametri):
    for rbr in (0, -1, formula.najveci_rbr(parametri) + 1):
        with pytest.raises(ValueError):
            formula.margine(rbr, parametri)


def test_snapshot_rbr_1_do_500(parametri):
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert snapshot["formula_verzija"] == formula.FORMULA_VERZIJA, (
        "FORMULA_VERZIJA promijenjena: regeneriraj snapshot formule."
    )
    izracunato = [[m.gore, m.dolje, m.lijevo, m.desno] for m in _sve(parametri)]
    assert izracunato == snapshot["margine_mm_gore_dolje_lijevo_desno"], (
        "Margine su se promijenile: podigni FORMULA_VERZIJA i regeneriraj snapshot."
    )
    assert formula.otisak(parametri) == snapshot["otisak"]


def test_otisak_ukljucuje_formula_verziju(parametri, monkeypatch):
    prije = formula.otisak(parametri)
    assert len(prije) == 12
    monkeypatch.setattr(formula, "FORMULA_VERZIJA", formula.FORMULA_VERZIJA + 1)
    assert formula.otisak(parametri) != prije


def test_otisak_se_mijenja_sa_sjemenom(parametri):
    drugo = parametri.model_copy(update={"sjeme": 1})
    assert formula.otisak(parametri) != formula.otisak(drugo)

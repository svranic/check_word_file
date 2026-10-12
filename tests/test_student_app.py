from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from provjera.jezgra import formula, profil
from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.poruke import formatiraj, poruka

KORIJEN = Path(__file__).resolve().parents[1]
STUDENT = str(KORIJEN / "apps" / "student.py")


@pytest.fixture
def aplikacija():
    return AppTest.from_file(STUDENT).run()


def _posalji(at: AppTest, unos: str) -> AppTest:
    at.text_input(key="rbr_unos").input(unos)
    return at.button[0].click().run()


def test_ispravan_rbr_prikazuje_margine_i_obrazac(aplikacija):
    at = _posalji(aplikacija, "54.")
    assert not at.exception
    p = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
    ocekivane = formula.margine(54, p.formula).u_twips()
    assert [(m.label, m.value) for m in at.metric] == [
        (poruka(f"margine.{s}"), formatiraj(ocekivane[s], Jedinica.TWIPS))
        for s in ("gore", "dolje", "lijevo", "desno")
    ]
    tekst = " ".join(m.value for m in at.markdown)
    assert "Izgled (Layout) → Margine (Margins)" in tekst
    assert "Ime_Prezime_GiG_OG_Vjezba_1.docx" in tekst
    natpisi = [c.value for c in at.caption]
    assert poruka("margine.naslovnica", naslovnica="2,5 cm") in natpisi
    assert poruka("margine.usporedi") in natpisi
    assert not at.error


@pytest.mark.parametrize(
    ("unos", "kljuc"), [("", "rbr.prazno"), ("abc", "rbr.neispravno"), ("5,5", "rbr.neispravno")]
)
def test_neispravan_rbr_prikazuje_poruku(aplikacija, unos, kljuc):
    at = _posalji(aplikacija, unos)
    assert [e.value for e in at.error] == [poruka(kljuc)]
    assert not at.metric


def test_prevelik_rbr(aplikacija):
    at = _posalji(aplikacija, "99999")
    p = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
    najveci = formula.najveci_rbr(p.formula)
    assert [e.value for e in at.error] == [poruka("rbr.prevelik", rbr=99999, najveci=najveci)]
    assert not at.metric


def test_promjena_rbr_brise_provjeru(aplikacija):
    at = _posalji(aplikacija, "54")
    at.session_state["izvjestaj"] = "stari izvještaj"
    at.session_state["datoteka"] = b"stari bajtovi"
    at = _posalji(at, "55")
    assert "izvjestaj" not in at.session_state
    assert "datoteka" not in at.session_state


def test_isti_rbr_ne_brise_provjeru(aplikacija):
    at = _posalji(aplikacija, "54")
    at.session_state["izvjestaj"] = "izvještaj"
    at = _posalji(at, "54.")
    assert at.session_state["izvjestaj"] == "izvještaj"


def test_promjena_vjezbe_brise_provjeru(monkeypatch):
    p = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
    druga = p.model_copy(
        update={"vjezba": p.vjezba.model_copy(update={"id": "vjezba_2", "naziv": "Vježba 2"})}
    )
    monkeypatch.setattr(profil, "objavljeni", lambda _sadrzaji: ([p, druga], 0))
    at = _posalji(AppTest.from_file(STUDENT).run(), "54")
    at.session_state["izvjestaj"] = "izvještaj"
    at = at.selectbox(key="vjezba").select("vjezba_2").run()
    assert "izvjestaj" not in at.session_state


def test_neispravan_profil_daje_neutralnu_poruku(monkeypatch):
    monkeypatch.setattr(profil, "objavljeni", lambda _sadrzaji: ([], 1))
    at = AppTest.from_file(STUDENT).run()
    assert [w.value for w in at.warning] == [poruka("profil.nedostupno")]
    assert not at.text_input


def test_djelomicno_neispravni_profili(monkeypatch):
    p = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
    monkeypatch.setattr(profil, "objavljeni", lambda _sadrzaji: ([p], 1))
    at = AppTest.from_file(STUDENT).run()
    assert [w.value for w in at.warning] == [poruka("profil.djelomicno_nedostupno")]
    assert at.selectbox(key="vjezba")
    assert at.text_input(key="rbr_unos")

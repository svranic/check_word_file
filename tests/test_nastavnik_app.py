"""Nastavnička aplikacija (priča 3.1): podatkovna mapa, odabir vježbe, učitavanje ISVU popisa."""

import sys
from pathlib import Path

import pytest
from alati.isvu import ISPRAVNI, S_GRESKAMA, izvoz
from streamlit.testing.v1 import AppTest

from provjera.adapteri.popis import ucitaj_isvu
from provjera.jezgra import profil
from provjera.jezgra.poruke import poruka

KORIJEN = Path(__file__).resolve().parents[1]
NASTAVNIK = str(KORIJEN / "apps" / "nastavnik.py")
VJEZBA_1 = KORIJEN / "profili" / "vjezba_1.toml"


@pytest.fixture
def aplikacija():
    return AppTest.from_file(NASTAVNIK, default_timeout=30).run()


def _profil(id_vjezbe: str, naziv: str, objavljeno: bool) -> profil.Profil:
    p = profil.ucitaj(VJEZBA_1.read_bytes())
    return p.model_copy(
        update={
            "vjezba": p.vjezba.model_copy(
                update={"id": id_vjezbe, "naziv": naziv, "objavljeno": objavljeno}
            )
        }
    )


def test_prikazuje_podatkovnu_mapu_i_odabir_vjezbe(aplikacija):
    at = aplikacija
    assert not at.exception
    assert at.title[0].value == poruka("nastavnik.naslov")
    assert at.text_input(key="podatkovna_mapa").value == str(Path.home() / "ProvjeraWord")
    assert at.selectbox(key="vjezba").options == ["Vježba 1"]
    assert at.file_uploader
    assert not at.warning


@pytest.mark.parametrize("mapa", [".", "podaci", "tests/../podaci/x"])
def test_mapa_u_repozitoriju_zaustavlja_stranicu(aplikacija, mapa):
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(KORIJEN / mapa)).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("nastavnik.mapa_u_repozitoriju")]
    assert not at.selectbox
    assert not at.file_uploader


def test_mapa_izvan_repozitorija_je_prihvacena(aplikacija, tmp_path):
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(tmp_path / "Provjera")).run()
    assert not at.warning
    assert at.selectbox(key="vjezba")


def test_prazna_mapa_zaustavlja_stranicu(aplikacija):
    at = aplikacija.text_input(key="podatkovna_mapa").input("  ").run()
    assert [e.value for e in at.error] == [poruka("nastavnik.mapa_prazna")]
    assert not at.selectbox


def test_nudi_i_neobjavljene_vjezbe_te_broji_neispravne(monkeypatch):
    profili = [_profil("vjezba_1", "Vježba 1", True), _profil("vjezba_2", "Vježba 2", False)]
    monkeypatch.setattr(profil, "svi", lambda _sadrzaji: (profili, 2))
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    assert not at.exception
    assert at.selectbox(key="vjezba").options == [
        "Vježba 1",
        poruka("nastavnik.vjezba_neobjavljena", naziv="Vježba 2"),
    ]
    assert [w.value for w in at.warning] == [poruka("nastavnik.neispravni_profili", broj=2)]


def test_bez_ispravnih_profila(monkeypatch):
    monkeypatch.setattr(profil, "svi", lambda _sadrzaji: ([], 1))
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    assert [e.value for e in at.error] == [poruka("nastavnik.nema_profila")]
    assert not at.file_uploader


def test_svi_ukljucuje_neobjavljene_i_broji_duplikate():
    objavljen = VJEZBA_1.read_bytes()
    neobjavljen = objavljen.replace(b"objavljeno = true", b"objavljeno = false")
    assert neobjavljen != objavljen
    drugi = neobjavljen.replace(b'id = "vjezba_1"', b'id = "vjezba_9"')
    assert drugi != neobjavljen
    profili, neispravnih = profil.svi([objavljen, drugi, neobjavljen, b"nije toml ["])
    assert [p.vjezba.id for p in profili] == ["vjezba_1", "vjezba_9"]
    assert neispravnih == 2


def _ucitaj(at: AppTest, sadrzaj: bytes) -> AppTest:
    at.file_uploader(key="isvu").set_value(
        ("popis.xlsx", sadrzaj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    )
    return at.run()


def test_ispravan_popis_prikazuje_studente(aplikacija):
    at = _ucitaj(aplikacija, izvoz(ISPRAVNI))
    assert not at.exception
    assert [s.value for s in at.success] == [poruka("nastavnik.popis_ispravan")]
    tablica = at.dataframe[0].value
    assert list(tablica.columns) == [
        poruka(f"nastavnik.stupac_{s}") for s in ("rbr", "jmbag", "ime", "prezime", "aktivan")
    ]
    assert len(tablica) == len(ISPRAVNI)
    assert tablica.iloc[0, 1] == "0036123456"
    tekst = " ".join(m.value for m in at.markdown)
    assert poruka("popis.broj_neaktivnih", broj=1) in tekst


def test_popis_s_greskama_prikazuje_sve_greske(aplikacija):
    at = _ucitaj(aplikacija, izvoz(S_GRESKAMA))
    assert not at.exception
    popis = ucitaj_isvu(izvoz(S_GRESKAMA))
    assert [e.value for e in at.error] == [
        poruka("nastavnik.popis_neispravan", broj=len(popis.greske))
    ]
    redak = popis.greske[0].redak
    ocekivano = "\n".join(
        f"- Redak {g.redak}: {poruka(g.poruka_kljuc, **g.parametri)}" for g in popis.greske
    )
    assert ocekivano.startswith(f"- Redak {redak}: {poruka('popis.rbr_neispravan')}")
    assert ocekivano in [m.value for m in at.markdown]
    assert not at.success


def test_necitljiva_datoteka_ne_rusi_stranicu(aplikacija):
    at = _ucitaj(aplikacija, b"nije xlsx")
    assert not at.exception
    assert f"- {poruka('popis.necitljiv')}" in [m.value for m in at.markdown]


def test_stupac_aktivan_prikazuje_da_ne(aplikacija):
    at = _ucitaj(aplikacija, izvoz(ISPRAVNI))
    stupac = at.dataframe[0].value[poruka("nastavnik.stupac_aktivan")].tolist()
    da, ne = poruka("vrijednost.da"), poruka("vrijednost.ne")
    assert stupac == [da, da, ne, da, da]  # treći student u ISPRAVNI je ispisan


@pytest.mark.parametrize("vrsta", ["relativna", "nul", "datoteka"])
def test_neispravna_mapa_zaustavlja_stranicu(aplikacija, tmp_path, vrsta):
    datoteka = tmp_path / "nije_mapa.txt"
    datoteka.write_text("x", encoding="utf-8")
    unos = {
        "relativna": "ProvjeraWord",
        "nul": str(tmp_path / "a\0b"),
        "datoteka": str(datoteka),
    }[vrsta]
    at = aplikacija.text_input(key="podatkovna_mapa").input(unos).run()
    assert not at.exception
    assert [e.value for e in at.error] == [poruka("nastavnik.mapa_neispravna")]
    assert not at.selectbox


@pytest.mark.skipif(sys.platform != "win32", reason="Windows putanje ne razlikuju velika i mala slova")
def test_mapa_u_repozitoriju_drugacijih_slova(aplikacija):
    mapa = str(KORIJEN / "podaci").swapcase()
    at = aplikacija.text_input(key="podatkovna_mapa").input(mapa).run()
    assert [w.value for w in at.warning] == [poruka("nastavnik.mapa_u_repozitoriju")]
    assert not at.selectbox

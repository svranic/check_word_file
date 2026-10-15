"""Nastavnička aplikacija (priča 3.1): podatkovna mapa, odabir vježbe, učitavanje ISVU popisa."""

import io
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest
from alati.isvu import (
    ISPIS,
    ISPRAVNI,
    KASNI_UPIS,
    PONOVNI_UPIS,
    PRENUMERIRANI,
    S_GRESKAMA,
    UPISAN,
    izvoz,
)
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from provjera.adapteri import pdf_svojstva
from provjera.adapteri import popis as popis_modul
from provjera.adapteri.popis import (
    ZONA,
    Student,
    procitaj_izdano,
    procitaj_zamrznuti,
    spremi,
    ucitaj_isvu,
    zamrzni,
    zapisi_izdano,
)
from provjera.jezgra import formula, profil
from provjera.jezgra.poruke import poruka

KORIJEN = Path(__file__).resolve().parents[1]
NASTAVNIK = str(KORIJEN / "apps" / "nastavnik.py")
VJEZBA_1 = KORIJEN / "profili" / "vjezba_1.toml"


@pytest.fixture(autouse=True)
def izolirani_dom(tmp_path, monkeypatch):
    """Zadana podatkovna mapa (``~/ProvjeraWord``) u testovima je u ``tmp_path``.

    Tako ni testovi koji ne mijenjaju mapu ne čitaju stvarni zamrznuti popis.
    """
    dom = tmp_path / "dom"
    dom.mkdir()
    monkeypatch.setenv("USERPROFILE", str(dom))
    monkeypatch.setenv("HOME", str(dom))
    assert Path.home() == dom


@pytest.fixture
def aplikacija():
    return AppTest.from_file(NASTAVNIK, default_timeout=30).run()


@pytest.fixture
def podaci(tmp_path):
    return tmp_path / "ProvjeraWord"


@pytest.fixture
def u_mapi(aplikacija, podaci):
    """Aplikacija s podatkovnom mapom u ``tmp_path`` (nikad stvarna ``~/ProvjeraWord``)."""
    return aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()


def _zamijeni(sadrzaj: bytes, staro: bytes, novo: bytes) -> bytes:
    assert staro in sadrzaj
    return sadrzaj.replace(staro, novo)


def _toml(id_vjezbe: str, naziv: str, objavljeno: bool) -> bytes:
    sadrzaj = _zamijeni(VJEZBA_1.read_bytes(), b'id = "vjezba_1"', f'id = "{id_vjezbe}"'.encode())
    sadrzaj = _zamijeni(sadrzaj, 'naziv = "Vježba 1"'.encode(), f'naziv = "{naziv}"'.encode())
    return _zamijeni(
        sadrzaj, b"objavljeno = true", f"objavljeno = {str(objavljeno).lower()}".encode()
    )


# Dvije greške: prazan naziv vježbe i negativno sjeme formule.
NEISPRAVAN_TOML = _zamijeni(
    _toml("vjezba_8", "", True), b"sjeme = 20261012", b"sjeme = -1"
)


def _profili(monkeypatch, datoteke: list[tuple[str, bytes]]) -> None:
    """Mapa profila sadrži točno ``datoteke`` (ime, sadržaj); parsira ih stvarni ``ucitaj_sve``."""
    pravi = profil.ucitaj_sve
    monkeypatch.setattr(profil, "ucitaj_sve", lambda _imenovani: pravi(datoteke))


def test_prikazuje_podatkovnu_mapu_i_odabir_vjezbe(aplikacija):
    at = aplikacija
    assert not at.exception
    assert at.title[0].value == poruka("nastavnik.naslov")
    assert at.text_input(key="podatkovna_mapa").value == str(Path.home() / "ProvjeraWord")
    assert at.selectbox(key="vjezba").options == ["Vježba 1"]
    assert at.file_uploader
    # Jedino upozorenje: vježba nije spremna (nema zamrznutog popisa, samoprovjera nije pokrenuta).
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]


@pytest.mark.parametrize("mapa", [".", "podaci", "tests/../podaci/x"])
def test_mapa_u_repozitoriju_zaustavlja_stranicu(aplikacija, mapa):
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(KORIJEN / mapa)).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("nastavnik.mapa_u_repozitoriju")]
    assert not at.selectbox
    assert not at.file_uploader


def test_mapa_izvan_repozitorija_je_prihvacena(aplikacija, tmp_path):
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(tmp_path / "Provjera")).run()
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]
    assert at.selectbox(key="vjezba")


def test_prazna_mapa_zaustavlja_stranicu(aplikacija):
    at = aplikacija.text_input(key="podatkovna_mapa").input("  ").run()
    assert [e.value for e in at.error] == [poruka("nastavnik.mapa_prazna")]
    assert not at.selectbox


def test_nudi_i_neobjavljene_i_neispravne_vjezbe(monkeypatch):
    _profili(
        monkeypatch,
        [
            ("a_neispravan.toml", NEISPRAVAN_TOML),
            ("vjezba_1.toml", _toml("vjezba_1", "Vježba 1", True)),
            ("vjezba_2.toml", _toml("vjezba_2", "Vježba 2", False)),
            ("z_duplikat.toml", _toml("vjezba_1", "Kopija", True)),
        ],
    )
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    assert not at.exception
    # Ispravni prvi, da zadani odabir bude upotrebljiv; neispravni pod imenom datoteke.
    assert at.selectbox(key="vjezba").options == [
        "Vježba 1",
        poruka("nastavnik.vjezba_neobjavljena", naziv="Vježba 2"),
        poruka("nastavnik.profil_neispravan", datoteka="a_neispravan.toml"),
        poruka("nastavnik.profil_neispravan", datoteka="z_duplikat.toml"),
    ]
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]
    assert at.file_uploader


def test_neispravan_profil_prikazuje_sve_greske_i_zaustavlja(monkeypatch):
    _profili(monkeypatch, [("a_neispravan.toml", NEISPRAVAN_TOML)])
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    assert not at.exception
    assert at.selectbox(key="vjezba").options == [
        poruka("nastavnik.profil_neispravan", datoteka="a_neispravan.toml")
    ]
    assert [e.value.replace("\\", "") for e in at.error] == [
        poruka("nastavnik.profil_greske", datoteka="a_neispravan.toml", broj=2)
    ]
    [greske] = [m.value.replace("\\", "") for m in at.markdown]
    redci = greske.splitlines()
    assert len(redci) == 2
    assert any(r.startswith("- vjezba.naziv:") for r in redci)
    assert any(r.startswith("- formula.sjeme:") for r in redci)
    # Ostatak stranice se ne prikazuje.
    assert not at.subheader
    assert not at.file_uploader


def test_dupli_id_prikazuje_gresku_kljuca(monkeypatch):
    _profili(
        monkeypatch,
        [
            ("vjezba_1.toml", _toml("vjezba_1", "Vježba 1", True)),
            ("z_duplikat.toml", _toml("vjezba_1", "Kopija", True)),
        ],
    )
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    at = at.selectbox(key="vjezba").set_value("z_duplikat.toml").run()
    assert not at.exception
    assert [e.value.replace("\\", "") for e in at.error] == [
        poruka("nastavnik.profil_greske", datoteka="z_duplikat.toml", broj=1)
    ]
    assert "vjezba.id:" in at.markdown[0].value.replace("\\", "")
    assert not at.file_uploader


def test_ucitaj_sve_vraca_profil_ili_gresku():
    ispravan = VJEZBA_1.read_bytes()
    rezultat = profil.ucitaj_sve(
        [("a.toml", ispravan), ("b.toml", NEISPRAVAN_TOML), ("c.toml", ispravan)]
    )
    assert [ime for ime, _ in rezultat] == ["a.toml", "b.toml", "c.toml"]
    assert isinstance(rezultat[0][1], profil.Profil)
    assert isinstance(rezultat[1][1], profil.GreskaProfila)
    assert len(rezultat[1][1].greske) == 2
    assert isinstance(rezultat[2][1], profil.GreskaProfila)
    assert rezultat[2][1].greske == (poruka("profil.dupli_id", datoteka="a.toml"),)
    assert rezultat[2][1].greske[0].startswith("vjezba.id:")


def test_ucitaj_sve_dupli_id_zadrzava_jedini_objavljeni():
    nacrt = _toml("vjezba_1", "Nacrt", False)
    objavljen = _toml("vjezba_1", "Vježba 1", True)
    rezultat = dict(profil.ucitaj_sve([("a_nacrt.toml", nacrt), ("b_ziva.toml", objavljen)]))
    assert isinstance(rezultat["b_ziva.toml"], profil.Profil)
    assert rezultat["a_nacrt.toml"].greske == (
        poruka("profil.dupli_id", datoteka="b_ziva.toml"),
    )


@pytest.mark.parametrize("objavljeno", [True, False])
def test_ucitaj_sve_dupli_id_bez_jedinog_objavljenog_zadrzava_prvi(objavljeno):
    prvi = _toml("vjezba_1", "Prvi", objavljeno)
    drugi = _toml("vjezba_1", "Drugi", objavljeno)
    rezultat = dict(profil.ucitaj_sve([("a.toml", prvi), ("b.toml", drugi)]))
    assert isinstance(rezultat["a.toml"], profil.Profil)
    assert rezultat["b.toml"].greske == (poruka("profil.dupli_id", datoteka="a.toml"),)


def test_stvarna_mapa_profila_s_neispravnom_i_necitljivom(tmp_path, monkeypatch):
    """Kopija aplikacije u ``tmp_path/app/apps``: njezin ``MAPA_PROFILA`` je ``tmp_path/app/profili``.

    Skripta se pod AppTestom izvodi iznova, pa se globalni ``MAPA_PROFILA`` ne može
    monkeypatchati; kopija daje stvarnu privremenu mapu profila bez izmjene koda.
    """
    korijen = tmp_path / "app"
    (korijen / "apps").mkdir(parents=True)
    (korijen / "apps" / "nastavnik.py").write_bytes(Path(NASTAVNIK).read_bytes())
    mapa = korijen / "profili"
    mapa.mkdir()
    (mapa / "vjezba_1.toml").write_bytes(VJEZBA_1.read_bytes())
    (mapa / "pokvaren.toml").write_bytes(NEISPRAVAN_TOML)
    (mapa / "zakljucan.toml").write_bytes(VJEZBA_1.read_bytes())
    pravi = Path.read_bytes

    def read_bytes(self):
        if self.name == "zakljucan.toml":
            raise PermissionError(13, "Pristup odbijen")
        return pravi(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    at = AppTest.from_file(str(korijen / "apps" / "nastavnik.py"), default_timeout=30).run()
    assert not at.exception
    assert at.selectbox(key="vjezba").options == [
        "Vježba 1",
        poruka("nastavnik.profil_neispravan", datoteka="pokvaren.toml"),
        poruka("nastavnik.profil_neispravan", datoteka="zakljucan.toml"),
    ]
    at = at.selectbox(key="vjezba").set_value("zakljucan.toml").run()
    assert not at.exception
    assert [m.value.replace("\\", "") for m in at.markdown] == [
        "- " + poruka("profil.necitljiv", razlog="Pristup odbijen")
    ]
    assert not at.file_uploader


def test_bez_profila(monkeypatch):
    _profili(monkeypatch, [])
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    assert [e.value for e in at.error] == [poruka("nastavnik.nema_profila")]
    assert not at.file_uploader


def _ucitaj(at: AppTest, sadrzaj: bytes) -> AppTest:
    at.file_uploader(key="isvu").set_value(
        ("popis.xlsx", sadrzaj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    )
    return at.run()


def test_ispravan_popis_prikazuje_studente(u_mapi):
    at = _ucitaj(u_mapi, izvoz(ISPRAVNI))
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


def test_popis_s_greskama_prikazuje_sve_greske(u_mapi):
    at = _ucitaj(u_mapi, izvoz(S_GRESKAMA))
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


def test_necitljiva_datoteka_ne_rusi_stranicu(u_mapi):
    at = _ucitaj(u_mapi, b"nije xlsx")
    assert not at.exception
    assert f"- {poruka('popis.necitljiv')}" in [m.value for m in at.markdown]


def test_stupac_aktivan_prikazuje_da_ne(u_mapi):
    at = _ucitaj(u_mapi, izvoz(ISPRAVNI))
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


# --- Zamrzavanje popisa (priča 3.2) -------------------------------------------


def _popis_csv(podaci: Path) -> Path:
    return podaci / "vjezba_1" / "popis.csv"


def _zamrzni_unaprijed(podaci: Path, retci=ISPRAVNI) -> Path:
    return zamrzni(ucitaj_isvu(izvoz(retci)).studenti, podaci / "vjezba_1")


def _tekst(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _redak_studenta(rbr: int, ime: str, prezime: str, jmbag: str) -> str:
    return "- " + poruka(
        "nastavnik.razlike_student", rbr=rbr, ime=ime, prezime=prezime, jmbag=jmbag
    )


def test_bez_zamrznutog_popisa_nudi_zamrzavanje(u_mapi, podaci):
    at = u_mapi
    assert [i.value for i in at.info] == [poruka("nastavnik.zamrznuti_nema")]
    at = _ucitaj(at, izvoz(ISPRAVNI))
    gumb = at.button(key="zamrzni")
    assert gumb.label == poruka("nastavnik.zamrzni")
    assert not gumb.disabled
    assert not _popis_csv(podaci).exists()  # učitavanje samo ne zapisuje ništa

    at = gumb.click().run()
    assert not at.exception
    putanja = _popis_csv(podaci)
    assert putanja.read_bytes().startswith(b"\xef\xbb\xbf")
    assert procitaj_zamrznuti(putanja) == ucitaj_isvu(izvoz(ISPRAVNI)).studenti
    assert poruka("nastavnik.zamrznuto", broj=5) in [s.value for s in at.success]
    stanje = poruka("nastavnik.zamrznuti_stanje", broj=5, aktivnih=4, neaktivnih=1)
    assert stanje in _tekst(at)
    assert not at.info
    # Nakon zamrzavanja nema više gumba „Zamrzni popis“, nego usporedba bez razlika.
    assert not [b for b in at.button if b.key == "zamrzni"]
    assert at.button(key="primijeni").disabled


def test_izvoz_s_greskama_ne_moze_se_zamrznuti(u_mapi, podaci):
    at = _ucitaj(u_mapi, izvoz(S_GRESKAMA))
    assert not at.exception
    assert at.button(key="zamrzni").disabled
    assert poruka("nastavnik.zamrzni_onemoguceno") in [c.value for c in at.caption]
    assert not _popis_csv(podaci).exists()


def test_postojeci_popis_prikazuje_razlike_i_ne_mijenja_se(podaci, aplikacija):
    putanja = _zamrzni_unaprijed(podaci)
    prije = putanja.read_bytes()
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    stanje = poruka("nastavnik.zamrznuti_stanje", broj=5, aktivnih=4, neaktivnih=1)
    assert stanje in _tekst(at)
    assert poruka("nastavnik.zamrznuti_ne_uredivati") in [c.value for c in at.caption]

    at = _ucitaj(at, izvoz(KASNI_UPIS))
    assert not at.exception
    assert not [b for b in at.button if b.key == "zamrzni"]
    tekst = _tekst(at)
    assert poruka("nastavnik.razlike_novi") in tekst
    assert (
        poruka(
            "nastavnik.razlike_novi_student",
            ime="Marta",
            prezime="Babić",
            jmbag="0036000006",
            rbr=6,
        )
        in tekst
    )
    gumb = at.button(key="primijeni")
    assert gumb.label == poruka("nastavnik.primijeni")
    assert not gumb.disabled
    assert putanja.read_bytes() == prije  # dok se ne primijeni

    at = gumb.click().run()
    assert not at.exception
    assert poruka("nastavnik.primijenjeno", novi=1, ispisani=0, ponovno=0) in [
        s.value for s in at.success
    ]
    studenti = procitaj_zamrznuti(putanja)
    assert studenti[:5] == ucitaj_isvu(izvoz(ISPRAVNI)).studenti
    assert studenti[5] == Student(6, "0036000006", "Marta", "Babić", True)
    assert at.button(key="primijeni").disabled  # isti izvoz više nema razlika
    assert poruka("nastavnik.razlike_nema") in [s.value for s in at.success]


def test_prenumeriran_izvoz_nema_razlika(podaci, aplikacija):
    putanja = _zamrzni_unaprijed(podaci)
    prije = putanja.read_bytes()
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(PRENUMERIRANI))
    assert poruka("nastavnik.razlike_nema") in [s.value for s in at.success]
    assert at.button(key="primijeni").disabled
    assert putanja.read_bytes() == prije


def test_ispis_i_ponovni_upis_u_aplikaciji(podaci, aplikacija):
    putanja = _zamrzni_unaprijed(podaci)
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(ISPIS))
    assert poruka("nastavnik.razlike_ispisani") in _tekst(at)
    assert _redak_studenta(2, "Đuro", "Šimić", "0036000002") in _tekst(at)
    assert _redak_studenta(4, "Luka", "Čačić", "0036000004") in _tekst(at)
    assert _redak_studenta(3, "Ivana", "Žužić", "0036000003") not in _tekst(at)  # već neaktivna
    at = at.button(key="primijeni").click().run()
    assert poruka("nastavnik.primijenjeno", novi=0, ispisani=2, ponovno=0) in [
        s.value for s in at.success
    ]
    assert [s.aktivan for s in procitaj_zamrznuti(putanja)] == [True, False, False, False, True]

    at = _ucitaj(at, izvoz(PONOVNI_UPIS))
    assert poruka("nastavnik.razlike_ponovno") in _tekst(at)
    assert _redak_studenta(3, "Ivana", "Žužić", "0036000003") in _tekst(at)
    at = at.button(key="primijeni").click().run()
    assert [s.aktivan for s in procitaj_zamrznuti(putanja)] == [True, True, True, True, True]
    assert [s.rbr for s in procitaj_zamrznuti(putanja)] == [1, 2, 3, 4, 5]


def test_postojeci_popis_i_izvoz_s_greskama_ne_nudi_primjenu(podaci, aplikacija):
    putanja = _zamrzni_unaprijed(podaci)
    prije = putanja.read_bytes()
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(S_GRESKAMA))
    assert not at.exception
    assert poruka("nastavnik.primijeni_onemoguceno") in [w.value for w in at.warning]
    assert not [b for b in at.button if b.key in ("primijeni", "zamrzni")]
    assert putanja.read_bytes() == prije


def test_promjena_imena_je_upozorenje(podaci, aplikacija):
    _zamrzni_unaprijed(podaci)
    retci = tuple(
        (*redak[:2], "Đurđa", *redak[3:]) if redak[1] == "0036000002" else redak
        for redak in ISPRAVNI
    )
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(retci))
    assert poruka("nastavnik.razlike_imena") in [w.value for w in at.warning]
    assert "Đuro Šimić → Đurđa Šimić" in _tekst(at)
    assert at.button(key="primijeni").disabled
    assert [i.value for i in at.info] == [poruka("nastavnik.razlike_nema_za_primjenu")]
    assert poruka("nastavnik.razlike_nema") not in [s.value for s in at.success]


def test_ostecen_popis_prikazuje_poruku_s_retkom(podaci, aplikacija):
    putanja = _popis_csv(podaci)
    putanja.parent.mkdir(parents=True)
    putanja.write_bytes(
        b"\xef\xbb\xbfrbr,jmbag,ime,prezime,aktivan\r\nx,0036000001,Ana,Horvat,true\r\n"
    )
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    redak = poruka("popis.redak", redak=2, poruka=poruka("popis.rbr_neispravan"))
    assert [e.value for e in at.error] == [
        poruka("nastavnik.zamrznuti_ostecen", putanja=str(putanja), poruka=redak)
    ]
    assert not at.file_uploader  # ništa se ne može zamrznuti ni primijeniti preko oštećenog


def _greske(at: AppTest) -> list[str]:
    return [e.value for e in at.error]


def test_zamrznut_nakon_prikaza_se_ne_prepisuje(u_mapi, podaci):
    at = _ucitaj(u_mapi, izvoz(ISPRAVNI))
    gumb = at.button(key="zamrzni")
    putanja = _zamrzni_unaprijed(podaci, KASNI_UPIS)  # npr. druga kartica preglednika
    prije = putanja.read_bytes()
    at = gumb.click().run()
    assert not at.exception
    assert poruka("nastavnik.vec_zamrznut") in _greske(at)
    assert poruka("nastavnik.zamrznuto", broj=5) not in [s.value for s in at.success]
    assert putanja.read_bytes() == prije


def test_neuspjelo_zamrzavanje_prikazuje_poruku(u_mapi, podaci, monkeypatch):
    def pukni(*_args):
        raise PermissionError("datoteka je zaključana")

    at = _ucitaj(u_mapi, izvoz(ISPRAVNI))
    # Pada i tvrda poveznica i zamjensko ekskluzivno stvaranje (npr. zaključana mapa).
    monkeypatch.setattr(popis_modul.os, "link", pukni)
    monkeypatch.setattr(popis_modul, "_stvori_iskljucivo", pukni)
    at = at.button(key="zamrzni").click().run()
    assert not at.exception
    assert poruka("nastavnik.zapis_neuspio") in _greske(at)
    assert not _popis_csv(podaci).exists()
    assert list(_popis_csv(podaci).parent.iterdir()) == []  # bez privremenih datoteka


def test_ostecen_popis_izmedu_prikaza_i_primjene(podaci, aplikacija):
    putanja = _zamrzni_unaprijed(podaci)
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(KASNI_UPIS))
    gumb = at.button(key="primijeni")
    ostecen = b"\xef\xbb\xbfrbr;jmbag;ime;prezime;aktivan\r\n"  # npr. spremljen u Excelu
    putanja.write_bytes(ostecen)
    at = gumb.click().run()
    assert not at.exception
    zaglavlje = poruka("popis.zamrznuti_zaglavlje", stupci="rbr,jmbag,ime,prezime,aktivan")
    ocekivano = poruka(
        "nastavnik.zamrznuti_ostecen",
        putanja=str(putanja),
        poruka=poruka("popis.redak", redak=1, poruka=zaglavlje),
    )
    assert ocekivano in _greske(at)
    assert not at.success
    assert putanja.read_bytes() == ostecen


def test_popis_promijenjen_izmedu_prikaza_i_primjene(podaci, aplikacija):
    putanja = _zamrzni_unaprijed(podaci)
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(KASNI_UPIS))
    gumb = at.button(key="primijeni")
    drugi = list(procitaj_zamrznuti(putanja))
    drugi[0] = Student(drugi[0].rbr, drugi[0].jmbag, drugi[0].ime, drugi[0].prezime, False)
    spremi(tuple(drugi), putanja)  # druga kartica je u međuvremenu primijenila nešto drugo
    prije = putanja.read_bytes()
    at = gumb.click().run()
    assert not at.exception
    assert poruka("nastavnik.popis_promijenjen") in _greske(at)
    assert not [s for s in at.success if s.value.startswith("Promjene su primijenjene")]
    assert putanja.read_bytes() == prije


def test_imena_se_prikazuju_bez_markdowna(podaci, aplikacija):
    _zamrzni_unaprijed(podaci)
    retci = (*ISPRAVNI, ("6.", "0036000006", "*Mia*", "[x](y)", UPISAN))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _ucitaj(at, izvoz(retci))
    tekst = _tekst(at)
    assert r"\*Mia\* \[x\]\(y\)" in tekst
    assert "*Mia*" not in tekst.replace(r"\*Mia\*", "")


# --- Spremnost (priča 3.3) ----------------------------------------------------


def _sintetski_popis(rbrovi, aktivan=True) -> tuple[Student, ...]:
    return tuple(
        Student(rbr=r, jmbag=f"{9900000000 + r}", ime="Ana", prezime=f"Testić{r}", aktivan=aktivan)
        for r in rbrovi
    )


def test_spremnost_spremno(podaci, aplikacija):
    spremi(_sintetski_popis(range(1, 79)), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=1)]
    assert "- " + poruka("spremnost.samoprovjera_nije_pokrenuta") in _tekst(at)
    at = at.button(key="samoprovjera").click().run()
    assert not at.exception
    assert poruka("spremnost.naslov") in [s.value for s in at.subheader]
    vjezba = profil.ucitaj(VJEZBA_1.read_bytes())
    tekst = _tekst(at).replace("\\", "")
    assert poruka("spremnost.profil", naziv="Vježba 1", verzija=profil.verzija(vjezba)) in tekst
    assert poruka("spremnost.aktivnih", broj=78) in tekst
    ukljucenih = sum(p.ukljuceno for p in vjezba.pravila.values())
    assert poruka("spremnost.pravila", broj=ukljucenih, ukupno=len(vjezba.pravila)) in tekst
    assert "✅ " + poruka("spremnost.margine_jedinstvene") in tekst
    [status] = [s for s in at.success if s.value == poruka("spremnost.spremno")]
    assert status.icon == "✅"
    assert not at.error
    assert not at.warning


def test_spremnost_bez_popisa(u_mapi):
    at = u_mapi
    [status] = at.warning
    assert status.value == poruka("spremnost.nije_spremno", broj=2)
    assert status.icon == "❌"
    assert "- " + poruka("spremnost.nema_popisa") in _tekst(at)
    assert "- " + poruka("spremnost.samoprovjera_nije_pokrenuta") in _tekst(at)
    assert poruka("spremnost.margine_neprovjerene") in _tekst(at)
    assert not at.success
    assert not at.error  # „nije spremno“ je upozorenje, ne greška


def test_spremnost_prevelik_rbr(podaci, aplikacija):
    najveci = formula.najveci_rbr(profil.ucitaj(VJEZBA_1.read_bytes()).formula)
    spremi(_sintetski_popis([1, 2, najveci + 1]), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]
    ocekivano = poruka("spremnost.rbr_izvan_raspona", rbrovi=str(najveci + 1), najveci=najveci)
    assert "- " + ocekivano in _tekst(at)


def test_spremnost_bez_aktivnih(podaci, aplikacija):
    spremi(_sintetski_popis([1, 2], aktivan=False), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]
    assert "- " + poruka("spremnost.nema_aktivnih") in _tekst(at)


def test_spremnost_sva_pravila_iskljucena(podaci, monkeypatch):
    bez_pravila = _zamijeni(VJEZBA_1.read_bytes(), b"ukljuceno = true", b"ukljuceno = false")
    _profili(monkeypatch, [("vjezba_1.toml", bez_pravila)])
    spremi(_sintetski_popis([1, 2]), _popis_csv(podaci))
    at = AppTest.from_file(NASTAVNIK, default_timeout=30).run()
    at = at.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]
    assert "- " + poruka("spremnost.nema_pravila") in _tekst(at)


def test_spremnost_neaktivni_rbr_izvan_raspona(podaci, aplikacija):
    najveci = formula.najveci_rbr(profil.ucitaj(VJEZBA_1.read_bytes()).formula)
    studenti = _sintetski_popis([1]) + _sintetski_popis([najveci + 1], aktivan=False)
    spremi(studenti, _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=2)]
    ocekivano = poruka("spremnost.rbr_izvan_raspona", rbrovi=str(najveci + 1), najveci=najveci)
    assert "- " + ocekivano in _tekst(at)
    assert poruka("spremnost.aktivnih", broj=1) in _tekst(at)


# --- Samoprovjera (priča 3.4) -------------------------------------------------


def _samoprovjera(at: AppTest) -> AppTest:
    return at.button(key="samoprovjera").click().run()


def test_samoprovjera_nije_pokrenuta(u_mapi):
    at = u_mapi
    assert poruka("samoprovjera.naslov") in [s.value for s in at.subheader]
    gumb = at.button(key="samoprovjera")
    assert gumb.label == poruka("samoprovjera.pokreni") == "Pokreni samoprovjeru"
    assert gumb.label != poruka("samoprovjera.naslov")
    assert not at.dataframe
    assert "- " + poruka("spremnost.samoprovjera_nije_pokrenuta") in _tekst(at)


def test_samoprovjera_prolazi_i_prikazuje_tablicu(u_mapi):
    at = _samoprovjera(u_mapi)
    assert not at.exception
    assert poruka("samoprovjera.prolazi") in [s.value for s in at.success]
    tablica = at.dataframe[0].value
    assert list(tablica.columns) == [
        poruka(f"samoprovjera.stupac_{s}")
        for s in ("primjer", "ocekivano", "pronadeno", "status")
    ]
    assert len(tablica) == 45
    assert set(tablica[poruka("samoprovjera.stupac_status")]) == {
        poruka("samoprovjera.status_prolazi")
    }
    redak = tablica.set_index(poruka("samoprovjera.stupac_primjer")).loc["krive_margine_tijela"]
    assert redak[poruka("samoprovjera.stupac_ocekivano")] == "R-MARGINE"
    assert redak[poruka("samoprovjera.stupac_pronadeno")] == "R-MARGINE"
    ispravan = tablica.set_index(poruka("samoprovjera.stupac_primjer")).loc["ispravan"]
    assert ispravan[poruka("samoprovjera.stupac_ocekivano")] == poruka("samoprovjera.nijedno")
    # Spremnost više ne navodi samoprovjeru (ostaje samo „nema popisa“).
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=1)]
    assert poruka("spremnost.samoprovjera_nije_pokrenuta") not in _tekst(at)


def test_samoprovjera_odstupanje(podaci, monkeypatch):
    # Pogrešna izmjena profila: tolerancija margina (~2 mm, iznad pola koraka) propušta
    # krive_margine_tijela. Validacija bi takav profil odbila, pa se zaobilazi model_copy.
    ispravan = profil.ucitaj(VJEZBA_1.read_bytes())
    tolerancije = ispravan.tolerancije.model_copy(update={"margine": 113})
    labav = ispravan.model_copy(update={"tolerancije": tolerancije})
    monkeypatch.setattr(profil, "ucitaj_sve", lambda _imenovani: [("vjezba_1.toml", labav)])
    spremi(_sintetski_popis(range(1, 79)), _popis_csv(podaci))
    at = AppTest.from_file(NASTAVNIK, default_timeout=60).run()
    at = at.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _samoprovjera(at)
    assert not at.exception
    assert [e.value for e in at.error] == [poruka("samoprovjera.ne_prolazi", broj=1)]
    tablica = at.dataframe[0].value.set_index(poruka("samoprovjera.stupac_primjer"))
    redak = tablica.loc["krive_margine_tijela"]
    assert redak[poruka("samoprovjera.stupac_status")] == poruka("samoprovjera.status_ne_prolazi")
    assert redak[poruka("samoprovjera.stupac_ocekivano")] == "R-MARGINE"
    assert redak[poruka("samoprovjera.stupac_pronadeno")] == poruka("samoprovjera.nijedno")
    assert [w.value for w in at.warning] == [poruka("spremnost.nije_spremno", broj=1)]
    assert "- " + poruka("spremnost.samoprovjera_ne_prolazi", broj=1) in _tekst(at)


def test_samoprovjera_iskljuceno_pravilo_preskace(monkeypatch):
    ispravan = profil.ucitaj(VJEZBA_1.read_bytes())
    pravila = dict(ispravan.pravila)
    pravila["R-OKVIRI"] = pravila["R-OKVIRI"].model_copy(update={"ukljuceno": False})
    bez_okvira = ispravan.model_copy(update={"pravila": pravila})
    monkeypatch.setattr(profil, "ucitaj_sve", lambda _imenovani: [("vjezba_1.toml", bez_okvira)])
    at = _samoprovjera(AppTest.from_file(NASTAVNIK, default_timeout=60).run())
    assert not at.exception
    assert poruka("samoprovjera.prolazi") in [s.value for s in at.success]
    tablica = at.dataframe[0].value.set_index(poruka("samoprovjera.stupac_primjer"))
    status = tablica[poruka("samoprovjera.stupac_status")]
    assert status["okvir_tekst"] == poruka("samoprovjera.status_preskoceno")
    assert status["okvir_naslov"] == poruka("samoprovjera.status_preskoceno")
    assert status["tekst_font"] == poruka("samoprovjera.status_prolazi")


def test_samoprovjera_bez_referentnog_skupa(monkeypatch):
    _profili(monkeypatch, [("vjezba_7.toml", _toml("vjezba_7", "Vježba 7", True))])
    at = _samoprovjera(AppTest.from_file(NASTAVNIK, default_timeout=30).run())
    assert not at.exception
    mapa = KORIJEN / "tests" / "referentni" / "vjezba_7"
    razlog = poruka("samoprovjera.nema_skupa", mapa=str(mapa))
    assert [e.value for e in at.error] == [razlog]
    assert not at.dataframe
    problem = poruka("spremnost.samoprovjera_nema_skupa", poruka=razlog)
    assert "- " + problem.replace("\\", "") in _tekst(at).replace("\\", "")


def test_promjena_profila_ponistava_samoprovjeru(monkeypatch):
    datoteke = [("vjezba_1.toml", VJEZBA_1.read_bytes())]
    _profili(monkeypatch, datoteke)
    at = _samoprovjera(AppTest.from_file(NASTAVNIK, default_timeout=60).run())
    assert poruka("samoprovjera.prolazi") in [s.value for s in at.success]
    # Ista vježba, nova verzija profila (npr. promijenjena tolerancija).
    datoteke[0] = (
        "vjezba_1.toml",
        _zamijeni(VJEZBA_1.read_bytes(), b'margine = "0,03 cm"', b'margine = "0,02 cm"'),
    )
    at = at.run()
    assert not at.exception
    assert poruka("samoprovjera.prolazi") not in [s.value for s in at.success]
    assert not at.dataframe
    assert "- " + poruka("spremnost.samoprovjera_nije_pokrenuta") in _tekst(at)


def _privremeni_skup(tmp_path: Path, monkeypatch) -> Path:
    """Kopija referentnog skupa Vježbe 1 u ``tmp_path``; aplikacija čita nju."""
    from provjera.adapteri import samoprovjera as adapter

    korijen = tmp_path / "referentni"
    shutil.copytree(KORIJEN / "tests" / "referentni" / "vjezba_1", korijen / "vjezba_1")
    pravi_pokreni, pravi_otisak = adapter.pokreni, adapter.otisak_skupa
    monkeypatch.setattr(adapter, "pokreni", lambda p, _mapa: pravi_pokreni(p, korijen))
    monkeypatch.setattr(adapter, "otisak_skupa", lambda v, _mapa: pravi_otisak(v, korijen))
    return korijen / "vjezba_1"


def test_samoprovjera_visak_i_manjak_datoteka(tmp_path, monkeypatch):
    mapa = _privremeni_skup(tmp_path, monkeypatch)
    shutil.copy(mapa / "ispravan.docx", mapa / "visak.docx")
    (mapa / "tekst_font.docx").unlink()
    at = _samoprovjera(AppTest.from_file(NASTAVNIK, default_timeout=60).run())
    assert not at.exception
    assert [e.value for e in at.error] == [poruka("samoprovjera.ne_prolazi", broj=2)]
    tablica = at.dataframe[0].value.set_index(poruka("samoprovjera.stupac_primjer"))
    ne_prolazi = poruka("samoprovjera.status_ne_prolazi")
    visak, manjak = tablica.loc["visak"], tablica.loc["tekst_font"]
    status = poruka("samoprovjera.stupac_status")
    assert visak[status] == poruka(
        "samoprovjera.status_razlog", status=ne_prolazi, razlog=poruka("samoprovjera.nema_zapisa")
    )
    assert manjak[status] == poruka(
        "samoprovjera.status_razlog", status=ne_prolazi, razlog=poruka("samoprovjera.nema_datoteke")
    )
    nista = poruka("samoprovjera.nista")
    assert visak[poruka("samoprovjera.stupac_ocekivano")] == nista
    assert visak[poruka("samoprovjera.stupac_pronadeno")] == nista
    assert manjak[poruka("samoprovjera.stupac_ocekivano")] == "R-TEKST"
    assert manjak[poruka("samoprovjera.stupac_pronadeno")] == nista


def test_promjena_referentnog_skupa_ponistava_samoprovjeru(tmp_path, monkeypatch):
    mapa = _privremeni_skup(tmp_path, monkeypatch)
    at = _samoprovjera(AppTest.from_file(NASTAVNIK, default_timeout=60).run())
    assert poruka("samoprovjera.prolazi") in [s.value for s in at.success]
    ocekivano = mapa / "ocekivano.toml"
    ocekivano.write_bytes(ocekivano.read_bytes() + b"\n# izmjena\n")
    at = at.run()
    assert not at.exception
    assert poruka("samoprovjera.prolazi") not in [s.value for s in at.success]
    assert not at.dataframe
    assert "- " + poruka("spremnost.samoprovjera_nije_pokrenuta") in _tekst(at)


# --- PDF sa svojstvima (priča 3.5) --------------------------------------------


def _popis_za_pdf() -> tuple[Student, ...]:
    """Rbr. 1–5, Rbr. 3 je ispisan."""
    return tuple(
        Student(rbr=r, jmbag=f"{9900000000 + r}", ime="Đurđa", prezime=f"Šćekić{r}", aktivan=r != 3)
        for r in range(1, 6)
    )


def _mapa_vjezbe(podaci: Path) -> Path:
    return podaci / "vjezba_1"


def test_pdf_nije_spremno_gumb_onemogucen(podaci, aplikacija):
    spremi(_popis_za_pdf(), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert poruka("nastavnik.pdf_naslov") in [s.value for s in at.subheader]
    gumb = at.button(key="generiraj_pdf")
    assert gumb.label == poruka("nastavnik.pdf_generiraj") == "Generiraj PDF"
    assert gumb.disabled
    assert poruka("nastavnik.pdf_onemoguceno") in [c.value for c in at.caption]
    mapa = _mapa_vjezbe(podaci)
    assert not (mapa / "svojstva_vjezba_1.pdf").exists()
    assert not (mapa / "izdano.json").exists()
    assert not at.get("download_button")


def test_pdf_bez_popisa_gumb_onemogucen(u_mapi, podaci):
    gumb = u_mapi.button(key="generiraj_pdf")
    assert gumb.disabled
    assert not _mapa_vjezbe(podaci).exists()


def test_pdf_spremno_generira_pdf_i_izdano(podaci, aplikacija):
    spremi(_popis_za_pdf(), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _samoprovjera(at)
    assert [s.value for s in at.success if s.value == poruka("spremnost.spremno")]
    gumb = at.button(key="generiraj_pdf")
    assert not gumb.disabled
    assert poruka("nastavnik.pdf_onemoguceno") not in [c.value for c in at.caption]
    at = gumb.click().run()
    assert not at.exception
    assert not at.error

    mapa = _mapa_vjezbe(podaci)
    pdf = mapa / "svojstva_vjezba_1.pdf"
    assert pdf.exists()
    putanja_poruka = poruka("nastavnik.pdf_generirano", putanja=str(pdf), broj=4)
    assert putanja_poruka in [s.value for s in at.success]

    vjezba = profil.ucitaj(VJEZBA_1.read_bytes())
    izdano = procitaj_izdano(mapa)
    assert izdano.formula_otisak == formula.otisak(vjezba.formula)
    assert izdano.profil_verzija == profil.verzija(vjezba)
    assert izdano.vrijeme.utcoffset() is not None
    podaci_izdano = json.loads((mapa / "izdano.json").read_text(encoding="utf-8"))
    assert set(podaci_izdano) == {"formula_otisak", "profil_verzija", "vrijeme"}

    tekst = "\n".join(s.extract_text() for s in PdfReader(io.BytesIO(pdf.read_bytes())).pages)
    for s in _popis_za_pdf():
        assert s.jmbag not in tekst
        assert (s.prezime in tekst) == s.aktivan
    assert "Đurđa" in tekst

    [preuzmi] = at.get("download_button")
    assert preuzmi.proto.label == poruka("nastavnik.pdf_preuzmi")

    # Gumb za preuzimanje ostaje i nakon druge interakcije sa stranicom.
    at = at.run()
    assert at.get("download_button")


def test_pdf_neuspjelo_pisanje_prikazuje_poruku(podaci, aplikacija, monkeypatch):
    spremi(_popis_za_pdf(), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _samoprovjera(at)

    def pukni(*_args):
        raise OSError("disk pun")

    monkeypatch.setattr(pdf_svojstva, "zapisi_atomski", pukni)
    at = at.button(key="generiraj_pdf").click().run()
    assert not at.exception
    assert [e.value for e in at.error] == [poruka("nastavnik.pdf_zapis_neuspio")]
    assert not (_mapa_vjezbe(podaci) / "izdano.json").exists()
    assert not at.get("download_button")


def _generiran_pdf(podaci: Path, aplikacija: AppTest) -> AppTest:
    spremi(_popis_za_pdf(), _popis_csv(podaci))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    at = _samoprovjera(at)
    at = at.button(key="generiraj_pdf").click().run()
    assert not at.exception
    assert at.get("download_button")
    return at


def test_pdf_neuspjelo_pisanje_izdanog_cuva_prethodni_par(podaci, aplikacija, monkeypatch):
    at = _generiran_pdf(podaci, aplikacija)
    mapa = _mapa_vjezbe(podaci)
    pdf_prije = (mapa / "svojstva_vjezba_1.pdf").read_bytes()
    izdano_prije = (mapa / "izdano.json").read_bytes()

    def pukni(*_args):
        raise OSError("disk pun")

    monkeypatch.setattr(popis_modul, "zapisi_atomski", pukni)
    at = at.button(key="generiraj_pdf").click().run()
    assert not at.exception
    assert [e.value for e in at.error] == [poruka("nastavnik.pdf_zapis_neuspio")]
    assert (mapa / "svojstva_vjezba_1.pdf").read_bytes() == pdf_prije
    assert (mapa / "izdano.json").read_bytes() == izdano_prije
    assert not at.get("download_button")


def test_pdf_neuspjelo_pisanje_pdf_vraca_prethodni_izdano(podaci, aplikacija, monkeypatch):
    at = _generiran_pdf(podaci, aplikacija)
    mapa = _mapa_vjezbe(podaci)
    pdf_prije = (mapa / "svojstva_vjezba_1.pdf").read_bytes()
    izdano_prije = (mapa / "izdano.json").read_bytes()

    def pukni(*_args):
        raise OSError("disk pun")

    monkeypatch.setattr(pdf_svojstva, "zapisi_atomski", pukni)
    at = at.button(key="generiraj_pdf").click().run()
    assert [e.value for e in at.error] == [poruka("nastavnik.pdf_zapis_neuspio")]
    assert (mapa / "svojstva_vjezba_1.pdf").read_bytes() == pdf_prije
    assert (mapa / "izdano.json").read_bytes() == izdano_prije
    assert not at.get("download_button")


def test_pdf_promjena_popisa_skriva_preuzimanje(podaci, aplikacija):
    at = _generiran_pdf(podaci, aplikacija)
    spremi(_popis_za_pdf()[:4], _popis_csv(podaci))
    at = at.run()
    assert not at.exception
    assert not at.get("download_button")


def test_pdf_druga_podatkovna_mapa_skriva_preuzimanje(podaci, aplikacija, tmp_path):
    at = _generiran_pdf(podaci, aplikacija)
    druga = tmp_path / "Druga"
    spremi(_popis_za_pdf(), _popis_csv(druga))
    at = at.text_input(key="podatkovna_mapa").input(str(druga)).run()
    assert not at.exception
    assert not at.button(key="generiraj_pdf").disabled
    assert not at.get("download_button")


def test_pdf_prikazuje_poveznicu(u_mapi):
    vjezba = profil.ucitaj(VJEZBA_1.read_bytes())
    assert vjezba.vjezba.poveznica in [c.value for c in u_mapi.code]
    assert poruka("nastavnik.pdf_poveznica") in [c.value for c in u_mapi.caption]


def test_pdf_prikazuje_zadnje_izdano(podaci, aplikacija):
    at = _generiran_pdf(podaci, aplikacija)
    izdano = procitaj_izdano(_mapa_vjezbe(podaci))
    ocekivano = poruka(
        "nastavnik.pdf_izdano",
        vrijeme=izdano.vrijeme.strftime("%d.%m.%Y. %H:%M"),
        verzija=izdano.profil_verzija,
    )
    assert ocekivano in [c.value for c in at.caption]
    assert poruka("nastavnik.pdf_izdano_razlika") not in [w.value for w in at.warning]


def test_pdf_izdano_za_drugi_profil_upozorava(podaci, aplikacija):
    drugi = profil.ucitaj(
        _zamijeni(VJEZBA_1.read_bytes(), b"sjeme = 20261012", b"sjeme = 1")
    )
    zapisi_izdano(_mapa_vjezbe(podaci), drugi, datetime(2026, 10, 1, 9, 5, tzinfo=ZONA))
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert poruka("nastavnik.pdf_izdano_razlika") in [w.value for w in at.warning]
    assert poruka(
        "nastavnik.pdf_izdano", vrijeme="01.10.2026. 09:05", verzija=profil.verzija(drugi)
    ) in [c.value for c in at.caption]


def test_pdf_ostecen_izdano_prikazuje_gresku(podaci, aplikacija):
    _mapa_vjezbe(podaci).mkdir(parents=True)
    (_mapa_vjezbe(podaci) / "izdano.json").write_bytes(b"{")
    at = aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()
    assert not at.exception
    assert [e.value for e in at.error] == [poruka("popis.izdano_necitljivo")]


# --- Batch provjera (priča 4.1) -------------------------------------------------


def _batch_popis() -> tuple[Student, ...]:
    return tuple(
        Student(rbr=r, jmbag=f"{9900000000 + r}", ime="Ana", prezime=p, aktivan=True)
        for r, p in ((1, "Horvat"), (2, "Kovač"))
    )


def _predaje(tmp_path: Path, vjezba: profil.Profil) -> Path:
    from alati.generator import ispravan

    from provjera.jezgra import naziv

    mapa = tmp_path / "predaje"
    mapa.mkdir()
    for s in _batch_popis():
        (mapa / naziv.kanonski(s.ime, s.prezime, vjezba)).write_bytes(ispravan(s.rbr, vjezba))
    (mapa / "~$privremena.docx").write_bytes(b"x")
    return mapa


def _batch_aplikacija(aplikacija: AppTest, podaci: Path, izdano: bool = True) -> AppTest:
    vjezba = profil.ucitaj(VJEZBA_1.read_bytes())
    spremi(_batch_popis(), _popis_csv(podaci))
    if izdano:
        zapisi_izdano(_mapa_vjezbe(podaci), vjezba, datetime(2026, 10, 1, 12, 0, tzinfo=ZONA))
    return aplikacija.text_input(key="podatkovna_mapa").input(str(podaci)).run()


def test_batch_bez_popisa_nije_moguc(u_mapi):
    assert poruka("batch.naslov") in [s.value for s in u_mapi.subheader]
    assert poruka("batch.nije_moguce", broj=1) in [c.value for c in u_mapi.caption]
    assert not u_mapi.get("button") or all(b.key != "pokreni_batch" for b in u_mapi.button)


def test_batch_bez_mape_gumb_onemogucen(podaci, aplikacija):
    at = _batch_aplikacija(aplikacija, podaci)
    assert not at.exception
    assert at.button(key="pokreni_batch").disabled
    assert poruka("batch.mapa_prazna") in [c.value for c in at.caption]


def test_batch_neispravna_mapa(podaci, aplikacija, tmp_path):
    at = _batch_aplikacija(aplikacija, podaci)
    at = at.text_input(key="mapa_predaja").input(str(tmp_path / "nema")).run()
    assert poruka("batch.mapa_neispravna") in [e.value for e in at.error]
    assert at.button(key="pokreni_batch").disabled


def test_batch_sretan_put(podaci, aplikacija, tmp_path):
    at = _batch_aplikacija(aplikacija, podaci)
    mapa = _predaje(tmp_path, profil.ucitaj(VJEZBA_1.read_bytes()))
    at = at.text_input(key="mapa_predaja").input(str(mapa)).run()
    assert not [w for w in at.warning if w.value.startswith("Margine")]
    gumb = at.button(key="pokreni_batch")
    assert gumb.label == "Pokreni batch provjeru" and not gumb.disabled
    at = gumb.click().run()
    assert not at.exception
    assert poruka("batch.gotovo", broj=2) in [s.value for s in at.success]
    tablica = at.dataframe[-1].value
    assert list(tablica[poruka("batch.stupac_status")]) == ["✅ spremno"] * 2
    assert list(tablica[poruka("batch.stupac_student")]) == ["1. Ana Horvat", "2. Ana Kovač"]


@pytest.mark.parametrize("izdano", ["nema", "drugi", "smece"])
def test_batch_otisak_trazi_potvrdu(podaci, aplikacija, tmp_path, izdano):
    at = _batch_aplikacija(aplikacija, podaci, izdano=izdano != "nema")
    if izdano == "smece":
        (_mapa_vjezbe(podaci) / "izdano.json").write_bytes(b"{")
    if izdano == "drugi":
        putanja = _mapa_vjezbe(podaci) / "izdano.json"
        podaci_izdanog = json.loads(putanja.read_text(encoding="utf-8"))
        podaci_izdanog["formula_otisak"] = "000000000000"
        putanja.write_text(json.dumps(podaci_izdanog), encoding="utf-8")
    mapa = _predaje(tmp_path, profil.ucitaj(VJEZBA_1.read_bytes()))
    at = at.text_input(key="mapa_predaja").input(str(mapa)).run()
    kljuc = {"nema": "batch.otisak_NEMA_IZDANOG", "drugi": "batch.otisak_RAZLICIT",
             "smece": "batch.otisak_NECITLJIVO"}[izdano]
    assert poruka(kljuc) in [w.value for w in at.warning]
    assert at.button(key="pokreni_batch").disabled
    at = at.checkbox[0].check().run()
    assert not at.button(key="pokreni_batch").disabled
    at = at.button(key="pokreni_batch").click().run()
    assert poruka("batch.gotovo", broj=2) in [s.value for s in at.success]


def _pokrenut_batch(aplikacija: AppTest, podaci: Path, mapa: Path) -> AppTest:
    at = _batch_aplikacija(aplikacija, podaci)
    at = at.text_input(key="mapa_predaja").input(str(mapa)).run()
    return at.button(key="pokreni_batch").click().run()


def test_batch_preskace_podatkovnu_mapu_unutar_predaja(aplikacija, tmp_path):
    mapa = _predaje(tmp_path, profil.ucitaj(VJEZBA_1.read_bytes()))
    podaci = mapa / "ProvjeraWord"
    (podaci / "vjezba_2").mkdir(parents=True)
    (podaci / "vjezba_2" / "rad.docx").write_bytes(b"x")
    at = _pokrenut_batch(aplikacija, podaci, mapa)
    assert not at.exception
    assert poruka("batch.gotovo", broj=2) in [s.value for s in at.success]
    assert all("ProvjeraWord" not in d for d in at.dataframe[-1].value[poruka("batch.stupac_datoteka")])


@pytest.mark.parametrize("unutra", ["", "vjezba_1"])
def test_batch_odbija_mapu_u_podatkovnoj_mapi(podaci, aplikacija, unutra):
    at = _batch_aplikacija(aplikacija, podaci)
    at = at.text_input(key="mapa_predaja").input(str(podaci / unutra)).run()
    assert poruka("batch.mapa_u_podacima") in [e.value for e in at.error]
    assert at.button(key="pokreni_batch").disabled


def test_batch_rezultat_nestaje_kad_se_promijeni_popis_ili_mapa(podaci, aplikacija, tmp_path):
    mapa = _predaje(tmp_path, profil.ucitaj(VJEZBA_1.read_bytes()))
    at = _pokrenut_batch(aplikacija, podaci, mapa)
    assert poruka("batch.gotovo", broj=2) in [s.value for s in at.success]
    druga = tmp_path / "druga"
    druga.mkdir()
    at = at.text_input(key="mapa_predaja").input(str(druga)).run()
    assert poruka("batch.gotovo", broj=2) not in [s.value for s in at.success]
    at = at.text_input(key="mapa_predaja").input(str(mapa)).run()
    assert poruka("batch.gotovo", broj=2) in [s.value for s in at.success]
    spremi(_batch_popis()[:1], _popis_csv(podaci))
    at = at.run()
    assert poruka("batch.gotovo", broj=2) not in [s.value for s in at.success]


def test_batch_necitljiva_mapa_prikazuje_gresku(podaci, aplikacija, tmp_path, monkeypatch):
    from provjera.adapteri import batch

    mapa = _predaje(tmp_path, profil.ucitaj(VJEZBA_1.read_bytes()))

    def necitljivo(*_a, **_k):
        raise PermissionError(13, "Pristup odbijen")

    monkeypatch.setattr(batch, "pronadi_datoteke", necitljivo)
    at = _pokrenut_batch(aplikacija, podaci, mapa)
    assert not at.exception
    assert poruka("batch.mapa_necitljiva", razlog="Pristup odbijen") in [e.value for e in at.error]

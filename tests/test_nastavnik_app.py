"""Nastavnička aplikacija (priča 3.1): podatkovna mapa, odabir vježbe, učitavanje ISVU popisa."""

import sys
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
from streamlit.testing.v1 import AppTest

from provjera.adapteri import popis as popis_modul
from provjera.adapteri.popis import Student, procitaj_zamrznuti, spremi, ucitaj_isvu, zamrzni
from provjera.jezgra import profil
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

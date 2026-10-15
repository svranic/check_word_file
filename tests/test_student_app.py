import logging
import re
from pathlib import Path

import pytest
from alati.generator import ispravan
from streamlit.runtime.uploaded_file_manager import UploadedFile
from streamlit.testing.v1 import AppTest

from provjera.jezgra import formula, profil
from provjera.jezgra.nalaz import (
    Dio,
    Izvjestaj,
    Izvor,
    Lokacija,
    Nalaz,
    Status,
    Vrijednost,
    VrstaIzvora,
)
from provjera.jezgra.ulaz import RazlogOdbijanja
from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.poruke import formatiraj, poruka

KORIJEN = Path(__file__).resolve().parents[1]
STUDENT = str(KORIJEN / "apps" / "student.py")
ISPRAVAN_NAZIV = "Lucija_Šimek_GiG_OG_Vjezba_1.docx"


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
    at.session_state["greska_provjere"] = "izvjestaj.greska"
    at = _posalji(at, "55")
    assert "izvjestaj" not in at.session_state
    assert "greska_provjere" not in at.session_state


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


# --- Učitavanje dokumenta (priča 1.3) ----------------------------------------


def _docx() -> bytes:
    """Ispravan sintetski rad za Rbr. 54 (naslovnica + tijelo, A4)."""
    return ispravan(54, profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes()))


def _ucitaj(at: AppTest, naziv: str, sadrzaj: bytes) -> AppTest:
    at.file_uploader[0].set_value((naziv, sadrzaj, "application/octet-stream"))
    return at.run()


def test_polje_za_ucitavanje_tek_uz_valjan_rbr(aplikacija):
    assert not aplikacija.file_uploader
    assert _posalji(aplikacija, "54").file_uploader


def test_ispravan_docx_i_naziv_su_spremni(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), ISPRAVAN_NAZIV, _docx())
    assert not at.exception
    assert [(s.value, s.icon) for s in at.success] == [(poruka("izvjestaj.spremno"), "✅")]
    assert not at.error


@pytest.mark.parametrize(
    ("naziv", "sadrzaj", "kljuc"),
    [
        ("rad.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64, "ulaz.stari_doc"),
        ("rad.pdf", b"%PDF-1.7", "ulaz.neispravan_format"),
        ("rad.docx", b"PK\x03\x04skraceno", "ulaz.ostecena"),
    ],
)
def test_neprihvatljiva_datoteka_daje_poruku(aplikacija, naziv, sadrzaj, kljuc):
    at = _ucitaj(_posalji(aplikacija, "54"), naziv, sadrzaj)
    assert not at.exception
    assert [e.value for e in at.error] == [poruka(kljuc, mb=0)]
    assert at.file_uploader  # stranica ostaje upotrebljiva


def test_poruka_za_format_sadrzi_uputu_spremi_kao(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "rad.pdf", b"%PDF-1.7")
    assert "Spremi kao (Save As) → Word dokument (.docx)" in at.error[0].value


def test_bajtovi_ne_ostaju_u_stanju_ni_u_logovima(aplikacija, caplog):
    caplog.set_level(logging.DEBUG)
    naziv = "Tajna_Studentica_GiG_OG_Vjezba_1.docx"
    at = _ucitaj(_posalji(aplikacija, "54"), naziv, _docx())
    for kljuc, vrijednost in at.session_state.to_dict().items():
        assert not isinstance(vrijednost, (bytes, bytearray, UploadedFile)), kljuc
        assert not (isinstance(vrijednost, list) and vrijednost), kljuc
    assert naziv not in caplog.text
    assert "Tajna" not in caplog.text


def test_promjena_rbr_brise_rezultat_ucitavanja(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), ISPRAVAN_NAZIV, _docx())
    assert at.success
    at = _posalji(at, "55")
    assert "izvjestaj" not in at.session_state
    assert not at.success


@pytest.mark.parametrize(("razlog", "mb"), [("prevelika", 10), ("zip_bomba", 100)])
def test_poruka_velicine_navodi_granicu(aplikacija, razlog, mb):
    at = _posalji(aplikacija, "54")
    at.session_state["izvjestaj"] = Izvjestaj(RazlogOdbijanja(razlog), (), "abcd1234", 54)
    at = at.run()
    assert [e.value for e in at.error] == [poruka(f"ulaz.{razlog}", mb=mb)]
    assert f"{mb} MB" in at.error[0].value


def test_stari_doc_upucuje_na_spremi_kao(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "rad.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    assert "Spremi kao (Save As) → Word dokument (.docx)" in at.error[0].value


def test_polje_dopusta_vecu_datoteku_od_granice_jezgre(aplikacija):
    # Streamlit ne smije odbiti datoteku prije jezgre, inače student vidi englesku poruku.
    at = _posalji(aplikacija, "54")
    assert at.file_uploader[0].proto.max_upload_size_mb > 10


# --- Izvještaj (priča 1.4) ---------------------------------------------------


def _n(status, pravilo="R-NAZIV", izvor=None, pojave=1):
    return Nalaz(
        pravilo, status, Lokacija(Dio.NAZIV), "R-NAZIV.ne_odgovara_obrascu",
        ocekivano=Vrijednost("Ime_Prezime_GiG_OG_Vjezba_1.docx", Jedinica.TEKST),
        pronadeno=Vrijednost("moj_rad.docx", Jedinica.TEKST), izvor=izvor, pojave=pojave,
    )


def test_redoslijed_grupa_i_status_tekstom(aplikacija):
    at = _posalji(aplikacija, "54")
    nalazi = (_n(Status.PROSLO), _n(Status.NEPROVJERLJIVO), _n(Status.NE_PROLAZI, pojave=3))
    at.session_state["izvjestaj"] = Izvjestaj(None, nalazi, "abcd1234", 54)
    at = at.run()
    assert [(e.value, e.icon) for e in at.error] == [(poruka("izvjestaj.nije_spremno"), "❌")]
    assert [h.value for h in at.subheader][-3:] == [
        poruka("izvjestaj.grupa.NE_PROLAZI"),
        poruka("izvjestaj.grupa.NEPROVJERLJIVO"),
        poruka("izvjestaj.grupa.PROSLO"),
    ]
    redci_statusa = [m.value for m in at.markdown if m.value.startswith("**")]
    assert [r.split("**")[1] for r in redci_statusa] == [
        poruka("status.NE_PROLAZI"), poruka("status.NEPROVJERLJIVO"), poruka("status.PROSLO"),
    ]
    natpisi = [c.value for c in at.caption]
    assert any("Očekivano" in c and "Ime" in c for c in natpisi)
    assert any("Pronađeno" in c for c in natpisi)
    assert poruka("izvjestaj.pojave", pojave=3) in natpisi
    assert poruka("izvjestaj.verzija_profila", verzija="abcd1234") in natpisi


def test_primjeri_lokacija_uz_broj_pojava(aplikacija):
    at = _posalji(aplikacija, "54")
    primjeri = tuple(Lokacija(Dio.TIJELO, sekcija=2, odlomak=i, isjecak=f"Odlomak_{i}") for i in (3, 7, 9))
    nalaz = Nalaz(
        "R-NAZIV", Status.NE_PROLAZI, primjeri[0], "R-NAZIV.ne_odgovara_obrascu",
        ocekivano=Vrijednost("Ime_Prezime_GiG_OG_Vjezba_1.docx", Jedinica.TEKST),
        pronadeno=Vrijednost("moj_rad.docx", Jedinica.TEKST), pojave=40, primjeri=primjeri,
    )
    at.session_state["izvjestaj"] = Izvjestaj(None, (nalaz,), "abcd1234", 54)
    at = at.run()
    natpisi = [c.value for c in at.caption]
    assert poruka("izvjestaj.pojave", pojave=40) in natpisi
    [redak] = [c for c in natpisi if c.startswith("Primjeri")]
    tekst = redak.replace("\\", "")
    assert all(f"odlomak {i}: „Odlomak_{i}…“" in tekst for i in (3, 7, 9))
    assert tekst.endswith("; …")


def _primjeri(at: AppTest, pojave: int, odlomci: tuple[int, ...]) -> list[str]:
    primjeri = tuple(Lokacija(Dio.TIJELO, sekcija=2, odlomak=i) for i in odlomci)
    nalaz = Nalaz(
        "R-NAZIV", Status.NE_PROLAZI, primjeri[0] if primjeri else Lokacija(Dio.NAZIV),
        "R-NAZIV.ne_odgovara_obrascu",
        ocekivano=Vrijednost("Ime_Prezime_GiG_OG_Vjezba_1.docx", Jedinica.TEKST),
        pronadeno=Vrijednost("moj_rad.docx", Jedinica.TEKST), pojave=pojave, primjeri=primjeri,
    )
    at.session_state["izvjestaj"] = Izvjestaj(None, (nalaz,), "abcd1234", 54)
    at = at.run()
    return [c.value.replace("\\", "") for c in at.caption if c.value.startswith("Primjeri")]


def test_svi_primjeri_bez_tri_tocke(aplikacija):
    [redak] = _primjeri(_posalji(aplikacija, "54"), 2, (3, 7))
    assert "odlomak 3" in redak and "odlomak 7" in redak and "…" not in redak


@pytest.mark.parametrize(("pojave", "odlomci"), [(1, ()), (2, (3,)), (2, (3, 3))])
def test_manje_od_dva_razlicita_primjera_se_ne_prikazuje(aplikacija, pojave, odlomci):
    assert not _primjeri(_posalji(aplikacija, "54"), pojave, odlomci)


def test_tehnicki_detalji_u_prosirivom_dijelu(aplikacija):
    at = _posalji(aplikacija, "54")
    nalaz = _n(Status.NE_PROLAZI, izvor=Izvor(VrstaIzvora.STIL, "Normal"))
    at.session_state["izvjestaj"] = Izvjestaj(None, (nalaz,), "abcd1234", 54)
    at = at.run()
    [prosirivi] = at.expander
    assert prosirivi.label == poruka("izvjestaj.tehnicki_detalji")
    assert "Normal" in prosirivi.markdown[0].value


def test_neispravan_naziv_prikazuje_obrazac(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "moj rad.docx", _docx())
    assert [e.value for e in at.error] == [poruka("izvjestaj.nije_spremno")]
    tekst = " ".join(m.value for m in at.markdown).replace("\\", "")
    assert "Ime_Prezime_GiG_OG_Vjezba_1.docx" in tekst


@pytest.mark.parametrize(("iznimka", "kljuc"), [(MemoryError, "izvjestaj.preopterecenje"), (RuntimeError, "izvjestaj.greska")])
def test_preopterecenje_ne_rusi_stranicu(monkeypatch, iznimka, kljuc):
    def baca(*_):
        raise iznimka()

    monkeypatch.setattr("provjera.jezgra.provjera.provjeri", baca)
    at = _ucitaj(_posalji(AppTest.from_file(STUDENT).run(), "54"), ISPRAVAN_NAZIV, _docx())
    assert not at.exception
    assert [e.value for e in at.error] == [poruka(kljuc)]
    assert at.file_uploader


def test_naziv_s_markdown_znakovima_je_escapiran(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "moj__rad*1*.docx", _docx())
    izvorni = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert any(r"moj\_\_rad\*1\*\.docx" in t for t in izvorni)
    assert not any("moj__rad*1*" in t for t in izvorni)


def test_uspjesno_ponovno_ucitavanje_brise_staru_gresku(monkeypatch):
    from provjera.jezgra import provjera as modul

    pravi = modul.provjeri

    def baca(*_):
        raise MemoryError

    monkeypatch.setattr(modul, "provjeri", baca)
    at = _ucitaj(_posalji(AppTest.from_file(STUDENT).run(), "54"), ISPRAVAN_NAZIV, _docx())
    assert [e.value for e in at.error] == [poruka("izvjestaj.preopterecenje")]
    monkeypatch.setattr(modul, "provjeri", pravi)
    at = _ucitaj(at, ISPRAVAN_NAZIV, _docx())
    assert not at.error
    assert [s.value for s in at.success] == [poruka("izvjestaj.spremno")]


# --- Sažetak (priča 1.6) -----------------------------------------------------


def test_gumb_za_sazetak_uz_izvjestaj(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), ISPRAVAN_NAZIV, _docx())
    [gumb] = at.get("download_button")
    assert gumb.proto.label == poruka("sazetak.preuzmi")
    assert re.fullmatch(r"\d\d\.\d\d\.\d{4}\. \d\d:\d\d", at.session_state["vrijeme_provjere"])


def test_nema_sazetka_za_odbijenu_datoteku(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "rad.pdf", b"%PDF-1.7")
    assert at.get("download_button") == []


def test_promjena_rbr_brise_vrijeme_provjere(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), ISPRAVAN_NAZIV, _docx())
    at = _posalji(at, "55")
    assert "vrijeme_provjere" not in at.session_state
    assert at.get("download_button") == []


def test_sazetak_dobiva_vjezbu_i_vrijeme_provjere(monkeypatch):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from provjera.jezgra import sazetak

    pozivi = []
    pravi = sazetak.html_sazetka

    def spijun(izvjestaj, naziv_vjezbe, vrijeme):
        pozivi.append((izvjestaj, naziv_vjezbe, vrijeme))
        return pravi(izvjestaj, naziv_vjezbe, vrijeme)

    monkeypatch.setattr(sazetak, "html_sazetka", spijun)
    at = _ucitaj(_posalji(AppTest.from_file(STUDENT).run(), "54"), ISPRAVAN_NAZIV, _docx())
    izvjestaj, naziv_vjezbe, vrijeme = pozivi[-1]
    assert naziv_vjezbe == "Vježba 1"
    assert vrijeme == at.session_state["vrijeme_provjere"]
    sada = datetime.now(ZoneInfo("Europe/Zagreb"))
    assert vrijeme in {(sada - timedelta(minutes=m)).strftime("%d.%m.%Y. %H:%M") for m in (0, 1)}
    assert ISPRAVAN_NAZIV not in pravi(izvjestaj, naziv_vjezbe, vrijeme)
    assert poruka("sazetak.datoteka", rbr=54) == "sazetak_provjere_rbr_54.html"


def test_gumb_za_sazetak_i_za_nespreman_rad(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "pogresan naziv.docx", _docx())
    assert [e.value for e in at.error] == [poruka("izvjestaj.nije_spremno")]
    assert len(at.get("download_button")) == 1


def test_greska_sazetka_ne_prikazuje_gresku_provjere(monkeypatch):
    from provjera.jezgra import sazetak

    def baca(*_):
        raise ValueError

    monkeypatch.setattr(sazetak, "html_sazetka", baca)
    at = _ucitaj(_posalji(AppTest.from_file(STUDENT).run(), "54"), ISPRAVAN_NAZIV, _docx())
    assert not at.error
    assert at.success
    assert at.get("download_button") == []


def test_margine_i_naziv_dolaze_iz_odabrane_vjezbe(monkeypatch):
    p = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
    druga = p.model_copy(
        update={
            "vjezba": p.vjezba.model_copy(update={"id": "vjezba_2", "naziv": "Vježba 2"}),
            "formula": p.formula.model_copy(update={"sjeme": 12345}),
            "naziv_datoteke": p.naziv_datoteke.model_copy(update={"sufiks": "_GiG_OG_Vjezba_2"}),
        }
    )
    assert formula.margine(54, druga.formula) != formula.margine(54, p.formula)
    monkeypatch.setattr(profil, "objavljeni", lambda _sadrzaji: ([p, druga], 0))
    at = _posalji(AppTest.from_file(STUDENT).run(), "54")
    at = at.selectbox(key="vjezba").select("vjezba_2").run()
    at = _posalji(at, "54")
    ocekivane = formula.margine(54, druga.formula).u_twips()
    assert [m.value for m in at.metric] == [
        formatiraj(ocekivane[s], Jedinica.TWIPS) for s in ("gore", "dolje", "lijevo", "desno")
    ]
    assert "_GiG_OG_Vjezba_2" in " ".join(m.value for m in at.markdown)


def test_necitljiv_profil_ne_rusi_stranicu(monkeypatch):
    from pathlib import Path

    pravi = Path.read_bytes

    def citaj(self):
        if self.suffix == ".toml":
            raise PermissionError("zaključano")
        return pravi(self)

    monkeypatch.setattr(Path, "read_bytes", citaj)
    at = AppTest.from_file(STUDENT).run()
    assert not at.exception
    assert [w.value for w in at.warning] == [poruka("profil.nedostupno")]


def test_gumb_za_sazetak_salje_html_s_nazivom_i_vrstom(monkeypatch, aplikacija):
    import streamlit

    pozivi = []
    pravi = streamlit.download_button

    def spijun(*a, **k):
        pozivi.append(k)
        return pravi(*a, **k)

    monkeypatch.setattr(streamlit, "download_button", spijun)
    at = _posalji(aplikacija, "54")
    datoteka = ispravan(54, profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes()))
    at = _ucitaj(at, "Ana_Horvat_GiG_OG_Vjezba_1.docx", datoteka)
    assert pozivi, "gumb za sažetak nije prikazan"
    poziv = pozivi[-1]
    assert poziv["file_name"] == "sazetak_provjere_rbr_54.html"
    assert poziv["mime"] == "text/html"
    assert poziv["data"].decode("utf-8").lstrip().lower().startswith("<!doctype html>")

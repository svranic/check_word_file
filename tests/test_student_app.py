import io
import logging
from pathlib import Path

import docx
import pytest
from streamlit.runtime.uploaded_file_manager import UploadedFile
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
    at.session_state["rezultat_ulaza"] = "prihvaceno"
    at = _posalji(at, "55")
    assert "izvjestaj" not in at.session_state
    assert "rezultat_ulaza" not in at.session_state


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
    spremnik = io.BytesIO()
    docx.Document().save(spremnik)
    return spremnik.getvalue()


def _ucitaj(at: AppTest, naziv: str, sadrzaj: bytes) -> AppTest:
    at.file_uploader[0].set_value((naziv, sadrzaj, "application/octet-stream"))
    return at.run()


def test_polje_za_ucitavanje_tek_uz_valjan_rbr(aplikacija):
    assert not aplikacija.file_uploader
    assert _posalji(aplikacija, "54").file_uploader


def test_ispravan_docx_je_prihvacen(aplikacija):
    at = _ucitaj(_posalji(aplikacija, "54"), "Rad.DOCX", _docx())
    assert not at.exception
    assert [s.value for s in at.success] == [poruka("ulaz.prihvaceno")]
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
    at = _ucitaj(_posalji(aplikacija, "54"), "Rad.docx", _docx())
    assert at.success
    at = _posalji(at, "55")
    assert "rezultat_ulaza" not in at.session_state
    assert not at.success


@pytest.mark.parametrize(("razlog", "mb"), [("prevelika", 10), ("zip_bomba", 100)])
def test_poruka_velicine_navodi_granicu(aplikacija, razlog, mb):
    at = _posalji(aplikacija, "54")
    at.session_state["rezultat_ulaza"] = razlog
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

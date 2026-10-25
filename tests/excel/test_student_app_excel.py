"""Excel vježba u studentskoj aplikaciji: isti link, odabir vježbe u izborniku."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from provjera.excel.adapteri.predlozak import StudentPredloska, izradi
from provjera.excel.jezgra import profil as profil_modul
from provjera.word.jezgra.poruke import poruka

KORIJEN = Path(__file__).resolve().parents[2]
PROFIL = profil_modul.ucitaj((KORIJEN / "profili" / "excel" / "vjezba_2.toml").read_bytes())
ANA = StudentPredloska("Ana", "Horvat", "0036000001")
NAZIV = "Ana_Horvat_GiG_OG_Vjezba_2.xlsx"


@pytest.fixture
def aplikacija(tmp_path) -> AppTest:
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "student.py").write_bytes((KORIJEN / "apps" / "student.py").read_bytes())
    for vrsta, izvor in (("word", KORIJEN / "tests" / "word" / "fixtures" / "vjezba_1_baseline.toml"),
                         ("excel", KORIJEN / "profili" / "excel" / "vjezba_2.toml")):
        (tmp_path / "profili" / vrsta).mkdir(parents=True)
        (tmp_path / "profili" / vrsta / izvor.name).write_bytes(izvor.read_bytes())
    at = AppTest.from_file(str(tmp_path / "apps" / "student.py")).run()
    return at.selectbox(key="vjezba").select("excel:vjezba_2").run()


def _ucitaj(at: AppTest, naziv: str, sadrzaj: bytes) -> AppTest:
    at.file_uploader[0].set_value((naziv, sadrzaj, "application/octet-stream"))
    return at.run()


def test_izbornik_nudi_word_i_excel_vjezbe(aplikacija):
    assert not aplikacija.exception
    assert aplikacija.selectbox(key="vjezba").options == ["Vježba 1", PROFIL.vjezba.naziv]
    assert aplikacija.file_uploader[0].label == poruka("excel.oznaka")
    assert not aplikacija.text_input  # Excel vježba ne traži Rbr.


def test_rijeseni_predlozak_je_spreman(aplikacija):
    at = _ucitaj(aplikacija, NAZIV, izradi(PROFIL, ANA, rjesenje=True))
    assert not at.exception
    assert [s.value for s in at.success] == [poruka("excel.spremno")]


def test_prazan_predlozak_nije_spreman(aplikacija):
    at = _ucitaj(aplikacija, NAZIV, izradi(PROFIL, ANA))
    assert [e.value for e in at.error] == [poruka("excel.nije_spremno")]
    assert any("Ćelija je prazna" in m.value for m in at.markdown)


def test_word_dokument_odbija_excel_porukom(aplikacija):
    at = _ucitaj(aplikacija, "rad.docx", b"PK\x03\x04")
    assert [e.value for e in at.error] == [poruka("excel.ulaz.neispravan_format")]

"""Čuvari arhitekture: čista jezgra (AD-1), privatnost repozitorija (AD-2), katalog poruka (AD-11)."""

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from provjera.jezgra.poruke import KATALOG, poruka

KORIJEN = Path(__file__).resolve().parents[1]
JEZGRA = KORIJEN / "provjera" / "jezgra"
APPS = KORIJEN / "apps"

ZABRANJENI_UVOZI_JEZGRE = {
    "streamlit",
    "openpyxl",
    "fpdf",
    "time",
    "logging.config",
    "logging.basicConfig",
    "provjera.adapteri",
}
ZABRANJENI_POZIVI_SATA = {"now", "utcnow", "today"}
ZABRANJENI_MODULI_STUDENTA = ("provjera.adapteri", "openpyxl", "fpdf")
OSOBNI_NASTAVCI = (".xlsx", ".xls", ".xlsm", ".csv", ".docx", ".doc", ".pdf")


# --- AD-1: jezgra ne uvozi zabranjeno i ne čita sat -------------------------


def _zabranjen(modul: str) -> bool:
    return any(
        modul == z or modul.startswith(z + ".") for z in ZABRANJENI_UVOZI_JEZGRE
    )


def _apsolutni_modul(cvor: ast.ImportFrom, paket: str) -> str:
    """Razrješava relativni uvoz (``from ..x import y``) u apsolutno ime modula."""
    if cvor.level == 0:
        return cvor.module or ""
    dijelovi = paket.split(".")[: len(paket.split(".")) - (cvor.level - 1)]
    return ".".join(dijelovi + ([cvor.module] if cvor.module else []))


def prekrsaji_jezgre(
    izvor: str, naziv: str, paket: str = "provjera.jezgra"
) -> list[str]:
    """Vraća popis kršenja AD-1 u izvornom kodu jednog modula jezgre."""
    prekrsaji = []
    for cvor in ast.walk(ast.parse(izvor, filename=naziv)):
        if isinstance(cvor, ast.Import):
            moduli = [a.name for a in cvor.names]
        elif isinstance(cvor, ast.ImportFrom):
            modul = _apsolutni_modul(cvor, paket)
            moduli = [modul] + [f"{modul}.{a.name}" for a in cvor.names]
        else:
            moduli = []
        for modul in moduli:
            if _zabranjen(modul):
                prekrsaji.append(f"{naziv}:{cvor.lineno}: uvoz {modul}")
                break
        if (
            isinstance(cvor, ast.Call)
            and isinstance(cvor.func, ast.Attribute)
            and cvor.func.attr in ZABRANJENI_POZIVI_SATA | {"basicConfig"}
        ):
            prekrsaji.append(f"{naziv}:{cvor.lineno}: poziv .{cvor.func.attr}()")
    return prekrsaji


def test_jezgra_ne_krsi_ad1():
    prekrsaji = []
    for datoteka in sorted(JEZGRA.rglob("*.py")):
        relativno = datoteka.relative_to(KORIJEN)
        paket = ".".join(relativno.parent.parts)  # i za __init__.py i za modul
        prekrsaji += prekrsaji_jezgre(
            datoteka.read_text(encoding="utf-8"), relativno.as_posix(), paket
        )
    assert prekrsaji == []


@pytest.mark.parametrize(
    "izvor",
    [
        "import streamlit as st",
        "import openpyxl",
        "from fpdf import FPDF",
        "import time",
        "from time import monotonic",
        "import logging.config",
        "from logging import config",
        "from datetime import datetime\nx = datetime.now()",
        "import datetime\nx = datetime.date.today()",
        "import datetime\nx = datetime.datetime.utcnow()",
        "import logging\nlogging.basicConfig()",
        "from logging import basicConfig",
        "from provjera.adapteri import popis",
        "from ..adapteri import popis",
        "from .. import adapteri",
    ],
)
def test_provjera_jezgre_hvata_prekrsaj(izvor):
    assert prekrsaji_jezgre(izvor, "primjer.py")


def test_provjera_jezgre_dopusta_cist_kod():
    izvor = "import logging\nfrom datetime import date\nlog = logging.getLogger(__name__)"
    assert prekrsaji_jezgre(izvor, "primjer.py") == []


# --- AD-2: studentska aplikacija ne povlači adaptere ni lokalne biblioteke ----


def ucitani_zabranjeni_moduli(skripta: Path) -> list[str]:
    """Izvodi skriptu u zasebnom procesu i vraća zabranjene module iz ``sys.modules``."""
    kod = (
        "import json, runpy, sys\n"
        f"runpy.run_path({str(skripta)!r}, run_name='__main__')\n"
        f"zabranjeni = {ZABRANJENI_MODULI_STUDENTA!r}\n"
        "print(json.dumps(sorted(m for m in sys.modules "
        "if any(m == z or m.startswith(z + '.') for z in zabranjeni))))\n"
    )
    # Radni direktorij izvan repozitorija: `provjera` se mora uvesti kao instalirani
    # paket, kao pod `streamlit run`, koji na sys.path stavlja apps/, a ne korijen.
    rezultat = subprocess.run(
        [sys.executable, "-c", kod],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert rezultat.returncode == 0, rezultat.stderr
    return json.loads(rezultat.stdout.strip().splitlines()[-1])


def test_student_ne_uvozi_zabranjene_module():
    assert ucitani_zabranjeni_moduli(APPS / "student.py") == []


def test_graf_uvoza_hvata_zabranjen_modul(tmp_path):
    skripta = tmp_path / "skripta.py"
    skripta.write_text("import openpyxl\n", encoding="utf-8")
    assert "openpyxl" in ucitani_zabranjeni_moduli(skripta)


def test_student_ne_koristi_predmemoriju():
    # AD-10: dokument ne smije završiti u st.cache_*.
    stablo = ast.parse((APPS / "student.py").read_text(encoding="utf-8"))
    nazivi = {c.attr for c in ast.walk(stablo) if isinstance(c, ast.Attribute)}
    nazivi |= {c.id for c in ast.walk(stablo) if isinstance(c, ast.Name)}
    assert nazivi.isdisjoint({"cache_data", "cache_resource", "cache", "experimental_memo"})


# --- AD-2: osobni podaci nisu u repozitoriju ---------------------------------


def nedopustene_putanje(putanje: list[str]) -> list[str]:
    """Putanje koje ne smiju biti u gitu: sve iz ``samples/`` i tablice/dokumenti izvan ``tests/``."""
    return [
        p
        for p in putanje
        if p.lower().startswith("samples/")
        or (p.lower().endswith(OSOBNI_NASTAVCI) and not p.startswith("tests/"))
    ]


def test_git_ne_sadrzi_osobne_podatke():
    provjera_repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=KORIJEN,
        capture_output=True,
        text=True,
    )
    assert provjera_repo.returncode == 0, (
        "Projekt nije git repozitorij; pokreni `git init -b main`."
    )
    # Praćene i nove neignorirane datoteke: hvata i ono što bi `git add .` dodao.
    izlaz = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=KORIJEN,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    putanje = [p for p in izlaz.split("\0") if p]
    assert nedopustene_putanje(putanje) == []


def test_provjera_putanja_hvata_osobne_podatke():
    putanje = [
        "samples/popis.txt",
        "Samples/rad.txt",
        "podaci/studenti.XLSX",
        "Rad.docx",
        "izvoz.csv",
        "stari.doc",
        "svojstva.pdf",
        "tests/fixtures/sintetski.xlsx",
        "apps/student.py",
    ]
    assert nedopustene_putanje(putanje) == [
        "samples/popis.txt",
        "Samples/rad.txt",
        "podaci/studenti.XLSX",
        "Rad.docx",
        "izvoz.csv",
        "stari.doc",
        "svojstva.pdf",
    ]


# --- AD-11: katalog poruka ---------------------------------------------------


def _kljucevi_iz_aplikacije(datoteka: Path) -> set[str]:
    stablo = ast.parse(datoteka.read_text(encoding="utf-8"))
    return {
        cvor.args[0].value
        for cvor in ast.walk(stablo)
        if isinstance(cvor, ast.Call)
        and isinstance(cvor.func, ast.Name)
        and cvor.func.id == "poruka"
        and cvor.args
        and isinstance(cvor.args[0], ast.Constant)
    }


@pytest.mark.parametrize("aplikacija", ["student.py", "nastavnik.py"])
def test_kljucevi_aplikacije_postoje_u_katalogu(aplikacija):
    kljucevi = _kljucevi_iz_aplikacije(APPS / aplikacija)
    assert kljucevi
    assert kljucevi - KATALOG.keys() == set()


def test_student_prikazuje_naslov_i_napomenu_o_privatnosti():
    at = AppTest.from_file(str(APPS / "student.py")).run()
    assert not at.exception
    assert at.title[0].value == poruka("app.naslov")
    assert poruka("privatnost.obrada") in [e.value for e in at.info]
    assert "SAD" in poruka("privatnost.obrada")


def test_nepoznat_kljuc_baca_keyerror():
    with pytest.raises(KeyError):
        poruka("nepostojeci.kljuc")

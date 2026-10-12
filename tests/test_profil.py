from pathlib import Path

import pytest

from provjera.jezgra import profil

PROFIL_VJEZBE_1 = Path(__file__).resolve().parents[1] / "profili" / "vjezba_1.toml"


def _vjezba_1() -> str:
    return PROFIL_VJEZBE_1.read_text(encoding="utf-8")


def test_ucitava_vjezbu_1_u_twipsima_i_mm():
    p = profil.ucitaj(PROFIL_VJEZBE_1.read_bytes())
    assert p.vjezba.objavljeno
    assert p.naziv_datoteke.obrazac == "Ime_Prezime_GiG_OG_Vjezba_1.docx"
    f = p.formula
    assert (f.osnovica_lijevo, f.osnovica_desno, f.osnovica_gore, f.osnovica_dolje) == (30, 25, 25, 25)
    assert (f.raspon, f.korak, f.naslovnica) == (5, 1, 25)
    assert p.tolerancije.margine == 17


def test_verzija_ne_ovisi_o_redoslijedu_ni_komentarima():
    izvorni = _vjezba_1()
    # Isti sadržaj: obrnut redoslijed odjeljaka i ključeva, drugi komentari.
    preuredeni = (
        "# drugi komentar\n"
        "[tolerancije]\nmargine = \"0,03 cm\"\n"
        "[formula]\nsjeme = 20261012\nnaslovnica = \"2,5 cm\"\nkorak = \"0,1 cm\"\n"
        "raspon = \"0,5 cm\"\nosnovica_desno = \"2,5 cm\"\nosnovica_lijevo = \"3 cm\"\n"
        "osnovica_dolje = \"2,5 cm\"\nosnovica_gore = \"2,5 cm\"\n"
        "[naziv_datoteke]\nnastavak = \".docx\"\nsufiks = \"_GiG_OG_Vjezba_1\"\n"
        "[vjezba]\nobjavljeno = true\nnaziv = \"Vježba 1\"\nid = \"vjezba_1\"\n"
    )
    a = profil.ucitaj(izvorni.encode("utf-8"))
    b = profil.ucitaj(preuredeni.encode("utf-8"))
    assert profil.verzija(a) == profil.verzija(b)
    assert len(profil.verzija(a)) == 8
    int(profil.verzija(a), 16)


def test_verzija_se_mijenja_s_vrijednoscu():
    a = profil.ucitaj(_vjezba_1().encode("utf-8"))
    b = profil.ucitaj(_vjezba_1().replace("20261012", "1").encode("utf-8"))
    assert profil.verzija(a) != profil.verzija(b)


def test_sve_greske_odjednom():
    tekst = (
        _vjezba_1()
        .replace('osnovica_gore = "2,5 cm"', 'osnovica_gore = "2,5 inch"')
        .replace('nastavak = ".docx"', 'nastavak = ".docx"\nnepoznato = 1')
        .replace("sjeme = 20261012", "sjeme = -1")
    )
    with pytest.raises(profil.GreskaProfila) as greska:
        profil.ucitaj(tekst.encode("utf-8"))
    greske = greska.value.greske
    assert len(greske) == 3
    assert any(g.startswith("formula.osnovica_gore") for g in greske)
    assert any(g.startswith("naziv_datoteke.nepoznato") for g in greske)
    assert any(g.startswith("formula.sjeme") for g in greske)


@pytest.mark.parametrize(
    ("staro", "novo"),
    [
        ('korak = "0,1 cm"', 'korak = "0 cm"'),
        ('raspon = "0,5 cm"', 'raspon = "0,45 cm"'),
        ('margine = "0,03 cm"', 'margine = "0,06 cm"'),
        ('margine = "0,03 cm"', "margine = 0.03"),
        ("[tolerancije]", "[pravila.R-NEPOSTOJECE]\nukljuceno = true\n[tolerancije]"),
        ("objavljeno = true", ""),
        ('osnovica_desno = "2,5 cm"', 'osnovica_desno = "0,5 cm"'),
        ('naslovnica = "2,5 cm"', 'naslovnica = "0 cm"'),
        ('raspon = "0,5 cm"', 'raspon = "1,1 cm"'),
        ("ukljuceno = true", "ukljuceno = 5"),
        ("ukljuceno = true", "ukljuceno = true\nnepoznato = 1"),
    ],
)
def test_neispravan_profil_baca_gresku_profila(staro, novo):
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(_vjezba_1().replace(staro, novo).encode("utf-8"))


@pytest.mark.parametrize("sadrzaj", [b"[vjezba", b"\xff\xfe"])
def test_neispravan_toml(sadrzaj):
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(sadrzaj)


def test_objavljeni_preskace_neobjavljene_i_broji_neispravne():
    objavljen = _vjezba_1().encode("utf-8")
    neobjavljen = _vjezba_1().replace("objavljeno = true", "objavljeno = false").encode("utf-8")
    profili, neispravnih = profil.objavljeni([objavljen, neobjavljen, b"[vjezba", objavljen])
    assert [p.vjezba.id for p in profili] == ["vjezba_1"]
    assert neispravnih == 2  # neispravan TOML i duplikat id-a


def test_ucitava_profil_s_bom():
    assert profil.ucitaj(b"\xef\xbb\xbf" + _vjezba_1().encode("utf-8")).vjezba.id == "vjezba_1"

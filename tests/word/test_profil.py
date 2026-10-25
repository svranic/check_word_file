from pathlib import Path

import pytest

from provjera.word.jezgra import profil

PROFIL_VJEZBE_1 = Path(__file__).resolve().parents[2] / "tests" / "word" / "fixtures" / "vjezba_1_baseline.toml"


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
        "[tolerancije]\nstranica = \"0,1 cm\"\nmargine = \"0,03 cm\"\n"
        "[formula]\nsjeme = 20261012\nnaslovnica = \"2,5 cm\"\nkorak = \"0,1 cm\"\n"
        "raspon = \"0,5 cm\"\nosnovica_desno = \"2,5 cm\"\nosnovica_lijevo = \"3 cm\"\n"
        "osnovica_dolje = \"2,5 cm\"\nosnovica_gore = \"2,5 cm\"\n"
        "[naziv_datoteke]\nnastavak = \".docx\"\nsufiks = \"_GiG_OG_Vjezba_1\"\n"
        "[vjezba]\npoveznica = \"https://provjera-word.streamlit.app/\"\n"
        "objavljeno = true\nnaziv = \"Vježba 1\"\nid = \"vjezba_1\"\n"
        "[pravila.R-TEKST]\nprored = \"1\"\nrazmak_iza = \"6 pt\"\nrazmak_ispred = \"6 pt\"\n"
        "poravnanje = \"obostrano\"\nvelicina = \"12 pt\"\nfont = \"Calibri\"\nstil = \"Normal\"\n"
        "[pravila.R-NASLOVI]\noznaka = \"{n}.\"\nrazmak_iza = \"6 pt\"\nrazmak_ispred = \"6 pt\"\n"
        "poravnanje = \"lijevo\"\nvelicina = \"12 pt\"\npodebljano = true\nfont = \"Calibri\"\n"
        "stil = \"Heading 1\"\n"
        "[pravila.R-LITERATURA]\nvelicina = \"12 pt\"\nfont = \"Calibri\"\nukljuceno = true\n"
        "[pravila.R-SAZETAK]\ntolerancija = \"0,03 cm\"\nuvlaka_desno = \"3,5 cm\"\n"
        "uvlaka_lijevo = \"3,5 cm\"\nporavnanje = \"obostrano\"\nvelicina = \"12 pt\"\n"
        "font = \"Calibri\"\nukljuceno = true\n"
        "[pravila.R-BROJ-STRANICE]\nvelicina = \"10 pt\"\nfont = \"Calibri\"\nukljuceno = true\n"
        "[uloge]\npoglavlja = [\"Uvod\", \"Studij geodezije i geomatike u Varaždinu\", "
        "\"Zaključak\", \"Literatura\"]\nliteratura = \"Literatura\"\nsazetak = \"Sažetak\"\n"
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


def test_r_tekst_i_uloge_dolaze_iz_profila():
    p = profil.ucitaj(PROFIL_VJEZBE_1.read_bytes())
    tekst = p.pravila["R-TEKST"]
    assert (tekst.stil, tekst.font, tekst.velicina, tekst.poravnanje.value) == ("Normal", "Calibri", 24, "obostrano")
    assert (tekst.razmak_ispred, tekst.razmak_iza, tekst.prored) == (120, 120, 240)
    assert p.uloge.sazetak == "Sažetak" and p.uloge.literatura in p.uloge.poglavlja


@pytest.mark.parametrize("odjeljak", ["[uloge]", "[pravila.R-TEKST]", "[pravila.R-NASLOVI]"])
def test_bez_odjeljka_uloga_ili_r_teksta_profil_je_neispravan(odjeljak):
    tekst = _vjezba_1()
    pocetak = tekst.index(odjeljak)
    kraj = tekst.find("\n[", pocetak + 1)
    bez = tekst[:pocetak] + (tekst[kraj + 1:] if kraj != -1 else "")
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(bez.encode("utf-8"))


def test_neispravno_poravnanje_u_profilu():
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(_vjezba_1().replace('poravnanje = "obostrano"', 'poravnanje = "koso"').encode("utf-8"))


def test_iskljucen_r_tekst_ne_treba_ciljne_vrijednosti():
    tekst = _vjezba_1()
    pocetak = tekst.index("[pravila.R-TEKST]")
    kraj = tekst.find("\n[", pocetak + 1)
    bez = tekst[:pocetak] + "[pravila.R-TEKST]\nukljuceno = false\n" + (tekst[kraj + 1:] if kraj != -1 else "")
    assert profil.ucitaj(bez.encode("utf-8")).pravila["R-TEKST"].ukljuceno is False
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(bez.replace("ukljuceno = false", "ukljuceno = true").encode("utf-8"))


def test_poravnanje_ostalo_nije_dopusteno_u_profilu():
    with pytest.raises(profil.GreskaProfila):
        profil.ucitaj(_vjezba_1().replace('poravnanje = "obostrano"', 'poravnanje = "ostalo"').encode("utf-8"))


def test_bez_poveznice_greska_kljuca_vjezba_poveznica():
    tekst = "\n".join(
        r for r in _vjezba_1().splitlines() if not r.startswith("poveznica =")
    )
    with pytest.raises(profil.GreskaProfila) as greska:
        profil.ucitaj(tekst.encode("utf-8"))
    assert len(greska.value.greske) == 1
    assert greska.value.greske[0].startswith("vjezba.poveznica:")


@pytest.mark.parametrize(
    "poveznica",
    [
        "http://provjera.primjer.hr/",
        "provjera.primjer.hr",
        "https://",
        "https:///put",
        "https://primjer.hr/ razmak",
        " https://primjer.hr/",
        "ftp://primjer.hr/",
        "https://[neispravno",
        "https://primjer.hr:abc/",
        "https://primjer.hr:99999/",
        "",
    ],
)
def test_poveznica_mora_biti_https(poveznica):
    tekst = _vjezba_1().replace(
        'poveznica = "https://provjera-word.streamlit.app/"', f'poveznica = "{poveznica}"'
    )
    with pytest.raises(profil.GreskaProfila) as greska:
        profil.ucitaj(tekst.encode("utf-8"))
    assert [g.split(":")[0] for g in greska.value.greske] == ["vjezba.poveznica"]


def test_poveznica_vjezbe_1():
    p = profil.ucitaj(PROFIL_VJEZBE_1.read_bytes())
    assert p.vjezba.poveznica.startswith("https://")


@pytest.mark.parametrize(
    ("staro", "novo", "poruka_greske"),
    [
        # Bez ove provjere formula se za raspon 0 vrti beskonačno.
        ('raspon = "0,5 cm"', 'raspon = "0 cm"', "raspon mora biti pozitivan višekratnik koraka"),
        ('korak = "0,1 cm"', 'korak = "0,2 cm"', "raspon mora biti pozitivan višekratnik koraka"),
    ],
)
def test_raspon_mora_biti_pozitivan_visekratnik_koraka(staro, novo, poruka_greske):
    with pytest.raises(profil.GreskaProfila) as greska:
        profil.ucitaj(_vjezba_1().replace(staro, novo).encode("utf-8"))
    assert any(poruka_greske in g for g in greska.value.greske)


def test_neispravan_neobjavljeni_nacrt_se_ne_broji():
    nacrt = _vjezba_1().replace("objavljeno = true", "objavljeno = false")
    nacrt = nacrt.replace('korak = "0,1 cm"', 'korak = "0 cm"').encode("utf-8")
    profili, neispravnih = profil.objavljeni([_vjezba_1().encode("utf-8"), nacrt])
    assert [p.vjezba.id for p in profili] == ["vjezba_1"]
    assert neispravnih == 0


def test_verzija_se_mijenja_s_postavkom_pravila():
    a = profil.ucitaj(_vjezba_1().encode("utf-8"))
    izvor = _vjezba_1()
    assert 'font = "Calibri"' in izvor
    b = profil.ucitaj(izvor.replace('font = "Calibri"', 'font = "Arial"', 1).encode("utf-8"))
    assert profil.verzija(a) != profil.verzija(b)

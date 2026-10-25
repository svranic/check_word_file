"""Samoprovjera profila na referentnom skupu (priča 3.4): jezgra, adapter i objavljeni profili."""

import shutil
import tomllib
from pathlib import Path

import pytest

from provjera.word.adapteri.samoprovjera import GreskaReferentnog, pokreni
from provjera.word.jezgra import profil
from provjera.word.jezgra.poruke import KATALOG
from provjera.word.jezgra.samoprovjera import (
    RezultatPrimjera,
    StatusPrimjera,
    broj_odstupanja,
    neuspjeli,
    ukupno,
    usporedi,
)

KORIJEN = Path(__file__).resolve().parents[2]
REFERENTNI = KORIJEN / "tests" / "word" / "referentni"
VJEZBA_1 = KORIJEN / "profili" / "word" / "vjezba_1.toml"
SVA = {"R-MARGINE", "R-TEKST", "R-OKVIRI"}


@pytest.fixture(scope="module")
def vjezba():
    return profil.ucitaj(VJEZBA_1.read_bytes())


@pytest.fixture(scope="module")
def rezultati_vjezbe_1(vjezba):
    return pokreni(vjezba, REFERENTNI)


def _iskljuci(p: profil.Profil, pravilo_id: str) -> profil.Profil:
    pravila = dict(p.pravila)
    pravila[pravilo_id] = pravila[pravilo_id].model_copy(update={"ukljuceno": False})
    return p.model_copy(update={"pravila": pravila})


def _po_imenu(rezultati) -> dict[str, RezultatPrimjera]:
    return {r.ime: r for r in rezultati}


# --- Jezgra --------------------------------------------------------------------


def test_usporedi_isti_skup_prolazi():
    r = usporedi("a", ["R-TEKST"], {"R-TEKST"}, SVA)
    assert r == RezultatPrimjera("a", frozenset({"R-TEKST"}), frozenset({"R-TEKST"}),
                                 StatusPrimjera.PROLAZI)


@pytest.mark.parametrize("pronadeno", [set(), {"R-MARGINE", "R-TEKST"}, {"R-TEKST"}])
def test_usporedi_razlicit_skup_ne_prolazi(pronadeno):
    assert usporedi("a", {"R-MARGINE"}, pronadeno, SVA).status is StatusPrimjera.NE_PROLAZI


def test_usporedi_iskljuceno_ocekivano_pravilo_preskace():
    r = usporedi("okvir_tekst", {"R-OKVIRI"}, set(), {"R-MARGINE"})
    assert r.status is StatusPrimjera.PRESKOCENO


def test_ispravan_se_ne_preskace_ni_kad_su_sva_pravila_iskljucena():
    assert usporedi("ispravan", set(), set(), set()).status is StatusPrimjera.PROLAZI


def test_ukupno_trazi_neprekocen_ispravan_rad():
    ispravan = usporedi("ispravan", set(), set(), SVA)
    pokvaren = usporedi("m", {"R-MARGINE"}, {"R-MARGINE"}, SVA)
    preskocen = usporedi("o", {"R-OKVIRI"}, set(), set())
    assert ukupno([ispravan, pokvaren, preskocen])
    assert not ukupno([pokvaren, preskocen])
    assert not ukupno([])
    assert broj_odstupanja([pokvaren]) == 1
    assert broj_odstupanja([]) == 1


def test_ukupno_pada_na_odstupanju():
    ispravan = usporedi("ispravan", set(), set(), SVA)
    odstupanje = usporedi("m", {"R-MARGINE"}, set(), SVA)
    nema = neuspjeli("x", {"R-TEKST"}, "samoprovjera.nema_datoteke")
    assert not ukupno([ispravan, odstupanje])
    assert broj_odstupanja([ispravan, odstupanje, nema]) == 2


def test_rezultat_je_nepromjenjiv_i_hashabilan():
    r = neuspjeli("x", None, "samoprovjera.nema_zapisa", {"a": 1})
    with pytest.raises(TypeError):
        r.parametri["a"] = 2
    assert {r, neuspjeli("x", None, "samoprovjera.nema_zapisa", {"a": 1})} == {r}


# --- Matrica: referentni skup Vježbe 1 ------------------------------------------


def test_sve_se_slaze(rezultati_vjezbe_1):
    ocekivano = tomllib.loads((REFERENTNI / "vjezba_1" / "ocekivano.toml").read_text("utf-8"))
    assert [r.ime for r in rezultati_vjezbe_1] == sorted(ocekivano["primjeri"])
    assert {r.status for r in rezultati_vjezbe_1} == {StatusPrimjera.PROLAZI}
    assert ukupno(rezultati_vjezbe_1)
    assert broj_odstupanja(rezultati_vjezbe_1) == 0


def test_kaskada_vise_nalaza_istog_pravila_prolazi(rezultati_vjezbe_1):
    """``tekst_font`` pada R-TEKST u svim odlomcima osnovnog teksta; skup je ipak {R-TEKST}."""
    r = _po_imenu(rezultati_vjezbe_1)["tekst_font"]
    assert r.ocekivano == r.pronadeno == frozenset({"R-TEKST"})
    assert r.status is StatusPrimjera.PROLAZI


def test_iskljuceno_pravilo_preskace_samo_njegove_primjere(vjezba):
    rezultati = pokreni(_iskljuci(vjezba, "R-OKVIRI"), REFERENTNI)
    preskoceni = {r.ime for r in rezultati if r.status is StatusPrimjera.PRESKOCENO}
    # okvir_naslovnica očekuje prolaz (okvir na naslovnici je dopušten), pa se ne preskače.
    assert preskoceni == {"okvir_naslov", "okvir_tekst"}
    assert _po_imenu(rezultati)["okvir_naslovnica"].status is StatusPrimjera.PROLAZI
    assert {r.status for r in rezultati if r.ime not in preskoceni} == {StatusPrimjera.PROLAZI}
    assert ukupno(rezultati)


def test_tolerancija_koja_propusta_krive_margine(vjezba):
    # Profil zaobilazi validaciju (tolerancija veća od pola koraka), kao pogrešna izmjena.
    tolerancije = vjezba.tolerancije.model_copy(update={"margine": 120})  # ~2,1 mm
    labav = vjezba.model_copy(update={"tolerancije": tolerancije})
    rezultati = pokreni(labav, REFERENTNI)
    r = _po_imenu(rezultati)["krive_margine_tijela"]
    assert r.status is StatusPrimjera.NE_PROLAZI
    assert r.ocekivano == frozenset({"R-MARGINE"})
    assert r.pronadeno == frozenset()
    assert not ukupno(rezultati)
    assert broj_odstupanja(rezultati) >= 1


def test_bez_skupa_baca_gresku_referentnog(vjezba, tmp_path):
    with pytest.raises(GreskaReferentnog) as greska:
        pokreni(vjezba, tmp_path)
    assert greska.value.poruka_kljuc == "samoprovjera.nema_skupa"
    assert greska.value.parametri["mapa"] == str(tmp_path / "vjezba_1")


# --- Adapter: rubni slučajevi mape ------------------------------------------------


def _mapa(tmp_path: Path, ocekivano: str | None) -> Path:
    mapa = tmp_path / "vjezba_1"
    mapa.mkdir()
    if ocekivano is not None:
        (mapa / "ocekivano.toml").write_text(ocekivano, encoding="utf-8")
    return mapa


def test_bez_ocekivano_toml(vjezba, tmp_path):
    _mapa(tmp_path, None)
    with pytest.raises(GreskaReferentnog) as greska:
        pokreni(vjezba, tmp_path)
    assert greska.value.poruka_kljuc == "samoprovjera.nema_ocekivanog"


_NAZIV = 'naziv = "x"\n'


@pytest.mark.parametrize(
    "sadrzaj",
    [
        "nije = [toml",
        'rbr = 54\n[primjeri.a]\npadaju = []',
        'rbr = 54\nnaziv = "x"\n[primjeri.a]\n',
        "rbr = 0\n" + _NAZIV + "[primjeri.a]\npadaju = []",
        "rbr = -1\n" + _NAZIV + "[primjeri.a]\npadaju = []",
        "rbr = true\n" + _NAZIV + "[primjeri.a]\npadaju = []",
        "rbr = 54\n" + _NAZIV + "[primjeri.a]\npadaju = [1]",
        "rbr = 54\n" + _NAZIV + "[primjeri]\na = 5",
    ],
)
def test_neispravan_ocekivano_toml(vjezba, tmp_path, sadrzaj):
    _mapa(tmp_path, sadrzaj)
    with pytest.raises(GreskaReferentnog) as greska:
        pokreni(vjezba, tmp_path)
    assert greska.value.poruka_kljuc == "samoprovjera.ocekivano_neispravno"


def test_primjer_bez_datoteke_i_datoteka_bez_zapisa(vjezba, tmp_path):
    izvor = REFERENTNI / "vjezba_1"
    mapa = _mapa(
        tmp_path,
        'rbr = 54\nnaziv = "Ana_Horvat_GiG_OG_Vjezba_1.docx"\n'
        "[primjeri.ispravan]\npadaju = []\n"
        '[primjeri.nestali]\npadaju = ["R-TEKST"]\n',
    )
    shutil.copy(izvor / "ispravan.docx", mapa / "ispravan.docx")
    shutil.copy(izvor / "tekst_font.docx", mapa / "visak.docx")
    (mapa / "biljeska.txt").write_text("nije primjer", encoding="utf-8")
    rezultati = _po_imenu(pokreni(vjezba, tmp_path))
    assert list(rezultati) == ["ispravan", "nestali", "visak"]
    assert rezultati["ispravan"].status is StatusPrimjera.PROLAZI
    assert rezultati["nestali"] == neuspjeli("nestali", {"R-TEKST"}, "samoprovjera.nema_datoteke")
    assert rezultati["visak"] == neuspjeli("visak", None, "samoprovjera.nema_zapisa")
    assert not ukupno(rezultati.values())
    assert broj_odstupanja(rezultati.values()) == 2


def test_odbijen_dokument_ne_prolazi(vjezba, tmp_path):
    mapa = _mapa(
        tmp_path,
        'rbr = 54\nnaziv = "Ana_Horvat_GiG_OG_Vjezba_1.docx"\n[primjeri.ostecen]\npadaju = []\n',
    )
    (mapa / "ostecen.docx").write_bytes(b"nije docx")
    [r] = pokreni(vjezba, tmp_path)
    assert r.status is StatusPrimjera.NE_PROLAZI
    assert r.razlog == "samoprovjera.odbijeno"
    assert r.parametri["razlog"]  # razlog odbijanja iz izvještaja (npr. "ostecena")


_TRI_PRIMJERA = (
    'rbr = 54\nnaziv = "Ana_Horvat_GiG_OG_Vjezba_1.docx"\n'
    "[primjeri.ispravan]\npadaju = []\n"
    '[primjeri.tekst_font]\npadaju = ["R-TEKST"]\n'
    '[primjeri.krive_margine_tijela]\npadaju = ["R-MARGINE"]\n'
)


def _tri_primjera(tmp_path: Path) -> Path:
    mapa = _mapa(tmp_path, _TRI_PRIMJERA)
    for ime in ("ispravan", "tekst_font", "krive_margine_tijela"):
        shutil.copy(REFERENTNI / "vjezba_1" / f"{ime}.docx", mapa / f"{ime}.docx")
    return mapa


def test_nepoznat_id_pravila_odbacuje_skup(vjezba, tmp_path):
    """Tipfeler u ID-u inače bi primjer tiho preskočio (pravilo „nije uključeno“)."""
    _mapa(tmp_path, "rbr = 54\n" + _NAZIV + '[primjeri.a]\npadaju = ["R-MARGNE", "R-TEKST"]')
    with pytest.raises(GreskaReferentnog) as greska:
        pokreni(vjezba, tmp_path)
    assert greska.value.poruka_kljuc == "samoprovjera.nepoznato_pravilo"
    assert greska.value.parametri["pravila"] == "R-MARGNE"


def test_datoteke_zakljucavanja_i_skrivene_nisu_primjeri(vjezba, tmp_path):
    mapa = _tri_primjera(tmp_path)
    (mapa / "~$ispravan.docx").write_bytes(b"lock")
    (mapa / ".skriven.docx").write_bytes(b"x")
    rezultati = pokreni(vjezba, tmp_path)
    assert [r.ime for r in rezultati] == ["ispravan", "krive_margine_tijela", "tekst_font"]
    assert ukupno(rezultati)


def test_necitljiv_primjer_ne_prekida_ostale(vjezba, tmp_path, monkeypatch):
    _tri_primjera(tmp_path)
    pravi = Path.read_bytes

    def read_bytes(self):
        if self.stem == "tekst_font":
            raise PermissionError(13, "zaključano")
        return pravi(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    rezultati = _po_imenu(pokreni(vjezba, tmp_path))
    assert rezultati["tekst_font"] == neuspjeli("tekst_font", {"R-TEKST"}, "samoprovjera.necitljiv")
    assert rezultati["ispravan"].status is StatusPrimjera.PROLAZI
    assert rezultati["krive_margine_tijela"].status is StatusPrimjera.PROLAZI


def test_neocekivana_greska_provjere_ne_prekida_ostale(vjezba, tmp_path, monkeypatch):
    from provjera.word.adapteri import samoprovjera as adapter

    _tri_primjera(tmp_path)
    pravi = adapter.provjeri
    tekst_font = (REFERENTNI / "vjezba_1" / "tekst_font.docx").read_bytes()

    def provjeri(sadrzaj, p, kontekst):
        if sadrzaj == tekst_font:
            raise RuntimeError("kvar")
        return pravi(sadrzaj, p, kontekst)

    monkeypatch.setattr(adapter, "provjeri", provjeri)
    rezultati = _po_imenu(pokreni(vjezba, tmp_path))
    assert rezultati["tekst_font"] == neuspjeli(
        "tekst_font", {"R-TEKST"}, "samoprovjera.greska_provjere", {"razlog": "RuntimeError"}
    )
    assert rezultati["ispravan"].status is StatusPrimjera.PROLAZI


def test_necitljiva_mapa_baca_gresku_referentnog(vjezba, tmp_path, monkeypatch):
    _tri_primjera(tmp_path)

    def glob(self, _uzorak):
        raise PermissionError(13, "zaključano")

    monkeypatch.setattr(Path, "glob", glob)
    with pytest.raises(GreskaReferentnog) as greska:
        pokreni(vjezba, tmp_path)
    assert greska.value.poruka_kljuc == "samoprovjera.mapa_necitljiva"


def test_kljucevi_razloga_u_katalogu():
    for kljuc in (
        "samoprovjera.nema_skupa",
        "samoprovjera.nema_ocekivanog",
        "samoprovjera.ocekivano_neispravno",
        "samoprovjera.nema_datoteke",
        "samoprovjera.nema_zapisa",
        "samoprovjera.necitljiv",
        "samoprovjera.odbijeno",
        "samoprovjera.greska_provjere",
        "samoprovjera.nepoznato_pravilo",
        "samoprovjera.mapa_necitljiva",
    ):
        assert kljuc in KATALOG


# --- Svaki objavljeni profil mora proći samoprovjeru -------------------------------


def _objavljeni_profili() -> list[Path]:
    return [
        p
        for p in sorted((KORIJEN / "profili" / "word").glob("*.toml"))
        if tomllib.loads(p.read_text(encoding="utf-8-sig")).get("vjezba", {}).get("objavljeno") is True
    ]


def test_postoji_barem_jedan_objavljeni_profil():
    assert _objavljeni_profili()


@pytest.mark.parametrize("datoteka", _objavljeni_profili(), ids=lambda p: p.name)
def test_objavljeni_profil_prolazi_samoprovjeru(datoteka):
    rezultati = pokreni(profil.ucitaj(datoteka.read_bytes()), REFERENTNI)
    odstupanja = [r for r in rezultati if r.status is StatusPrimjera.NE_PROLAZI]
    assert ukupno(rezultati), f"samoprovjera ne prolazi za {datoteka.name}: {odstupanja}"

from pathlib import Path

import pytest
from alati.generator import ispravan

from provjera.jezgra import profil
from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status, Vrijednost
from provjera.jezgra.pravila import REGISTAR
from provjera.jezgra.pravila.osnova import Pravilo, PostavkeBaza
from provjera.jezgra.provjera import provjeri, spremnost, status_pravila
from provjera.jezgra.ulaz import RazlogOdbijanja

KORIJEN = Path(__file__).resolve().parents[1]
TOML = (KORIJEN / "profili" / "vjezba_1.toml").read_text(encoding="utf-8")
PROFIL = profil.ucitaj(TOML.encode("utf-8"))
NAZIV = "Lucija_Šimek_GiG_OG_Vjezba_1.docx"


def _docx() -> bytes:
    """Ispravan sintetski rad za Rbr. 54 (naslovnica + tijelo, A4)."""
    return ispravan(54, profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes()))


def _kontekst(naziv=NAZIV):
    return KontekstProvjere(naziv, 54, None, None)


def _nalaz(pravilo_id, status=Status.PROSLO, kljuc="test.kljuc", sekcija=1):
    return Nalaz(pravilo_id, status, Lokacija(Dio.TIJELO, sekcija=sekcija), kljuc,
                 ocekivano=Vrijednost(1, Jedinica.TWIPS), pronadeno=Vrijednost(2, Jedinica.TWIPS))


@pytest.fixture
def privremena_pravila(monkeypatch):
    """Zamjenjuje registar kopijom kojoj test dodaje pravila."""
    registar = dict(REGISTAR)
    monkeypatch.setattr("provjera.jezgra.provjera.REGISTAR", registar)

    def dodaj(pravilo_id, funkcija):
        registar[pravilo_id] = Pravilo(pravilo_id, funkcija, PostavkeBaza, ())

    return dodaj


def test_ispravan_dokument_i_naziv_su_spremni():
    izvjestaj = provjeri(_docx(), PROFIL, _kontekst())
    assert izvjestaj.odbijeno is None
    assert status_pravila(izvjestaj.nalazi, "R-NAZIV") is Status.PROSLO
    assert spremnost(izvjestaj)
    assert izvjestaj.rbr == 54
    assert izvjestaj.profil_verzija == profil.verzija(PROFIL)


def test_odbijena_datoteka_nema_nalaza():
    izvjestaj = provjeri(b"%PDF", PROFIL, _kontekst("rad.pdf"))
    assert izvjestaj.odbijeno is RazlogOdbijanja.NEISPRAVAN_FORMAT
    assert izvjestaj.nalazi == ()
    assert not spremnost(izvjestaj)


def test_iznimka_i_prazan_rezultat_su_neprovjerljivi_a_ostala_pravila_se_izvode(privremena_pravila):
    def baca(*_):
        raise KeyError("x")

    privremena_pravila("R-BACA", baca)
    privremena_pravila("R-PRAZNO", lambda *_: [])
    privremena_pravila("R-DOBRO", lambda *_: [_nalaz("R-DOBRO")])
    izvjestaj = provjeri(_docx(), PROFIL, _kontekst("pogresan naziv.docx"))
    assert status_pravila(izvjestaj.nalazi, "R-NAZIV") is Status.NE_PROLAZI
    assert status_pravila(izvjestaj.nalazi, "R-BACA") is Status.NEPROVJERLJIVO
    assert status_pravila(izvjestaj.nalazi, "R-PRAZNO") is Status.NEPROVJERLJIVO
    assert status_pravila(izvjestaj.nalazi, "R-DOBRO") is Status.PROSLO
    [baca_nalaz] = [n for n in izvjestaj.nalazi if n.pravilo_id == "R-BACA"]
    assert baca_nalaz.poruka_kljuc == "opce.neprovjerljivo"
    assert baca_nalaz.parametri["razlog"] == "KeyError"
    assert not spremnost(izvjestaj)


def test_ponavljanja_se_sazimaju(privremena_pravila):
    privremena_pravila(
        "R-PONAVLJA",
        lambda *_: [_nalaz("R-PONAVLJA", Status.NE_PROLAZI, sekcija=s) for s in (2, 3, 4)]
        + [_nalaz("R-PONAVLJA", Status.PROSLO)],
    )
    izvjestaj = provjeri(_docx(), PROFIL, _kontekst())
    nalazi = [n for n in izvjestaj.nalazi if n.pravilo_id == "R-PONAVLJA"]
    assert [(n.status, n.pojave, n.lokacija.sekcija) for n in nalazi] == [
        (Status.NE_PROLAZI, 3, 2),
        (Status.PROSLO, 1, 1),
    ]


def test_sazimanje_pamti_do_tri_primjera_lokacija(privremena_pravila):
    privremena_pravila(
        "R-PONAVLJA",
        lambda *_: [_nalaz("R-PONAVLJA", Status.NE_PROLAZI, sekcija=s) for s in range(2, 42)]
        + [_nalaz("R-PONAVLJA", Status.PROSLO)],
    )
    izvjestaj = provjeri(_docx(), PROFIL, _kontekst())
    sazeti, jedini = [n for n in izvjestaj.nalazi if n.pravilo_id == "R-PONAVLJA"]
    assert sazeti.pojave == 40
    assert [p.sekcija for p in sazeti.primjeri] == [2, 3, 4]
    assert sazeti.primjeri[0] == sazeti.lokacija
    assert (jedini.pojave, jedini.primjeri) == (1, ())


def test_ista_lokacija_se_ne_ponavlja_u_primjerima(privremena_pravila):
    privremena_pravila(
        "R-PONAVLJA",
        lambda *_: [_nalaz("R-PONAVLJA", Status.NE_PROLAZI, sekcija=s) for s in (2, 2, 3)],
    )
    [nalaz] = [n for n in provjeri(_docx(), PROFIL, _kontekst()).nalazi if n.pravilo_id == "R-PONAVLJA"]
    assert (nalaz.pojave, [p.sekcija for p in nalaz.primjeri]) == (3, [2, 3])


def test_status_pravila_poredak():
    nalazi = (
        _nalaz("R-X", Status.PROSLO),
        _nalaz("R-X", Status.NEPROVJERLJIVO),
        _nalaz("R-X", Status.NE_PROLAZI),
        _nalaz("R-Y", Status.PROSLO),
        _nalaz("R-Y", Status.NE_PROLAZI),
    )
    assert status_pravila(nalazi, "R-X") is Status.NEPROVJERLJIVO
    assert status_pravila(nalazi, "R-Y") is Status.NE_PROLAZI
    assert status_pravila(nalazi, "R-Z") is None


def test_iskljuceno_pravilo_nema_nalaza():
    iskljucen = profil.ucitaj(
        TOML.replace("[pravila.R-NAZIV]\nukljuceno = true", "[pravila.R-NAZIV]\nukljuceno = false").encode("utf-8")
    )
    izvjestaj = provjeri(_docx(), iskljucen, _kontekst("pogresan.docx"))
    assert status_pravila(izvjestaj.nalazi, "R-NAZIV") is None
    assert spremnost(izvjestaj)  # pogrešan naziv se ne provjerava


def test_izvjestaj_bez_nalaza_nije_spreman():
    from provjera.jezgra.nalaz import Izvjestaj

    assert not spremnost(Izvjestaj(None, (), "abcd1234", 54))


def test_svaki_kljuc_registriranog_pravila_je_u_katalogu():
    from provjera.jezgra.poruke import KATALOG

    for pravilo in REGISTAR.values():
        assert f"pravilo.{pravilo.id}" in KATALOG
        for kljuc in pravilo.poruke:
            assert kljuc in KATALOG, kljuc
    assert "opce.neprovjerljivo" in KATALOG


def test_nalazi_s_razlicitim_parametrima_se_ne_spajaju(privremena_pravila):
    def dva_razloga(*_):
        return [
            Nalaz("R-PAR", Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), "opce.neprovjerljivo", parametri={"razlog": r})
            for r in ("a", "b", "a")
        ]

    privremena_pravila("R-PAR", dva_razloga)
    nalazi = [n for n in provjeri(_docx(), PROFIL, _kontekst()).nalazi if n.pravilo_id == "R-PAR"]
    assert [(n.parametri["razlog"], n.pojave) for n in nalazi] == [("a", 2), ("b", 1)]


def test_neispravan_rezultat_pravila_je_neprovjerljiv(privremena_pravila):
    privremena_pravila("R-LOSE", lambda *_: [None])
    privremena_pravila("R-TUDE", lambda *_: [_nalaz("R-DRUGO")])
    izvjestaj = provjeri(_docx(), PROFIL, _kontekst())
    assert status_pravila(izvjestaj.nalazi, "R-LOSE") is Status.NEPROVJERLJIVO
    assert status_pravila(izvjestaj.nalazi, "R-TUDE") is Status.NEPROVJERLJIVO
    assert status_pravila(izvjestaj.nalazi, "R-NAZIV") is Status.PROSLO


def test_memory_error_u_pravilu_se_propusta(privremena_pravila):
    def baca(*_):
        raise MemoryError

    privremena_pravila("R-MEM", baca)
    with pytest.raises(MemoryError):
        provjeri(_docx(), PROFIL, _kontekst())


def test_greska_modela_ne_rusi_pravila_koja_ga_ne_trebaju(monkeypatch, privremena_pravila):
    def neuspjeh(*_):
        raise ValueError("model")

    monkeypatch.setattr("provjera.jezgra.model.procitaj", neuspjeh)
    privremena_pravila("R-TREBA-MODEL", lambda model, *_: [_nalaz("R-TREBA-MODEL")] if model else 1 / 0)
    izvjestaj = provjeri(_docx(), PROFIL, _kontekst())
    assert status_pravila(izvjestaj.nalazi, "R-NAZIV") is Status.PROSLO
    assert status_pravila(izvjestaj.nalazi, "R-TREBA-MODEL") is Status.NEPROVJERLJIVO
    [nalaz] = [n for n in izvjestaj.nalazi if n.pravilo_id == "R-TREBA-MODEL"]
    assert nalaz.parametri["razlog"] == "ValueError"


def test_profil_bez_odjeljka_pravila_dobiva_zadane_postavke():
    bez = profil.ucitaj(TOML.replace("[pravila.R-NAZIV]\nukljuceno = true\n", "").encode("utf-8"))
    assert bez.pravila["R-NAZIV"].ukljuceno is True


# --- Ukupni status (priča 4.1, AD-5) --------------------------------------------


def _izvjestaj(*statusi, odbijeno=None):
    from provjera.jezgra.nalaz import Izvjestaj

    nalazi = tuple(_nalaz(f"R-{i}", s) for i, s in enumerate(statusi))
    return Izvjestaj(odbijeno, nalazi, "v", 1)


@pytest.mark.parametrize(
    ("izvjestaj", "ima_datoteku", "aktivan", "ocekivano"),
    [
        (None, False, False, "NEAKTIVAN"),
        (_izvjestaj(Status.PROSLO), True, False, "NEAKTIVAN"),
        (None, False, True, "NIJE_PREDAO"),
        (None, True, True, "NEUSPJELA_OBRADA"),
        (_izvjestaj(odbijeno=RazlogOdbijanja.NEISPRAVAN_FORMAT), True, True, "NEISPRAVAN_FORMAT"),
        (_izvjestaj(odbijeno=RazlogOdbijanja.STARI_DOC), True, True, "NEISPRAVAN_FORMAT"),
        (_izvjestaj(odbijeno=RazlogOdbijanja.MAKRO), True, True, "NEISPRAVAN_FORMAT"),
        (_izvjestaj(odbijeno=RazlogOdbijanja.OSTECENA), True, True, "NEUSPJELA_OBRADA"),
        (_izvjestaj(odbijeno=RazlogOdbijanja.SIFRIRANA), True, True, "NEUSPJELA_OBRADA"),
        (_izvjestaj(odbijeno=RazlogOdbijanja.PRAZNA), True, True, "NEUSPJELA_OBRADA"),
        (_izvjestaj(Status.PROSLO, Status.NEPROVJERLJIVO), True, True, "ZA_RUCNI_PREGLED"),
        (_izvjestaj(Status.NE_PROLAZI, Status.NEPROVJERLJIVO), True, True, "ZA_RUCNI_PREGLED"),
        (_izvjestaj(Status.PROSLO, Status.NE_PROLAZI), True, True, "NIJE_SPREMNO"),
        (_izvjestaj(), True, True, "NIJE_SPREMNO"),
        (_izvjestaj(Status.PROSLO, Status.PROSLO), True, True, "SPREMNO"),
    ],
)
def test_ukupni_status(izvjestaj, ima_datoteku, aktivan, ocekivano):
    from provjera.jezgra.provjera import UkupniStatus, ukupni_status

    assert ukupni_status(izvjestaj, ima_datoteku, aktivan) is UkupniStatus[ocekivano]


def test_svaki_ukupni_status_ima_ikonu_i_tekst():
    from provjera.jezgra.poruke import KATALOG
    from provjera.jezgra.predaje import opis_statusa
    from provjera.jezgra.provjera import UkupniStatus

    for status in UkupniStatus:
        assert f"ukupni_status.{status.value}" in KATALOG
        ikona, _, tekst = opis_statusa(status).partition(" ")
        assert ikona and not ikona.isalpha() and tekst == opis_statusa(status, ikona=False)

"""Zbirna tablica (priča 4.3, FR27): sadržaj listova Rezultati, Nalazi i Nepovezano."""

from pathlib import Path

from provjera.adapteri.popis import Student
from provjera.jezgra import profil
from provjera.jezgra.nalaz import (
    Dio,
    Izvjestaj,
    Lokacija,
    NacinUparivanja,
    Nalaz,
    Status,
    Vrijednost,
)
from provjera.jezgra.jedinice import Jedinica
from provjera.jezgra.pravila import REGISTAR
from provjera.jezgra.predaje import RedakDatoteke, RezultatBatcha
from provjera.jezgra.ulaz import RazlogOdbijanja
from provjera.jezgra.uparivanje import RazlogNepovezanosti
from provjera.jezgra.zbirna import izradi

KORIJEN = Path(__file__).resolve().parents[1]
PROFIL = profil.ucitaj((KORIJEN / "profili" / "vjezba_1.toml").read_bytes())
VRIJEME = "15.10.2026. 12:30"

SPREMAN = Student(1, "0012345678", "Ana", "Horvat", True)
NESPREMAN = Student(2, "0023456789", "Ivan", "Šašić", True)
NIJE_PREDAO = Student(3, "0034567890", "Petra", "Kovač", True)
ISPISAN = Student(4, "0045678901", "Marko", "Babić", False)
RUCNI = Student(5, "0056789012", "Lea", "Marić", True)
FORMAT = Student(6, "0067890123", "Toni", "Jurić", True)
STUDENTI = (SPREMAN, NESPREMAN, NIJE_PREDAO, ISPISAN, RUCNI, FORMAT)


def _nalaz(pravilo_id, status, isjecak=None):
    return Nalaz(
        pravilo_id, status, Lokacija(Dio.TIJELO, 2, 7, isjecak), "opce.neprovjerljivo",
        ocekivano=Vrijednost(1134, Jedinica.TWIPS), pronadeno=Vrijednost(1417, Jedinica.TWIPS),
        parametri={"razlog": "test"},
    )


def _izvjestaj(*nalazi, odbijeno=None):
    return Izvjestaj(odbijeno, tuple(nalazi), "abcd1234", 1)


def _svi_prosli():
    return [_nalaz(p, Status.PROSLO) for p in REGISTAR]


def _rezultat():
    datoteke = (
        RedakDatoteke("=1+1.docx", SPREMAN, NacinUparivanja.TOCAN, _izvjestaj(*_svi_prosli())),
        RedakDatoteke(
            "Ivan_Šašić.docx", NESPREMAN, NacinUparivanja.PRIBLIZAN,
            _izvjestaj(*_svi_prosli()[1:], _nalaz("R-NAZIV", Status.NE_PROLAZI, "@SUM(A1)")),
        ),
        RedakDatoteke(
            "Lea.docx", RUCNI, NacinUparivanja.TOCAN,
            _izvjestaj(*_svi_prosli()[:-1], _nalaz("R-OKVIRI", Status.NEPROVJERLJIVO)),
        ),
        RedakDatoteke(
            "Toni.pdf", FORMAT, NacinUparivanja.TOCAN,
            _izvjestaj(odbijeno=RazlogOdbijanja.NEISPRAVAN_FORMAT),
        ),
        RedakDatoteke(
            "-rad.docx", nepovezano=RazlogNepovezanosti.DVOSMISLENO, kandidati=(SPREMAN, NESPREMAN)
        ),
    )
    return RezultatBatcha("abcd1234", STUDENTI, datoteke)


def _list(tablica, naziv):
    (list_,) = [l for l in tablica.listovi if l.naziv == naziv]
    return list_


def _po_rbr(list_):
    return {r[0]: dict(zip(list_.stupci, r)) for r in list_.retci}


def test_rezultati_po_aktivnom_studentu():
    rezultati = _list(izradi(_rezultat(), PROFIL, VRIJEME), "Rezultati")
    assert list(rezultati.stupci[:6]) == [
        "Rbr.", "Ime", "Prezime", "JMBAG", "Naziv datoteke", "Ukupni status",
    ]
    assert list(rezultati.stupci[6:-1]) == list(REGISTAR)
    assert rezultati.stupci[-1] == "Broj nalaza koji ne prolaze"
    retci = _po_rbr(rezultati)
    assert sorted(retci) == [1, 2, 3, 5, 6]  # neaktivni (4) nije u tablici
    assert retci[1]["Ukupni status"] == "spremno"
    assert retci[1]["Naziv datoteke"] == "=1+1.docx"
    assert retci[1]["R-NAZIV"] == "prošlo"
    assert retci[1]["Broj nalaza koji ne prolaze"] == 0
    assert retci[2]["Ukupni status"] == "nije spremno"
    assert retci[2]["R-NAZIV"] == "ne prolazi"
    assert retci[2]["Broj nalaza koji ne prolaze"] == 1
    assert retci[3]["Ukupni status"] == "nije predao"
    assert retci[3]["Naziv datoteke"] == "" and retci[3]["R-NAZIV"] == ""
    assert retci[5]["Ukupni status"] == "za ručni pregled"
    assert retci[5]["R-OKVIRI"] == "neprovjerljivo"
    assert retci[6]["Ukupni status"] == "neispravan format"


def test_iskljuceno_pravilo_nema_stupac():
    sadrzaj = (KORIJEN / "profili" / "vjezba_1.toml").read_text(encoding="utf-8")
    staro = "[pravila.R-LITERATURA]\nukljuceno = true"
    assert staro in sadrzaj
    sadrzaj = sadrzaj.replace(staro, "[pravila.R-LITERATURA]\nukljuceno = false", 1)
    bez = profil.ucitaj(sadrzaj.encode("utf-8"))
    rezultati = _list(izradi(_rezultat(), bez, VRIJEME), "Rezultati")
    assert "R-LITERATURA" not in rezultati.stupci


def test_nalazi_samo_ne_prolazi_i_neprovjerljivo():
    nalazi = _list(izradi(_rezultat(), PROFIL, VRIJEME), "Nalazi")
    assert list(nalazi.stupci) == [
        "Rbr.", "Pravilo", "Status", "Lokacija", "Očekivano", "Pronađeno", "Opis", "Pojave",
    ]
    po_rbr = [(r[0], r[1], r[2]) for r in nalazi.retci]
    assert po_rbr == [
        (2, "R-NAZIV", "ne prolazi"),
        (5, "R-OKVIRI", "neprovjerljivo"),
        (6, "", "neispravan format"),
    ]
    naziv = dict(zip(nalazi.stupci, nalazi.retci[0]))
    assert naziv["Očekivano"] == "2 cm" and naziv["Pronađeno"] == "2,5 cm"
    assert "@SUM(A1)" in naziv["Lokacija"]
    assert dict(zip(nalazi.stupci, nalazi.retci[2]))["Opis"] == "datoteka nije .docx"


def test_nepovezano_s_kandidatima():
    nepovezano = _list(izradi(_rezultat(), PROFIL, VRIJEME), "Nepovezano")
    assert nepovezano.retci == (
        ("-rad.docx", "dvosmisleno – datoteka odgovara više studenata, a JMBAG ih ne razlučuje",
         "1. Ana Horvat; 2. Ivan Šašić"),
    )


def test_zaglavlje_na_svakom_listu():
    tablica = izradi(_rezultat(), PROFIL, VRIJEME)
    assert [l.naziv for l in tablica.listovi] == ["Rezultati", "Nalazi", "Nepovezano"]
    for list_ in tablica.listovi:
        assert list_.zaglavlje == (
            "Vježba", "Vježba 1", "Verzija profila", "abcd1234", "Vrijeme provjere", VRIJEME,
        )


def test_neuspjela_obrada_ima_redak_razloga():
    pukla = Student(7, "0078901234", "Ena", "Perić", True)
    rezultat = RezultatBatcha(
        "abcd1234", (pukla,),
        (RedakDatoteke("Ena.docx", pukla, NacinUparivanja.TOCAN, greska="RuntimeError"),),
    )
    tablica = izradi(rezultat, PROFIL, VRIJEME)
    redak = _po_rbr(_list(tablica, "Rezultati"))[7]
    assert redak["Ukupni status"] == "neuspjela obrada"
    assert redak["R-NAZIV"] == "" and redak["Broj nalaza koji ne prolaze"] == ""
    assert _list(tablica, "Nalazi").retci == (
        (7, "", "neuspjela obrada", "", "", "", "neočekivana greška pri obradi (RuntimeError)", ""),
    )


def test_odbijena_datoteka_nema_broj_nalaza():
    retci = _po_rbr(_list(izradi(_rezultat(), PROFIL, VRIJEME), "Rezultati"))
    assert retci[6]["Broj nalaza koji ne prolaze"] == ""

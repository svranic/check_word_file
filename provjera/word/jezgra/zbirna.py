"""Sadržaj Excel zbirne tablice (priča 4.3, FR27): čiste funkcije bez I/O-a.

Adapter ``excel_izlaz`` samo zapisuje ovo u radnu knjigu. Statusi dolaze isključivo iz
``ukupni_status`` i ``status_pravila``, a prikaz vrijednosti iz ``poruke``.
"""

from dataclasses import dataclass

from provjera.word.jezgra.nalaz import Izvjestaj, Status
from provjera.word.jezgra.poruke import formatiraj, opis_lokacije, poruka, tekst_nalaza
from provjera.word.jezgra.pravila import REGISTAR
from provjera.word.jezgra.predaje import (
    RedakDatoteke,
    RezultatBatcha,
    opis_kandidata,
    opis_razloga,
    opis_statusa,
)
from provjera.word.jezgra.profil import Profil
from provjera.word.jezgra.provjera import status_pravila

Celija = str | int


@dataclass(frozen=True)
class List:
    naziv: str
    zaglavlje: tuple[Celija, ...]  # naziv vježbe, verzija profila, vrijeme provjere
    stupci: tuple[str, ...]
    retci: tuple[tuple[Celija, ...], ...]


@dataclass(frozen=True)
class ZbirnaTablica:
    listovi: tuple[List, ...]


def _status_pravila(status: Status | None) -> str:
    """„prošlo“, „ne prolazi“, „neprovjerljivo“ bez ikone; prazno ako pravila nema."""
    if status is None:
        return ""
    return poruka(f"status.{status.value}").partition(" ")[2]


def _broj_ne_prolazi(izvjestaj: Izvjestaj | None) -> Celija:
    # Odbijena datoteka nije provjerena: prazno, a ne 0 kao kod ispravnog rada.
    if izvjestaj is None or izvjestaj.odbijeno is not None:
        return ""
    return sum(n.pojave for n in izvjestaj.nalazi if n.status is Status.NE_PROLAZI)


def _vrijednost(v) -> str:
    return "" if v is None else formatiraj(v.iznos, v.jedinica)


def _nalazi(rbr: int, datoteka: RedakDatoteke) -> list[tuple[Celija, ...]]:
    razlog = opis_razloga(datoteka)
    if razlog is not None or datoteka.izvjestaj is None:
        status = opis_statusa(datoteka.status, ikona=False) if datoteka.status else ""
        return [(rbr, "", status, "", "", "", razlog or "", "")]
    return [
        (
            rbr,
            n.pravilo_id,
            _status_pravila(n.status),
            opis_lokacije(n.lokacija),
            _vrijednost(n.ocekivano),
            _vrijednost(n.pronadeno),
            tekst_nalaza(n),
            n.pojave,
        )
        for n in datoteka.izvjestaj.nalazi
        if n.status is not Status.PROSLO
    ]


def izradi(rezultat: RezultatBatcha, profil: Profil, vrijeme: str) -> ZbirnaTablica:
    """``vrijeme`` je već formatirano vrijeme provjere (``dd.mm.gggg. hh:mm``) iz adaptera."""
    zaglavlje = (
        poruka("zbirna.vjezba"), profil.vjezba.naziv,
        poruka("zbirna.verzija"), rezultat.profil_verzija,
        poruka("zbirna.vrijeme"), vrijeme,
    )
    pravila = [
        pravilo_id for pravilo_id, pravilo in REGISTAR.items()
        if (profil.pravila.get(pravilo_id) or pravilo.postavke()).ukljuceno
    ]
    rezultati: list[tuple[Celija, ...]] = []
    nalazi: list[tuple[Celija, ...]] = []
    for student in sorted((s for s in rezultat.studenti if s.aktivan), key=lambda s: s.rbr):
        datoteka = rezultat.datoteka_studenta(student)
        izvjestaj = None if datoteka is None else datoteka.izvjestaj
        statusi = [
            _status_pravila(status_pravila(izvjestaj.nalazi, p) if izvjestaj else None)
            for p in pravila
        ]
        rezultati.append(
            (
                student.rbr, student.ime, student.prezime, student.jmbag,
                "" if datoteka is None else datoteka.relativno,
                opis_statusa(rezultat.status_studenta(student), ikona=False),
                *statusi,
                _broj_ne_prolazi(izvjestaj),
            )
        )
        if datoteka is not None:
            nalazi += _nalazi(student.rbr, datoteka)
    nepovezane = [
        (d.relativno, opis_razloga(d) or "", opis_kandidata(d))
        for d in rezultat.datoteke
        if d.student is None
    ]
    return ZbirnaTablica(
        (
            List(
                poruka("zbirna.list_rezultati"),
                zaglavlje,
                (
                    poruka("zbirna.stupac_rbr"), poruka("zbirna.stupac_ime"),
                    poruka("zbirna.stupac_prezime"), poruka("zbirna.stupac_jmbag"),
                    poruka("zbirna.stupac_datoteka"), poruka("zbirna.stupac_ukupni_status"),
                    *pravila,
                    poruka("zbirna.stupac_broj_nalaza"),
                ),
                tuple(rezultati),
            ),
            List(
                poruka("zbirna.list_nalazi"),
                zaglavlje,
                (
                    poruka("zbirna.stupac_rbr"), poruka("zbirna.stupac_pravilo"),
                    poruka("zbirna.stupac_status"), poruka("zbirna.stupac_lokacija"),
                    poruka("zbirna.stupac_ocekivano"), poruka("zbirna.stupac_pronadeno"),
                    poruka("zbirna.stupac_opis"), poruka("zbirna.stupac_pojave"),
                ),
                tuple(nalazi),
            ),
            List(
                poruka("zbirna.list_nepovezano"),
                zaglavlje,
                (
                    poruka("zbirna.stupac_datoteka"), poruka("zbirna.stupac_razlog"),
                    poruka("zbirna.stupac_kandidati"),
                ),
                tuple(nepovezane),
            ),
        )
    )

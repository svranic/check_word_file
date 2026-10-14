"""Samoprovjera profila (priča 3.4): čita referentni skup ``<mapa>/<vjezba.id>/``.

Svaki primjer (``.docx`` s zapisom u ``[primjeri]`` iz ``ocekivano.toml``) provjerava se
istom jezgrom kao web (``provjeri`` i ``status_pravila``), a usporedbu radi
``provjera.jezgra.samoprovjera``. Referentni skup se ovdje samo čita, nikad ne mijenja.
"""

import hashlib
import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from provjera.jezgra.nalaz import KontekstProvjere, Status
from provjera.jezgra.pravila import REGISTAR
from provjera.jezgra.profil import Profil
from provjera.jezgra.provjera import provjeri, status_pravila
from provjera.jezgra.samoprovjera import RezultatPrimjera, neuspjeli, usporedi

OCEKIVANO = "ocekivano.toml"
NASTAVAK = ".docx"


class GreskaReferentnog(Exception):
    """Referentni skup za vježbu ne postoji ili je ``ocekivano.toml`` neispravan."""

    def __init__(
        self, poruka_kljuc: str, parametri: Mapping[str, str | int] | None = None
    ) -> None:
        super().__init__(poruka_kljuc)
        self.poruka_kljuc = poruka_kljuc
        self.parametri: Mapping[str, str | int] = MappingProxyType(dict(parametri or {}))


def _procitaj_ocekivano(mapa: Path) -> tuple[int, str, dict[str, frozenset[str]]]:
    putanja = mapa / OCEKIVANO
    if not mapa.is_dir():
        raise GreskaReferentnog("samoprovjera.nema_skupa", {"mapa": str(mapa)})
    if not putanja.is_file():
        raise GreskaReferentnog("samoprovjera.nema_ocekivanog", {"putanja": str(putanja)})
    try:
        podaci = tomllib.loads(putanja.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as greska:
        raise GreskaReferentnog(
            "samoprovjera.ocekivano_neispravno", {"putanja": str(putanja)}
        ) from greska
    rbr, naziv, primjeri = podaci.get("rbr"), podaci.get("naziv"), podaci.get("primjeri")
    ispravno = (
        isinstance(rbr, int)
        and not isinstance(rbr, bool)
        and rbr > 0
        and isinstance(naziv, str)
        and isinstance(primjeri, dict)
        and all(
            isinstance(zapis, dict)
            and isinstance(zapis.get("padaju"), list)
            and all(isinstance(p, str) for p in zapis["padaju"])
            for zapis in primjeri.values()
        )
    )
    if not ispravno:
        raise GreskaReferentnog("samoprovjera.ocekivano_neispravno", {"putanja": str(putanja)})
    nepoznata = sorted({p for z in primjeri.values() for p in z["padaju"]} - set(REGISTAR))
    if nepoznata:
        raise GreskaReferentnog(
            "samoprovjera.nepoznato_pravilo",
            {"putanja": str(putanja), "pravila": ", ".join(nepoznata)},
        )
    return rbr, naziv, {ime: frozenset(z["padaju"]) for ime, z in primjeri.items()}


def _primjeri(mapa: Path) -> dict[str, Path]:
    """``.docx`` primjeri bez Wordovih datoteka zaključavanja (``~$``) i skrivenih datoteka."""
    try:
        return {
            p.stem: p
            for p in mapa.glob(f"*{NASTAVAK}")
            if not p.name.startswith(("~$", ".")) and p.is_file()
        }
    except OSError as greska:
        raise GreskaReferentnog("samoprovjera.mapa_necitljiva", {"mapa": str(mapa)}) from greska


def _pronadeno(
    sadrzaj: bytes, profil: Profil, kontekst: KontekstProvjere
) -> frozenset[str] | str:
    """Skup pravila koja ne prolaze, ili razlog odbijanja dokumenta."""
    izvjestaj = provjeri(sadrzaj, profil, kontekst)
    if izvjestaj.odbijeno is not None:
        return str(izvjestaj.odbijeno.value)
    return frozenset(
        pid
        for pid in {n.pravilo_id for n in izvjestaj.nalazi}
        if status_pravila(izvjestaj.nalazi, pid) is not Status.PROSLO
    )


def otisak_skupa(vjezba_id: str, mapa_referentnog: Path) -> str:
    """Otisak referentnog skupa: ``ocekivano.toml`` i (ime, veličina, mtime) primjera.

    Promjena skupa mijenja otisak, pa aplikacija odbacuje stari rezultat samoprovjere.
    """
    mapa = mapa_referentnog / vjezba_id
    sazetak = hashlib.sha256()
    try:
        sazetak.update((mapa / OCEKIVANO).read_bytes())
        for ime, putanja in sorted(_primjeri(mapa).items()):
            stanje = putanja.stat()
            sazetak.update(f"|{ime}|{stanje.st_size}|{stanje.st_mtime_ns}".encode())
    except (OSError, GreskaReferentnog):
        return "nedostupan"
    return sazetak.hexdigest()[:16]


def pokreni(profil: Profil, mapa_referentnog: Path) -> tuple[RezultatPrimjera, ...]:
    """Provjerava sve primjere za ``profil.vjezba.id``; rezultati su poredani po imenu."""
    mapa = mapa_referentnog / profil.vjezba.id
    rbr, naziv, ocekivano = _procitaj_ocekivano(mapa)
    datoteke = _primjeri(mapa)
    # Isto kao pokretač pravila: pravilo bez odjeljka u profilu ima zadane postavke.
    ukljucena = frozenset(
        pid
        for pid, pravilo in REGISTAR.items()
        if (profil.pravila.get(pid) or pravilo.postavke()).ukljuceno
    )
    kontekst = KontekstProvjere(naziv, rbr, None, None)
    rezultati = []
    for ime in sorted(set(ocekivano) | set(datoteke)):
        if ime not in ocekivano:
            rezultati.append(neuspjeli(ime, None, "samoprovjera.nema_zapisa"))
            continue
        if ime not in datoteke:
            rezultati.append(neuspjeli(ime, ocekivano[ime], "samoprovjera.nema_datoteke"))
            continue
        try:
            sadrzaj = datoteke[ime].read_bytes()
        except OSError:
            rezultati.append(neuspjeli(ime, ocekivano[ime], "samoprovjera.necitljiv"))
            continue
        try:
            pronadeno = _pronadeno(sadrzaj, profil, kontekst)
        except MemoryError:
            raise
        except Exception as greska:  # noqa: BLE001 — jedan primjer ne prekida samoprovjeru
            rezultati.append(
                neuspjeli(
                    ime,
                    ocekivano[ime],
                    "samoprovjera.greska_provjere",
                    {"razlog": type(greska).__name__},
                )
            )
            continue
        if isinstance(pronadeno, str):
            rezultati.append(
                neuspjeli(ime, ocekivano[ime], "samoprovjera.odbijeno", {"razlog": pronadeno})
            )
        else:
            rezultati.append(usporedi(ime, ocekivano[ime], pronadeno, ukljucena))
    return tuple(rezultati)

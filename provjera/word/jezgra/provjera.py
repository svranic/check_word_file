"""Pokretač provjere (AD-1, AD-4, AD-5): jedina ulazna točka i jedine agregacije."""

from dataclasses import replace
from enum import Enum

from provjera.word.jezgra import model
from provjera.zajednicko import ulaz
from provjera.word.jezgra.nalaz import Dio, Izvjestaj, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.word.jezgra.poruke import opis_lokacije, poruka, tekst_nalaza
from provjera.word.jezgra.pravila import REGISTAR
from provjera.word.jezgra.profil import Profil, verzija
from provjera.zajednicko.ulaz import RazlogOdbijanja

NAJVISE_PRIMJERA = 3
_POREDAK = {Status.PROSLO: 0, Status.NE_PROLAZI: 1, Status.NEPROVJERLJIVO: 2}


def _neprovjerljivo(pravilo_id: str, razlog: str) -> Nalaz:
    return Nalaz(
        pravilo_id=pravilo_id,
        status=Status.NEPROVJERLJIVO,
        lokacija=Lokacija(Dio.DOKUMENT),
        poruka_kljuc="opce.neprovjerljivo",
        parametri={"razlog": razlog},
    )


def _prikaziv(nalaz: Nalaz) -> bool:
    """Nalaz čiji se tekst ne može složiti (nepoznat ključ, parametar) srušio bi cijeli
    izvještaj pri prikazu; zato postaje neprovjerljiv već ovdje."""
    try:
        tekst_nalaza(nalaz)
        poruka(f"pravilo.{nalaz.pravilo_id}")
        opis_lokacije(nalaz.lokacija)
    except Exception:  # noqa: BLE001 — bilo koja greška teksta je greška pravila
        return False
    return True


def _sazmi(nalazi: list[Nalaz]) -> list[Nalaz]:
    """Spaja ponavljanja istog nalaza u jedan, uz prvu lokaciju, zbroj pojava i primjere.

    ``primjeri`` sadrže do ``NAJVISE_PRIMJERA`` različitih lokacija spojenih nalaza,
    uključujući prvu; nalaz bez ponavljanja ostaje nepromijenjen.
    """
    grupe: dict[tuple, Nalaz] = {}
    for n in nalazi:
        kljuc = (
            n.pravilo_id, n.status, n.poruka_kljuc, n.ocekivano, n.pronadeno, n.izvor,
            tuple(sorted(n.parametri.items())),
        )
        if kljuc in grupe:
            prvi = grupe[kljuc]
            primjeri = list(prvi.primjeri or (prvi.lokacija,))
            for lokacija in n.primjeri or (n.lokacija,):
                if len(primjeri) < NAJVISE_PRIMJERA and lokacija not in primjeri:
                    primjeri.append(lokacija)
            grupe[kljuc] = replace(prvi, pojave=prvi.pojave + n.pojave, primjeri=tuple(primjeri))
        else:
            grupe[kljuc] = n
    return list(grupe.values())


def provjeri(docx: bytes, profil: Profil, kontekst: KontekstProvjere) -> Izvjestaj:
    razlog = ulaz.provjeri_ulaz(kontekst.naziv_datoteke, docx)
    if razlog:
        return Izvjestaj(razlog, (), verzija(profil), kontekst.rbr)

    # MemoryError je preopterećenje instance, ne svojstvo dokumenta: propušta se pozivatelju.
    razlog_modela = None
    try:
        dokument = model.procitaj(docx, profil.uloge)
    except model.NeispravanDokument:
        return Izvjestaj(ulaz.RazlogOdbijanja.OSTECENA, (), verzija(profil), kontekst.rbr)
    except MemoryError:
        raise
    except model.NepodrzaniDokument as greska:
        dokument, razlog_modela = None, str(greska)
    except Exception as greska:  # noqa: BLE001 — pravila koja trebaju model postaju neprovjerljiva
        dokument, razlog_modela = None, type(greska).__name__

    nalazi: list[Nalaz] = []
    for pravilo_id, pravilo in REGISTAR.items():
        postavke = profil.pravila.get(pravilo_id) or pravilo.postavke()
        if not postavke.ukljuceno:
            continue
        try:
            rezultat = list(pravilo.funkcija(dokument, kontekst, postavke, profil))
            if not rezultat:
                rezultat = [_neprovjerljivo(pravilo_id, "pravilo nije vratilo nalaz")]
            if not all(isinstance(n, Nalaz) and n.pravilo_id == pravilo_id for n in rezultat):
                rezultat = [_neprovjerljivo(pravilo_id, "neispravan rezultat pravila")]
            elif not all(_prikaziv(n) for n in rezultat):
                rezultat = [_neprovjerljivo(pravilo_id, "neispravan tekst nalaza")]
            rezultat = _sazmi(rezultat)
        except MemoryError:
            raise
        except Exception as greska:  # noqa: BLE001 — iznimka nikad ne smije dati prolaz
            # Bez modela pravilo koje ga treba pada; razlog je ono što je model spriječilo.
            razlog = razlog_modela if dokument is None else type(greska).__name__
            rezultat = [_neprovjerljivo(pravilo_id, razlog)]
        nalazi += rezultat
    return Izvjestaj(None, tuple(nalazi), verzija(profil), kontekst.rbr)


def status_pravila(nalazi: tuple[Nalaz, ...], pravilo_id: str) -> Status | None:
    statusi = [n.status for n in nalazi if n.pravilo_id == pravilo_id]
    return max(statusi, key=_POREDAK.__getitem__) if statusi else None


def spremnost(izvjestaj: Izvjestaj) -> bool:
    return (
        izvjestaj.odbijeno is None
        and bool(izvjestaj.nalazi)
        and all(n.status is Status.PROSLO for n in izvjestaj.nalazi)
    )


class UkupniStatus(Enum):
    SPREMNO = "SPREMNO"
    NIJE_SPREMNO = "NIJE_SPREMNO"
    ZA_RUCNI_PREGLED = "ZA_RUCNI_PREGLED"
    NIJE_PREDAO = "NIJE_PREDAO"
    NEISPRAVAN_FORMAT = "NEISPRAVAN_FORMAT"
    NEUSPJELA_OBRADA = "NEUSPJELA_OBRADA"
    NEAKTIVAN = "NEAKTIVAN"


# Odbijanja zbog vrste datoteke; ostala znače da se datoteka nije mogla obraditi.
_ODBIJANJA_FORMATA = frozenset(
    {RazlogOdbijanja.NEISPRAVAN_FORMAT, RazlogOdbijanja.STARI_DOC, RazlogOdbijanja.MAKRO}
)


def ukupni_status(izvjestaj: Izvjestaj | None, ima_datoteku: bool, aktivan: bool) -> UkupniStatus:
    """Status studenta u batchu; ``izvjestaj`` je ``None`` kad datoteke nema ili je provjera pukla."""
    if not aktivan:
        return UkupniStatus.NEAKTIVAN
    if not ima_datoteku:
        return UkupniStatus.NIJE_PREDAO
    if izvjestaj is None:
        return UkupniStatus.NEUSPJELA_OBRADA
    if izvjestaj.odbijeno is not None:
        if izvjestaj.odbijeno in _ODBIJANJA_FORMATA:
            return UkupniStatus.NEISPRAVAN_FORMAT
        return UkupniStatus.NEUSPJELA_OBRADA
    if any(n.status is Status.NEPROVJERLJIVO for n in izvjestaj.nalazi):
        return UkupniStatus.ZA_RUCNI_PREGLED
    return UkupniStatus.SPREMNO if spremnost(izvjestaj) else UkupniStatus.NIJE_SPREMNO

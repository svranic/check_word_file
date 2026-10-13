"""Pokretač provjere (AD-1, AD-4, AD-5): jedina ulazna točka i jedine agregacije."""

from dataclasses import replace

from provjera.jezgra import model, ulaz
from provjera.jezgra.nalaz import Dio, Izvjestaj, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.jezgra.pravila import REGISTAR
from provjera.jezgra.profil import Profil, verzija

_POREDAK = {Status.PROSLO: 0, Status.NE_PROLAZI: 1, Status.NEPROVJERLJIVO: 2}


def _neprovjerljivo(pravilo_id: str, razlog: str) -> Nalaz:
    return Nalaz(
        pravilo_id=pravilo_id,
        status=Status.NEPROVJERLJIVO,
        lokacija=Lokacija(Dio.DOKUMENT),
        poruka_kljuc="opce.neprovjerljivo",
        parametri={"razlog": razlog},
    )


def _sazmi(nalazi: list[Nalaz]) -> list[Nalaz]:
    """Spaja ponavljanja istog nalaza u jedan, uz prvu lokaciju i zbroj pojava."""
    grupe: dict[tuple, Nalaz] = {}
    for n in nalazi:
        kljuc = (
            n.pravilo_id, n.status, n.poruka_kljuc, n.ocekivano, n.pronadeno, n.izvor,
            tuple(sorted(n.parametri.items())),
        )
        if kljuc in grupe:
            prvi = grupe[kljuc]
            grupe[kljuc] = replace(prvi, pojave=prvi.pojave + n.pojave)
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

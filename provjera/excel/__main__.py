"""Naredbeni redak Excel vježbi.

    uv run python -m provjera.excel predlozak profili/excel/vjezba_2.toml izlaz/
    uv run python -m provjera.excel predlozak profili/excel/vjezba_2.toml izlaz/ --popis isvu.xlsx
    uv run python -m provjera.excel predlozak profili/excel/vjezba_2.toml izlaz/ --rjesenje
    uv run python -m provjera.excel provjeri profili/excel/vjezba_2.toml predaje/ --popis isvu.xlsx \
        --izvjestaj zbirno.xlsx

Bez ``--popis`` predložak je prazan (student sam upisuje podatke iz zadatka), a provjera
uspoređuje ulazne podatke samo ako ih je izdao osobni predložak.

Listovi i struktura predloška zaštićeni su lozinkom (``--lozinka``; bez nje lozinka iz
profila, a ako je i ona prazna, slučajna lozinka koja se zapisuje u izlaznu mapu u
LOZINKA_ZASTITE.txt). Lozinka nije potrebna za provjeru.
"""

import argparse
import secrets
import sys
from pathlib import Path

from provjera.excel.adapteri import predlozak, skupno
from provjera.excel.adapteri.predlozak import StudentPredloska
from provjera.excel.jezgra import profil as profil_modul
from provjera.excel.jezgra.provjera import provjeri


def _studenti(putanja: Path | None) -> list[StudentPredloska]:
    if putanja is None:
        return []
    # ISVU izvoz čita isti čitač kao i Word vježbe.
    from provjera.word.adapteri.popis import ucitaj_isvu

    ucitano = ucitaj_isvu(putanja.read_bytes())
    for greska in ucitano.greske:
        print(f"Upozorenje (redak {greska.redak}): {greska.poruka_kljuc}", file=sys.stderr)
    return [StudentPredloska(s.ime, s.prezime, s.jmbag) for s in ucitano.studenti if s.aktivan]


def _lozinka(args: argparse.Namespace, profil) -> str:
    if args.lozinka:
        return args.lozinka
    if profil.zadaci.lozinka:
        return profil.zadaci.lozinka
    lozinka = secrets.token_urlsafe(9)
    (args.izlaz / "LOZINKA_ZASTITE.txt").write_text(
        f"Lozinka zaštite listova i strukture predložaka u ovoj mapi: {lozinka}\n", encoding="utf-8")
    print(f"Lozinka zaštite zapisana je u {args.izlaz / 'LOZINKA_ZASTITE.txt'}")
    return lozinka


def _predlozak(args: argparse.Namespace) -> int:
    profil = profil_modul.ucitaj(args.profil.read_bytes())
    args.izlaz.mkdir(parents=True, exist_ok=True)
    lozinka = _lozinka(args, profil)
    if args.rjesenje:
        putanja = args.izlaz / f"RJESENJE_{profil.vjezba.id}.xlsx"
        putanja.write_bytes(predlozak.izradi(profil, rjesenje=True, lozinka=lozinka))
        print(f"Rješenje: {putanja}")
        return 0
    studenti = _studenti(args.popis)
    if studenti:
        putanje = predlozak.izradi_za_studente(profil, studenti, args.izlaz, lozinka)
        print(f"Izrađeno {len(putanje)} osobnih predložaka u {args.izlaz}")
    else:
        putanja = args.izlaz / f"Predlozak{profil.naziv_datoteke.sufiks}.xlsx"
        putanja.write_bytes(predlozak.izradi(profil, lozinka=lozinka))
        print(f"Predložak: {putanja}")
    return 0


def _provjeri(args: argparse.Namespace) -> int:
    profil = profil_modul.ucitaj(args.profil.read_bytes())
    studenti = _studenti(args.popis)
    if args.ulaz.is_file():
        prvi = provjeri(args.ulaz.name, args.ulaz.read_bytes(), profil)
        student = skupno.upari(args.ulaz, profil, studenti, prvi.jmbag_iz_datoteke) if studenti else None
        izvjestaj = provjeri(args.ulaz.name, args.ulaz.read_bytes(), profil, student.jmbag,
                             studenti.index(student)) if student else prvi
        print(skupno.tekst_izvjestaja(izvjestaj))
        return 0
    predaje = skupno.provjeri_mapu(args.ulaz, profil, studenti)
    for p in predaje:
        print(skupno.tekst_izvjestaja(p.izvjestaj) if args.detaljno else
              f"{p.izvjestaj.status.value:15} {p.putanja.name}")
    for koef, a, b in skupno.slicni_parovi(predaje):
        print(f"Slične formule ({koef:.0%}): {a.putanja.name} ↔ {b.putanja.name}")
    if args.izvjestaj:
        args.izvjestaj.write_bytes(skupno.zbirni_izvjestaj(predaje))
        print(f"Zbirni izvještaj: {args.izvjestaj}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows konzola nije uvijek UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m provjera.excel", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    pod = parser.add_subparsers(dest="naredba", required=True)

    p = pod.add_parser("predlozak", help="izradi predložak (prazan, osobne ili rješenje)")
    p.add_argument("profil", type=Path)
    p.add_argument("izlaz", type=Path, help="mapa za predloške")
    p.add_argument("--popis", type=Path, help="ISVU izvoz (.xlsx): osobni predložak za svakog studenta")
    p.add_argument("--rjesenje", action="store_true", help="predložak s referentnim formulama")
    p.add_argument("--lozinka", help="lozinka zaštite listova i strukture (ne upisuj je u profil u gitu)")
    p.set_defaults(funkcija=_predlozak)

    p = pod.add_parser("provjeri", help="provjeri datoteku ili mapu predaja")
    p.add_argument("profil", type=Path)
    p.add_argument("ulaz", type=Path, help="predana .xlsx datoteka ili mapa predaja")
    p.add_argument("--popis", type=Path, help="ISVU izvoz (.xlsx) za uparivanje i provjeru ulaznih podataka")
    p.add_argument("--izvjestaj", type=Path, help="zbirni izvještaj (.xlsx) za mapu")
    p.add_argument("--detaljno", action="store_true", help="ispiši sve stavke svake predaje")
    p.set_defaults(funkcija=_provjeri)

    args = parser.parse_args(argv)
    return args.funkcija(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Generator sintetskih ISVU izvoza popisa studenata (priča 3.1).

Oblik prati stvarni izvoz: 14 redaka metapodataka, prazan 15. redak, zaglavlje u
16. retku i sve vrijednosti kao tekst („1.“, JMBAG s vodećim nulama). Imena,
JMBAG-ovi i e-mailovi su izmišljeni.

Pokretanje: ``uv run python tests/alati/isvu.py`` zapisuje fixture u ``tests/fixtures/``.
"""

import io
from collections.abc import Sequence
from pathlib import Path

import openpyxl

KORIJEN = Path(__file__).resolve().parents[2]
MAPA = KORIJEN / "tests" / "fixtures"

ZAGLAVLJE = (
    "Rbr.",
    "JMBAG",
    "Ime",
    "Prezime",
    "E-mail na VU",
    "E-mail",
    "E-mail aktivan",
    "Smjer",
    "Način izvedbe",
    "Status upisa",
    "Dolazna mobilnost",
    "Status predmeta",
)
METAPODACI = (
    ("Popis studenata na predmetu",),
    ("Visoko učilište:", "Izmišljeno sveučilište"),
    ("Akademska godina:", "2026/2027"),
    ("Predmet:", "Osnove geoinformatike"),
    ("Šifra predmeta:", "000000"),
    ("Nositelj:", "Izmišljeni Nastavnik"),
    ("Semestar:", "zimski"),
    ("Izvedba:", "redovni"),
    ("Datum izvoza:", "01.10.2026."),
    ("Broj studenata:", "—"),
    ("Studij:", "Geodezija i geomatika"),
    ("Grupa:", "sve"),
    ("Napomena:", "sintetski podaci"),
    ("Izvor:", "ISVU"),
)
UPISAN = "upisan u tekuću ak. god."
ISPISAN = "ispisan - nije završio studij"

# (Rbr., JMBAG, Ime, Prezime, Status upisa)
Redak = tuple[object, object, object, object, object]

ISPRAVNI: tuple[Redak, ...] = (
    ("1.", "0036123456", "Ana Marija", "Horvat-Kovač", UPISAN),
    ("2.", "0036000002", "Đuro", "Šimić", UPISAN),
    ("3.", "0036000003", "Ivana", "Žužić", ISPISAN),
    ("4.", "0036000004", "Luka", "Čačić", UPISAN),
    ("5.", "0036000005", "Petra", "Ćosić", UPISAN),
)

S_GRESKAMA: tuple[Redak, ...] = (
    ("1.", "0036000001", "Ana", "Horvat", UPISAN),
    ("a", "0036000002", "Ivo", "Babić", UPISAN),
    ("0", "0036000003", "Eva", "Perić", UPISAN),
    ("5.", "0036000005", "Marko", "Novak", UPISAN),
    ("5.", "0036000006", "Maja", "Kos", UPISAN),
    ("7.", "0036000001", "Tea", "Jurić", UPISAN),
    ("8.", "", "Nina", "Vuk", UPISAN),
    ("9.", "0036000009", "", "Lovrić", UPISAN),
    ("10.", "0036000010", "Dino", "  ", UPISAN),
)


def izvoz(
    retci: Sequence[Redak],
    *,
    metapodaci: bool = True,
    zaglavlje: Sequence[str] = ZAGLAVLJE,
) -> bytes:
    """ISVU izvoz s danim retcima studenata; dodatni stupci popunjavaju se izmišljenim podacima."""
    knjiga = openpyxl.Workbook()
    list_ = knjiga.active
    list_.title = "Popis"
    if metapodaci:
        for redak in METAPODACI:
            list_.append(redak)
        list_.append(())  # prazan 15. redak
    list_.append(tuple(zaglavlje))
    for i, (rbr, jmbag, ime, prezime, status) in enumerate(retci, 1):
        dodatno = {
            "E-mail na VU": f"student{i}@primjer.invalid",
            "E-mail": f"osobni{i}@primjer.invalid",
            "E-mail aktivan": "Ne",
            "Smjer": "Geodezija i geomatika",
            "Način izvedbe": "redovni",
            "Dolazna mobilnost": "Ne",
            "Status predmeta": "upisana komponenta",
        }
        if all(v is None or not str(v).strip() for v in (rbr, jmbag, ime, prezime, status)):
            dodatno = {}  # prazan redak studenta je prazan u cijelosti
        vrijednosti = {
            "rbr.": rbr,
            "jmbag": jmbag,
            "ime": ime,
            "prezime": prezime,
            "status upisa": status,
        }
        list_.append(
            tuple(vrijednosti.get(s.strip().casefold(), dodatno.get(s)) for s in zaglavlje)
        )
    izlaz = io.BytesIO()
    knjiga.save(izlaz)
    return izlaz.getvalue()


def fixturei() -> dict[str, bytes]:
    return {
        "isvu_ispravan.xlsx": izvoz(ISPRAVNI),
        "isvu_greske.xlsx": izvoz(S_GRESKAMA),
    }


def main() -> None:
    MAPA.mkdir(parents=True, exist_ok=True)
    for naziv, sadrzaj in fixturei().items():
        (MAPA / naziv).write_bytes(sadrzaj)
        print(f"zapisano: {naziv}")


if __name__ == "__main__":
    main()

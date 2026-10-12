"""Katalog poruka (AD-11): jedini izvor teksta koji vidi korisnik.

Ključevi pravila imaju oblik ``<pravilo_id>.<slucaj>``; ostali tekst sučelja
koristi prefikse ``app.``, ``nastavnik.``, ``privatnost.``, ``profil.``,
``vjezba.``, ``rbr.``, ``margine.`` i ``naziv.``.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType

from provjera.jezgra.jedinice import Jedinica, twips_u_cm

KATALOG: Mapping[str, str] = MappingProxyType(
    {
        "app.naslov": "Provjera Word dokumenata",
        "app.podnaslov": (
            "Provjeri tehničko oblikovanje svoje zadaće prije predaje "
            "u sustav e-učenja."
        ),
        "privatnost.obrada": (
            "Tvoj dokument obrađuje se na poslužiteljima u SAD-u, samo u memoriji, "
            "i ništa se ne sprema: ni datoteka ni rezultat provjere."
        ),
        "nastavnik.naslov": "Provjera Word dokumenata – nastavnik",
        "profil.nedostupno": (
            "Provjera trenutno nije dostupna. Pokušaj kasnije ili se javi nastavniku."
        ),
        "profil.djelomicno_nedostupno": (
            "Provjera za neke vježbe trenutno nije dostupna. "
            "Ako tvoja vježba nije na popisu, javi se nastavniku."
        ),
        "vjezba.odabir": "Vježba",
        "rbr.oznaka": "Tvoj redni broj (Rbr.) iz PDF-a sa svojstvima",
        "rbr.primjer": "npr. 54",
        "vrijednost.da": "da",
        "vrijednost.ne": "ne",
        "rbr.potvrdi": "Prikaži moje margine",
        "rbr.prazno": "Upiši svoj redni broj, npr. 54.",
        "rbr.neispravno": "Redni broj mora biti pozitivan cijeli broj, npr. 54.",
        "rbr.prevelik": (
            "Redni broj {rbr} ne postoji za ovu vježbu (najveći je {najveci}). "
            "Provjeri broj u PDF-u sa svojstvima."
        ),
        "margine.naslov": "Tvoje margine za sekcije rada nakon naslovnice",
        "margine.gore": "Gore (Top)",
        "margine.dolje": "Dolje (Bottom)",
        "margine.lijevo": "Lijevo (Left)",
        "margine.desno": "Desno (Right)",
        "margine.uputa": (
            "U Wordu: Izgled (Layout) → Margine (Margins) → "
            "Prilagođene margine (Custom Margins)."
        ),
        "margine.naslovnica": "Naslovnica ima margine {naslovnica} sa svih strana.",
        "margine.usporedi": (
            "Provjeri jesu li margine iste kao u PDF-u sa svojstvima. "
            "Ako nisu, upisao si krivi redni broj."
        ),
        "ulaz.oznaka": "Učitaj svoj rad (.docx)",
        "ulaz.prihvaceno": "Datoteka je prošla provjeru formata (Word dokument .docx).",
        "ulaz.prazna": (
            "Datoteka je prazna (0 bajtova). Spremi rad ponovno u Wordu i učitaj ga."
        ),
        "ulaz.neispravan_format": (
            "Prihvaća se samo Word dokument (.docx). U Wordu odaberi "
            "Spremi kao (Save As) → Word dokument (.docx)."
        ),
        "ulaz.stari_doc": (
            "Ovo je stari Wordov format (.doc). Otvori datoteku u Wordu i odaberi "
            "Spremi kao (Save As) → Word dokument (.docx)."
        ),
        "ulaz.makro": (
            "Dokument s makronaredbama (.docm) nije dopušten. Odaberi "
            "Spremi kao (Save As) → Word dokument (.docx)."
        ),
        "ulaz.sifrirana": (
            "Datoteka je zaštićena lozinkom. Ukloni lozinku: Datoteka (File) → "
            "Informacije (Info) → Zaštiti dokument (Protect Document) → "
            "Šifriraj lozinkom (Encrypt with Password), obriši lozinku i spremi."
        ),
        "ulaz.prevelika": (
            "Datoteka je veća od {mb} MB. Smanji slike: Oblikovanje slike "
            "(Picture Format) → Komprimiraj slike (Compress Pictures), pa spremi ponovno."
        ),
        "ulaz.zip_bomba": (
            "Sadržaj datoteke prevelik je za provjeru (više od {mb} MB nakon "
            "raspakiranja). Smanji slike i spremi ponovno."
        ),
        "ulaz.ostecena": (
            "Datoteka je oštećena ili nije ispravan Word dokument. Otvori je u Wordu, "
            "provjeri sadržaj i ponovno je spremi kao Word dokument (.docx)."
        ),
        "naziv.obrazac": (
            "Naziv datoteke: `{obrazac}`, s tvojim imenom i prezimenom "
            "kako su zapisani u ISVU-u."
        ),
    }
)


def poruka(kljuc: str, **parametri: str | int) -> str:
    """Vraća tekst poruke s umetnutim parametrima; nepoznat ključ baca ``KeyError``."""
    return KATALOG[kljuc].format(**parametri)


def _decimalni_zarez(iznos: Decimal) -> str:
    tekst = f"{iznos.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
    return tekst.rstrip("0").rstrip(".").replace(".", ",")


def formatiraj(iznos: int | str | bool, jedinica: Jedinica) -> str:
    """Prikaz vrijednosti: twipsi kao cm s decimalnim zarezom, polutočke kao pt."""
    if jedinica is Jedinica.TWIPS:
        return f"{_decimalni_zarez(twips_u_cm(iznos))} cm"
    if jedinica is Jedinica.POLUTOCKE:
        return f"{_decimalni_zarez(Decimal(iznos) / 2)} pt"
    if jedinica is Jedinica.BOOL:
        return poruka("vrijednost.da" if iznos else "vrijednost.ne")
    return str(iznos)

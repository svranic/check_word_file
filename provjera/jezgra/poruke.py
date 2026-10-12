"""Katalog poruka (AD-11): jedini izvor teksta koji vidi korisnik.

Ključevi pravila imaju oblik ``<pravilo_id>.<slucaj>`` (npr. ``R-NAZIV.prolazi``),
a ``pravilo.<ID>`` je naziv pravila. Ostali tekst sučelja grupiran je po prefiksu:
``app.``, ``nastavnik.``, ``privatnost.``, ``profil.``, ``vjezba.``, ``rbr.``,
``margine.``, ``naziv.``, ``ulaz.``, ``opce.``, ``status.``, ``izvjestaj.``,
``lokacija.``, ``izvor.``, ``sazetak.`` i ``vrijednost.``.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from provjera.jezgra.jedinice import Jedinica, twips_u_cm
from provjera.jezgra.nalaz import Izvor, Lokacija, Nalaz, Vrijednost

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
        "pravilo.R-NAZIV": "Naziv datoteke",
        "R-NAZIV.prolazi": "Naziv datoteke je ispravan.",
        "R-NAZIV.ne_odgovara_obrascu": (
            "Naziv „{pronadeno}“ ne odgovara obrascu {ocekivano}. Preimenuj datoteku: "
            "ime i prezime pišu se bez razmaka, odvojeni podvlakom (_), s hrvatskim "
            "znakovima, a nakon njih slijedi točno nastavak iz obrasca."
        ),
        "R-NAZIV.ne_odgovara_ocekivanom": (
            "Naziv „{pronadeno}“ nije očekivani naziv {ocekivano}."
        ),
        "R-NAZIV.nije_tocno_upareno": (
            "Datoteka je povezana sa studentom, ali ne po točnom nazivu. "
            "Očekivani naziv je {ocekivano}."
        ),
        "pravilo.R-SEKCIJE": "Naslovnica kao zasebna sekcija",
        "R-SEKCIJE.prolazi": "Naslovnica je zasebna sekcija, a rad se nastavlja na novoj stranici.",
        "R-SEKCIJE.jedna_sekcija": (
            "Dokument ima samo jednu sekciju, a naslovnica mora biti zasebna sekcija. "
            "Stavi kursor na kraj naslovnice i odaberi Izgled (Layout) → "
            "Prijelomi (Breaks) → Sljedeća stranica (Next Page)."
        ),
        "R-SEKCIJE.krivi_prijelom": (
            "Naslovnicu od sekcije {sekcija} ne dijeli prijelom tipa „Sljedeća stranica“. "
            "Obriši postojeći prijelom sekcije nakon naslovnice i umetni Izgled (Layout) → "
            "Prijelomi (Breaks) → Sljedeća stranica (Next Page)."
        ),
        "R-SEKCIJE.bez_sekcija": (
            "U dokumentu nisu zapisane postavke sekcija pa raspored nije moguće provjeriti."
        ),
        "pravilo.R-MARGINE": "Margine i stranica",
        "R-MARGINE.prolazi": "Sekcija {sekcija}: margine su ispravne.",
        "R-MARGINE.sekcija_odstupa": (
            "Sekcija {sekcija}: margine nisu ispravne. Pronađeno: gore {gore_pronadeno}, "
            "dolje {dolje_pronadeno}, lijevo {lijevo_pronadeno}, desno {desno_pronadeno}. "
            "Očekivano: gore {gore_ocekivano}, dolje {dolje_ocekivano}, "
            "lijevo {lijevo_ocekivano}, desno {desno_ocekivano} "
            "(dopušteno odstupanje {tolerancija}). Stavi kursor u sekciju {sekcija} pa "
            "odaberi Izgled (Layout) → Margine (Margins) → Prilagođene margine "
            "(Custom Margins), uz Primijeni na (Apply to): Ovaj odjeljak (This section)."
        ),
        "R-MARGINE.nedostaje": (
            "Sekcija {sekcija}: margine nisu zapisane u dokumentu pa ih nije "
            "moguće provjeriti."
        ),
        "R-MARGINE.nedostaje_stranica": (
            "Sekcija {sekcija}: veličina stranice nije zapisana u dokumentu pa je nije "
            "moguće provjeriti."
        ),
        "R-MARGINE.bez_sekcija": (
            "U dokumentu nisu zapisane postavke stranice pa margine nije moguće provjeriti."
        ),
        "R-MARGINE.nije_a4": (
            "Sekcija {sekcija}: veličina stranice je {sirina} × {visina}, a treba biti A4. "
            "Odaberi Izgled (Layout) → Veličina (Size) → A4."
        ),
        "R-MARGINE.pejzazno": (
            "Sekcija {sekcija}: stranica je položena. Odaberi Izgled (Layout) → "
            "Usmjerenje (Orientation) → Uspravno (Portrait)."
        ),
        "R-MARGINE.gutter": (
            "Sekcija {sekcija}: postavljena je margina za uvez (Gutter) od {pronadeno}. "
            "U Prilagođenim marginama (Custom Margins) postavi Uvez (Gutter) na 0 cm."
        ),
        "R-MARGINE.zrcalne": (
            "Dokument koristi zrcalne margine. U Prilagođenim marginama (Custom Margins) "
            "pod Više stranica (Multiple pages) odaberi Uobičajeno (Normal)."
        ),
        "opce.neprovjerljivo": (
            "Ovo pravilo nije bilo moguće pouzdano provjeriti ({razlog}). "
            "Pitaj nastavnika da pregleda ovaj dio rada."
        ),
        "status.PROSLO": "✅ prošlo",
        "status.NE_PROLAZI": "❌ ne prolazi",
        "status.NEPROVJERLJIVO": "⚠️ neprovjerljivo",
        "izvjestaj.spremno": "Rad je spreman za predaju.",
        "izvjestaj.nije_spremno": "Rad nije spreman za predaju.",
        "izvjestaj.grupa.NE_PROLAZI": "Ne prolazi",
        "izvjestaj.grupa.NEPROVJERLJIVO": "Neprovjerljivo",
        "izvjestaj.grupa.PROSLO": "Prošlo",
        "izvjestaj.ocekivano": "Očekivano: {vrijednost}",
        "izvjestaj.pronadeno": "Pronađeno: {vrijednost}",
        "izvjestaj.pojave": "Ponavlja se {pojave} puta.",
        "izvjestaj.tehnicki_detalji": "Tehnički detalji",
        "izvjestaj.izvor": "Izvor vrijednosti: {izvor}",
        "izvjestaj.verzija_profila": "Verzija profila: {verzija}",
        "izvjestaj.preopterecenje": (
            "Provjera je trenutno preopterećena. Pokušaj ponovno za minutu."
        ),
        "izvjestaj.greska": (
            "Provjera nije uspjela zbog neočekivane greške. Pokušaj ponovno za minutu, "
            "a ako se ponovi, javi se nastavniku."
        ),
        "sazetak.naslov": "Sažetak provjere Word dokumenta",
        "sazetak.rbr": "Redni broj (Rbr.)",
        "sazetak.vjezba": "Vježba",
        "sazetak.verzija": "Verzija profila",
        "sazetak.vrijeme": "Vrijeme provjere (po zagrebačkom vremenu)",
        "sazetak.spremno": "✅ Rad je bio spreman za predaju.",
        "sazetak.nije_spremno": "❌ Rad nije bio spreman za predaju.",
        "sazetak.stupac_pravilo": "Provjera",
        "sazetak.stupac_status": "Status",
        "sazetak.napomena": (
            "Sažetak ne sadrži sadržaj rada ni naziv datoteke. Provjeru je moguće "
            "ponoviti u bilo kojem trenutku."
        ),
        "sazetak.preuzmi": "Preuzmi sažetak",
        "sazetak.datoteka": "sazetak_provjere_rbr_{rbr}.html",
        "lokacija.DOKUMENT": "Dokument",
        "lokacija.NAZIV": "Naziv datoteke",
        "lokacija.TIJELO": "Tijelo dokumenta",
        "lokacija.PODNOZJE": "Podnožje",
        "lokacija.sekcija": "sekcija {sekcija}",
        "lokacija.odlomak": "odlomak {odlomak}",
        "izvor.ZADANO": "zadane postavke dokumenta",
        "izvor.TEMA": "tema dokumenta",
        "izvor.STIL": "stil",
        "izvor.IZRAVNO": "izravno oblikovanje",
        "izvor.SEKCIJA": "postavke sekcije",
        "naziv.obrazac": (
            "Naziv datoteke: `{obrazac}`, s tvojim imenom i prezimenom "
            "kako su zapisani u ISVU-u."
        ),
    }
)


def poruka(kljuc: str, **parametri: str | int) -> str:
    """Vraća tekst poruke s umetnutim parametrima; nepoznat ključ baca ``KeyError``."""
    return KATALOG[kljuc].format(**parametri)


def tekst_nalaza(nalaz: Nalaz) -> str:
    """Korak ispravka: poruka nalaza s formatiranim očekivanim i pronađenim vrijednostima."""
    vrijednosti = {
        ime: formatiraj(v.iznos, v.jedinica)
        for ime, v in (("ocekivano", nalaz.ocekivano), ("pronadeno", nalaz.pronadeno))
        if v is not None
    }
    parametri = {
        ime: formatiraj(v.iznos, v.jedinica) if isinstance(v, Vrijednost) else v
        for ime, v in nalaz.parametri.items()
    }
    return poruka(nalaz.poruka_kljuc, **{**parametri, **vrijednosti})


def opis_lokacije(lokacija: Lokacija) -> str:
    dijelovi = [poruka(f"lokacija.{lokacija.dio.value}")]
    if lokacija.sekcija is not None:
        dijelovi.append(poruka("lokacija.sekcija", sekcija=lokacija.sekcija))
    if lokacija.odlomak is not None:
        dijelovi.append(poruka("lokacija.odlomak", odlomak=lokacija.odlomak))
    opis = ", ".join(dijelovi)
    return f"{opis}: „{lokacija.isjecak}…“" if lokacija.isjecak else opis


def opis_izvora(izvor: Izvor) -> str:
    opis = poruka(f"izvor.{izvor.vrsta.value}")
    return f"{opis} „{izvor.stil}“" if izvor.stil else opis


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

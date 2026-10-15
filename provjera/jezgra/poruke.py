"""Katalog poruka (AD-11): jedini izvor teksta koji vidi korisnik.

Ključevi pravila imaju oblik ``<pravilo_id>.<slucaj>`` (npr. ``R-NAZIV.prolazi``),
a ``pravilo.<ID>`` je naziv pravila. Ostali tekst sučelja grupiran je po prefiksu:
``app.``, ``nastavnik.``, ``popis.``, ``privatnost.``, ``profil.``, ``vjezba.``, ``rbr.``,
``margine.``, ``naziv.``, ``ulaz.``, ``opce.``, ``status.``, ``izvjestaj.``,
``lokacija.``, ``izvor.``, ``sazetak.``, ``poravnanje.``, ``prored.``, ``spremnost.``,
``samoprovjera.``, ``pdf.``, ``batch.``, ``ukupni_status.``, ``uparivanje.``, ``zbirna.`` i
``vrijednost.``.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType

from provjera.jezgra.jedinice import Jedinica, RETCI_PO_RETKU, retci_u_broj, twips_u_cm, twips_u_pt
from provjera.jezgra.nalaz import Izvor, Lokacija, Nalaz, Vrijednost

# Zajednička uputa R-STILOVI: svojstvo se mijenja u stilu, a ručno oblikovanje uklanja.
_UPUTA_STILOVI = (
    " Ručno oblikovanje vrijedi samo za taj tekst i ne mijenja se kad promijeniš stil. "
    "Ako treba, promijeni svojstvo u stilu: Početna (Home) → Stilovi (Styles) → desni klik "
    "na stil → Izmijeni (Modify). Zatim označi tekst i ukloni ručno oblikovanje: Ctrl+Space "
    "za znakove (font, veličina) i Ctrl+Q za odlomak (poravnanje, razmaci, prored, uvlake). "
    "Ctrl+Space uklanja i podebljanje, kurziv i podcrtavanje, pa ih nakon toga ponovno "
    "primijeni na riječi gdje su potrebni."
)

# Zajednička uputa R-BROJ-STRANICE: broj u podnožju u stilu Podnožje (Footer).
_UPUTA_PODNOZJE = (
    " Broj mora biti u stilu Podnožje (Footer), koji određuje njegov font i veličinu. Ako "
    "je broj stavljen u zaglavlje (Header, vrh stranice), obriši ga odande i umetni u "
    "podnožje (Bottom of Page). Ako "
    "sekcija koristi podnožje prethodne sekcije (Poveži s prethodnim (Link to Previous)), "
    "provjeri da se broj pritom ne pojavi i na naslovnici."
)

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
        "nastavnik.mapa": "Podatkovna mapa (popisi studenata i izdani podaci)",
        "nastavnik.mapa_pomoc": (
            "Mapa na ovom računalu u koju se spremaju popisi studenata. "
            "Ne smije biti unutar repozitorija aplikacije."
        ),
        "nastavnik.mapa_prazna": "Upiši putanju podatkovne mape.",
        "nastavnik.mapa_neispravna": (
            "Putanja podatkovne mape nije ispravna. Upiši potpunu putanju mape "
            "(npr. C:\\Users\\ime\\ProvjeraWord), a ne datoteke."
        ),
        "nastavnik.mapa_u_repozitoriju": (
            "Podatkovna mapa je unutar repozitorija aplikacije, pa bi osobni podaci "
            "studenata mogli završiti u gitu. Odaberi mapu izvan repozitorija."
        ),
        "nastavnik.mapa_odabrana": "Podaci se spremaju u: {mapa}",
        "nastavnik.vjezba": "Vježba",
        "nastavnik.vjezba_neobjavljena": "{naziv} (neobjavljena)",
        "nastavnik.nema_profila": "Nema profila vježbi u mapi profili/.",
        "nastavnik.profil_neispravan": "{datoteka} (neispravan profil)",
        "nastavnik.profil_greske": (
            "Profil {datoteka} je neispravan i ne može se koristiti. "
            "Ispravi ove greške (broj grešaka: {broj}):"
        ),
        "nastavnik.popis_naslov": "Popis studenata iz ISVU-a",
        "nastavnik.ucitaj_popis": "ISVU izvoz popisa studenata (.xlsx)",
        "nastavnik.popis_ispravan": "Popis je ispravan.",
        "nastavnik.popis_neispravan": (
            "Popis ima pogrešaka ({broj}) i ne može se zamrznuti. Ispravi ih u izvozu "
            "i učitaj ga ponovno."
        ),
        "nastavnik.stupac_rbr": "Rbr.",
        "nastavnik.stupac_jmbag": "JMBAG",
        "nastavnik.stupac_ime": "Ime",
        "nastavnik.stupac_prezime": "Prezime",
        "nastavnik.stupac_aktivan": "Aktivan",
        "popis.broj_studenata": "Studenata: {broj}",
        "popis.broj_neaktivnih": "Neaktivnih (ispisanih): {broj}",
        "popis.redak": "Redak {redak}: {poruka}",
        "popis.necitljiv": "Datoteka nije čitljiva .xlsx tablica.",
        "popis.bez_zaglavlja": (
            "Zaglavlje popisa nije pronađeno u prvih {najvise} redaka. Nedostaju stupci: {stupci}."
        ),
        "popis.bez_studenata": "Popis ne sadrži nijednog studenta.",
        "popis.rbr_neispravan": "Rbr. nije pozitivan cijeli broj.",
        "popis.dupli_rbr": "Rbr. {rbr} već se pojavio u retku {prvi}.",
        "popis.dupli_jmbag": "Isti JMBAG već se pojavio u retku {prvi}.",
        "popis.prazan_jmbag": "JMBAG je prazan.",
        "popis.jmbag_neispravan": "JMBAG mora imati točno 10 znamenki.",
        "popis.prazno_ime": "Ime je prazno.",
        "popis.prazno_prezime": "Prezime je prazno.",
        "popis.zamrznuti_necitljiv": "Zamrznuti popis nije čitljiva CSV datoteka u UTF-8.",
        "popis.zamrznuti_prazan": "Zamrznuti popis ne sadrži nijednog studenta.",
        "popis.zamrznuti_zaglavlje": "Zaglavlje mora biti točno: {stupci}.",
        "popis.zamrznuti_broj_stupaca": "Redak ima {pronadeno} stupaca umjesto {ocekivano}.",
        "popis.zamrznuti_aktivan": "Stupac aktivan mora biti true ili false.",
        "nastavnik.zamrznuti_naslov": "Zamrznuti popis za vježbu",
        "nastavnik.zamrznuti_nema": (
            "Popis za ovu vježbu još nije zamrznut. Učitaj ispravan ISVU izvoz i zamrzni ga."
        ),
        "nastavnik.zamrznuti_stanje": (
            "Zamrznuti popis – broj studenata: {broj}, aktivnih: {aktivnih}, "
            "neaktivnih: {neaktivnih}."
        ),
        "nastavnik.zamrznuti_ne_uredivati": (
            "Ne otvaraj i ne spremaj popis.csv u Excelu: spremanje mijenja razdjelnik i briše "
            "vodeće nule JMBAG-a, pa popis postaje neispravan."
        ),
        "nastavnik.zamrznuti_ostecen": (
            "Zamrznuti popis ({putanja}) je oštećen: {poruka} Ispravi ili ukloni datoteku; "
            "aplikacija je ne prepisuje."
        ),
        "nastavnik.zamrzni": "Zamrzni popis",
        "nastavnik.zamrzni_pomoc": (
            "Rbr. iz popisa određuje margine studenata i nakon zamrzavanja se više ne mijenja."
        ),
        "nastavnik.zamrzni_onemoguceno": "Popis s greškama ne može se zamrznuti.",
        "nastavnik.zamrznuto": "Popis je zamrznut. Broj studenata: {broj}.",
        "nastavnik.vec_zamrznut": (
            "Popis za ovu vježbu već je zamrznut i ne prepisuje se novim izvozom."
        ),
        "nastavnik.zapis_neuspio": (
            "Popis nije zapisan. Zatvori popis.csv ako je otvoren u drugom programu "
            "(npr. Excelu) i provjeri može li se pisati u podatkovnu mapu, pa pokušaj ponovno."
        ),
        "nastavnik.popis_neispravan_za_zapis": (
            "Popis nije zapisan jer nije ispravan (prazan ili s ponovljenim Rbr. ili JMBAG-om)."
        ),
        "nastavnik.popis_promijenjen": (
            "Zamrznuti popis se u međuvremenu promijenio, pa promjene nisu primijenjene. "
            "Osvježi stranicu i ponovno pregledaj razlike."
        ),
        "nastavnik.razlike_naslov": "Razlike novog izvoza i zamrznutog popisa (po JMBAG-u)",
        "nastavnik.razlike_nema": "Nema razlika: zamrznuti popis je ažuran.",
        "nastavnik.razlike_nema_za_primjenu": (
            "Nema promjena za primijeniti; razlike u imenima samo su upozorenje."
        ),
        "nastavnik.razlike_novi": "Novi studenti (kasni upis):",
        "nastavnik.razlike_novi_student": "{ime} {prezime} (JMBAG {jmbag}) dobiva Rbr. {rbr}",
        "nastavnik.razlike_ispisani": "Ispisani studenti (zadržavaju Rbr., postaju neaktivni):",
        "nastavnik.razlike_ponovno": "Ponovno upisani studenti (ponovno postaju aktivni):",
        "nastavnik.razlike_student": "Rbr. {rbr}: {ime} {prezime} (JMBAG {jmbag})",
        "nastavnik.razlike_imena": (
            "Promijenjeno ime u ISVU-u (samo upozorenje, zamrznuti popis se ne mijenja):"
        ),
        "nastavnik.razlike_ime": (
            "Rbr. {rbr}: {staro} → {novo} (JMBAG {jmbag})"
        ),
        "nastavnik.primijeni": "Primijeni promjene",
        "nastavnik.primijeni_onemoguceno": (
            "Promjene se ne mogu primijeniti dok novi izvoz ima grešaka."
        ),
        "nastavnik.primijenjeno": (
            "Promjene su primijenjene – novi studenti: {novi}, ispisani: {ispisani}, "
            "ponovno upisani: {ponovno}."
        ),
        "spremnost.naslov": "Spremnost",
        "spremnost.profil": "Profil: {naziv} (verzija {verzija})",
        "spremnost.aktivnih": "Aktivnih studenata: {broj}",
        "spremnost.pravila": "Uključenih pravila: {broj} od {ukupno}",
        "spremnost.margine_jedinstvene": "Margine su jedinstvene za sve Rbr. na popisu.",
        "spremnost.margine_nejedinstvene": "Margine nisu jedinstvene za sve Rbr. na popisu.",
        "spremnost.margine_neprovjerene": (
            "Jedinstvenost margina nije provjerena jer nema zamrznutog popisa."
        ),
        "spremnost.spremno": "spremno",
        "spremnost.nije_spremno": "nije spremno – problemi: {broj}",
        "spremnost.nema_popisa": "Nema zamrznutog popisa studenata za ovu vježbu.",
        "spremnost.nema_aktivnih": "Na zamrznutom popisu nema nijednog aktivnog studenta.",
        "spremnost.rbr_izvan_raspona": (
            "Rbr. {rbrovi} izvan je raspona formule margina "
            "(najveći dopušteni Rbr. je {najveci})."
        ),
        "spremnost.dupli_rbr": "Rbr. {rbrovi} pojavljuje se na popisu više puta.",
        "spremnost.iste_margine": "Rbr. {prvi} i Rbr. {drugi} imaju iste margine.",
        "spremnost.nema_pravila": "U profilu nije uključeno nijedno pravilo.",
        "spremnost.samoprovjera_nije_pokrenuta": (
            "Samoprovjera profila na referentnom skupu nije pokrenuta."
        ),
        "spremnost.samoprovjera_nema_skupa": "Samoprovjera nije moguća: {poruka}",
        "spremnost.samoprovjera_ne_prolazi": (
            "Samoprovjera profila ne prolazi (odstupanja: {broj})."
        ),
        "samoprovjera.naslov": "Samoprovjera",
        "samoprovjera.opis": (
            "Provjerava ispravan rad i sve pokvarene varijante iz referentnog skupa "
            "trenutnim profilom. Promjena profila poništava rezultat."
        ),
        "samoprovjera.pokreni": "Pokreni samoprovjeru",
        "samoprovjera.prolazi": "Samoprovjera prolazi.",
        "samoprovjera.ne_prolazi": "Samoprovjera ne prolazi (odstupanja: {broj}).",
        "samoprovjera.stupac_primjer": "Primjer",
        "samoprovjera.stupac_ocekivano": "Očekivano",
        "samoprovjera.stupac_pronadeno": "Pronađeno",
        "samoprovjera.stupac_status": "Status",
        "samoprovjera.status_prolazi": "✅ prolazi",
        "samoprovjera.status_ne_prolazi": "❌ ne prolazi",
        "samoprovjera.status_preskoceno": "⏭️ preskočeno (pravilo isključeno)",
        "samoprovjera.status_razlog": "{status} – {razlog}",
        "samoprovjera.nista": "—",
        "samoprovjera.nijedno": "nijedno pravilo",
        "samoprovjera.nema_skupa": "Za ovu vježbu nema referentnog skupa (mapa {mapa} ne postoji).",
        "samoprovjera.nema_ocekivanog": "Referentni skup nema datoteku {putanja}.",
        "samoprovjera.ocekivano_neispravno": (
            "Datoteka {putanja} nije ispravna (potrebni su rbr, naziv i [primjeri.<ime>] padaju)."
        ),
        "samoprovjera.nema_datoteke": "primjer nema .docx datoteku",
        "samoprovjera.nema_zapisa": "datoteka nema zapis u ocekivano.toml",
        "samoprovjera.necitljiv": "datoteka nije čitljiva",
        "samoprovjera.odbijeno": "provjera je odbila dokument ({razlog})",
        "samoprovjera.greska_provjere": "neočekivana greška pri provjeri ({razlog})",
        "samoprovjera.nepoznato_pravilo": (
            "Datoteka {putanja} navodi nepoznata pravila: {pravila}."
        ),
        "samoprovjera.mapa_necitljiva": "Mapa referentnog skupa {mapa} nije čitljiva.",
        "samoprovjera.u_tijeku": "Samoprovjera je u tijeku …",
        "pdf.naslov": "{naziv} – svojstva za oblikovanje rada",
        "pdf.verzija": "Verzija profila: {verzija}",
        "pdf.poveznica": "Web provjera rada: {poveznica}",
        "pdf.uputa": (
            "Pronađi svoj redak u tablici. Datoteku nazovi točno kao u stupcu „Naziv datoteke“, "
            "a sekcijama rada nakon naslovnice postavi svoje margine. Prije predaje provjeri rad "
            "na web provjeri: upiši svoj Rbr. i usporedi margine koje ondje vidiš s ovom tablicom."
        ),
        "pdf.privatnost": "Napomena o obradi: {obrada}",
        "pdf.zajednicki_naslov": "Zajednički zahtjevi (isti za sve studente)",
        "pdf.zahtjev": "{naziv}: {svojstva}.",
        "pdf.razdjelnik": ", ",
        "pdf.naslovnica": "Margine naslovnice",
        "pdf.opis.naslovnica": (
            "{naslovnica} sa svih strana "
            "(individualne margine iz tablice vrijede za sekcije rada nakon naslovnice)"
        ),
        "pdf.opis.R-NAZIV": (
            "{obrazac}, s imenom i prezimenom kako su zapisani u ISVU-u "
            "(tvoj točan naziv je u tablici)"
        ),
        "pdf.opis.R-SEKCIJE": (
            "naslovnica je zasebna sekcija, a rad se nastavlja novom sekcijom na novoj stranici "
            "(Izgled (Layout) → Prijelomi (Breaks) → Sljedeća stranica (Next Page))"
        ),
        "pdf.opis.R-PROMJENE": (
            "prije predaje prihvati sve praćene promjene (Pregled (Review) → Prihvati (Accept) "
            "→ Prihvati sve promjene (Accept All Changes)) i isključi praćenje"
        ),
        "pdf.opis.R-OKVIRI": (
            "naslovi i osnovni tekst ne smiju biti u tekstnim okvirima ni oblicima"
        ),
        "pdf.opis.R-BROJ-STRANICE": (
            "Wordovo polje broja stranice u podnožju svake sekcije rada, naslovnica nema broj"
        ),
        "pdf.opis.R-STILOVI": (
            "osnovni tekst i naslovi oblikuju se stilovima, bez ručnog oblikovanja"
        ),
        "pdf.oznaka": "{prvi}, {drugi} …",
        "pdf.svojstvo.stil": "stil {vrijednost}",
        "pdf.svojstvo.font": "font {vrijednost}",
        "pdf.svojstvo.velicina": "veličina {vrijednost}",
        "pdf.svojstvo.podebljano": "podebljano: {vrijednost}",
        "pdf.svojstvo.poravnanje": "poravnanje {vrijednost}",
        "pdf.svojstvo.razmak_ispred": "razmak ispred {vrijednost}",
        "pdf.svojstvo.razmak_iza": "razmak iza {vrijednost}",
        "pdf.svojstvo.prored": "prored {vrijednost}",
        "pdf.svojstvo.oznaka": "Wordova numeracija {vrijednost}",
        "pdf.svojstvo.uvlaka_lijevo": "uvlaka lijevo {vrijednost}",
        "pdf.svojstvo.uvlaka_desno": "uvlaka desno {vrijednost}",
        "pdf.tablica_naslov": "Individualna svojstva studenata",
        "pdf.tablica_opis": "Margine vrijede za sve sekcije rada nakon naslovnice.",
        "pdf.stupac_rbr": "Rbr.",
        "pdf.stupac_ime": "Ime",
        "pdf.stupac_prezime": "Prezime",
        "pdf.stupac_naziv": "Naziv datoteke",
        "pdf.stupac_gore": "Gore",
        "pdf.stupac_dolje": "Dolje",
        "pdf.stupac_lijevo": "Lijevo",
        "pdf.stupac_desno": "Desno",
        "pdf.stranica": "Stranica {broj} od {ukupno}",
        "nastavnik.pdf_naslov": "PDF sa svojstvima",
        "nastavnik.pdf_opis": (
            "PDF za objavu u e-učenju: Rbr., ime, prezime, očekivani naziv datoteke i margine "
            "svakog aktivnog studenta te zajednički zahtjevi. Ne sadrži JMBAG-ove."
        ),
        "nastavnik.pdf_generiraj": "Generiraj PDF",
        "nastavnik.pdf_onemoguceno": (
            "PDF se može generirati tek kad je vježba spremna (vidi odjeljak Spremnost)."
        ),
        "nastavnik.pdf_generirano": (
            "PDF je generiran ({putanja}). Otisak formule i verzija profila zapisani su u "
            "izdano.json. Broj studenata u PDF-u: {broj}."
        ),
        "nastavnik.pdf_zapis_neuspio": (
            "PDF nije zapisan. Zatvori PDF ili izdano.json ako je otvoren u drugom programu "
            "i provjeri može li se pisati u podatkovnu mapu, pa pokušaj ponovno."
        ),
        "nastavnik.pdf_preuzmi": "Preuzmi PDF",
        "nastavnik.pdf_poveznica": (
            "Poveznica na web provjeru koja će biti u PDF-u. Provjeri je prije generiranja; "
            "mijenja se u profilu vježbe ([vjezba] poveznica):"
        ),
        "nastavnik.pdf_izdano": (
            "Zadnji PDF izdan je {vrijeme} (verzija profila {verzija})."
        ),
        "nastavnik.pdf_izdano_razlika": (
            "Profil ili formula margina promijenili su se od zadnjeg izdanog PDF-a. Studenti "
            "već imaju raniji PDF: novi PDF mijenja njihova svojstva i treba ga ponovno objaviti."
        ),
        "nastavnik.pdf_nije_izdano": "PDF za ovu vježbu još nije izdan.",
        "popis.izdano_necitljivo": (
            "Datoteka izdano.json nije ispravna (potrebni su formula_otisak, profil_verzija "
            "i vrijeme u ISO 8601 s vremenskom zonom)."
        ),
        "profil.dupli_id": "vjezba.id: isti id već ima profil {datoteka}",
        "profil.necitljiv": "datoteka: nije čitljiva ({razlog})",
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
        "rbr.prazno": "Upiši svoj redni broj (pozitivan cijeli broj), npr. 54.",
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
        "pravilo.R-TEKST": "Osnovni tekst",
        "R-TEKST.prolazi": "Osnovni tekst je u stilu {stil} i ispravno je oblikovan.",
        "R-TEKST.nema_teksta": (
            "U radu nije pronađen osnovni tekst (odlomci ispod naslova poglavlja). "
            "Provjeri jesu li naslovi poglavlja oblikovani stilom Naslov 1 (Heading 1) "
            "i je li tekst poglavlja upisan ispod njih."
        ),
        "R-TEKST.drugi_stil": (
            "Odlomak osnovnog teksta je u stilu „{pronadeno}“, a mora biti u stilu "
            "„{stil}“, čak i kad izgleda jednako. Stavi kursor u odlomak i "
            "odaberi Početna (Home) → Stilovi (Styles) → {stil}."
        ),
        "R-TEKST.font": (
            "Font osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. Font se mijenja "
            "u stilu, ne ručno: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}. "
            "Ako je font zadan ručno, označi tekst i pritisni Ctrl+Space."
        ),
        "R-TEKST.font_tema": (
            "Font osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. Stil ne navodi "
            "font pa Word uzima font teme dokumenta (u novijim verzijama Aptos). Odaberi "
            "Dizajn (Design) → Fontovi (Fonts) i skup u kojem je font tijela {ocekivano}, "
            "ili zadaj font u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-TEKST.font_nepoznat": (
            "Font osnovnog teksta trebao bi doći iz teme dokumenta, ali tema nije zapisana "
            "u datoteci pa font nije moguće odrediti. Zadaj font izravno u stilu: "
            "Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-TEKST.velicina": (
            "Veličina fonta osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni je u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-TEKST.poravnanje": (
            "Poravnanje osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → "
            "Poravnanje (Alignment)."
        ),
        "R-TEKST.razmak_ispred": (
            "Razmak ispred odlomka osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → "
            "Ispred (Before)."
        ),
        "R-TEKST.razmak_iza": (
            "Razmak iza odlomka osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → "
            "Iza (After)."
        ),
        "R-TEKST.prored": (
            "Prored osnovnog teksta je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → "
            "Prored (Line spacing)."
        ),
        "pravilo.R-NASLOVI": "Naslovi poglavlja",
        "R-NASLOVI.prolazi": (
            "Naslovi poglavlja su u stilu „{stil}“, ispravno su oblikovani i numerirani "
            "Wordovom numeracijom."
        ),
        "R-NASLOVI.nedostaje": (
            "U radu nije pronađeno poglavlje „{naziv}“. Dodaj naslov poglavlja i oblikuj "
            "ga stilom: Početna (Home) → Stilovi (Styles) → {stil}."
        ),
        "R-NASLOVI.drugi_stil": (
            "Naslov poglavlja je u stilu „{pronadeno}“, a mora biti u stilu „{stil}“, čak i "
            "kad izgleda jednako. Ručno oblikovanje (podebljanje, veličina) samo mijenja izgled "
            "teksta, a stil Wordu govori da je to naslov: o njemu ovise numeracija, sadržaj "
            "(Table of Contents) i navigacija. Stavi kursor u naslov i odaberi Početna (Home) → "
            "Stilovi (Styles) → {stil}."
        ),
        "R-NASLOVI.rucni_broj": (
            "Broj naslova „{pronadeno}“ upisan je ručno. Obriši upisani broj i uključi Wordovu "
            "numeraciju: stavi kursor u naslov i odaberi "
            "Početna (Home) → Višerazinski popis (Multilevel List) → Definiraj novi višerazinski "
            "popis (Define New Multilevel List): za razinu 1 postavi oblik broja „1.“ i "
            "Poveži razinu sa stilom (Link level to style) „Naslov 1 (Heading 1)“."
            " Wordova numeracija se sama ažurira kad dodaš, obrišeš ili premjestiš poglavlje."
        ),
        "R-NASLOVI.rucni_broj_uz_numeraciju": (
            "Naslov „{pronadeno}“ ima ručno upisan broj, a Word već numerira taj naslov pa se "
            "broj prikazuje dvaput. Obriši ručno upisani broj iz teksta naslova."
        ),
        "R-NASLOVI.bez_numeracije": (
            "Naslov poglavlja nije numeriran Wordovom numeracijom. Stavi kursor u naslov i "
            "odaberi "
            "Početna (Home) → Višerazinski popis (Multilevel List) → Definiraj novi višerazinski "
            "popis (Define New Multilevel List): za razinu 1 postavi oblik broja „1.“ i "
            "Poveži razinu sa stilom (Link level to style) „Naslov 1 (Heading 1)“."
            " Broj ne upisuj ručno."
        ),
        "R-NASLOVI.kriva_oznaka": (
            "Naslov poglavlja ima oznaku „{pronadeno}“, a treba imati „{ocekivano}“. "
            "Provjeri redoslijed i stil naslova, pa odaberi "
            "Početna (Home) → Višerazinski popis (Multilevel List) → Definiraj novi višerazinski "
            "popis (Define New Multilevel List): za razinu 1 postavi oblik broja „1.“ i "
            "Poveži razinu sa stilom (Link level to style) „Naslov 1 (Heading 1)“."
            " Ako numeracija ne kreće ispravno, desni klik na broj → Postavi vrijednost "
            "numeriranja (Set Numbering Value)."
        ),
        "R-NASLOVI.sazetak_numeriran": (
            "Naslov sažetka je numeriran („{pronadeno}“), a sažetak nije poglavlje i ne smije "
            "imati broj. Stavi kursor u naslov sažetka i isključi numeraciju: Početna (Home) → "
            "Numeriranje (Numbering) → Ništa (None), ili mu dodijeli stil bez numeracije."
        ),
        "R-NASLOVI.font": (
            "Font naslova poglavlja je {pronadeno}, a treba biti {ocekivano}. Font se mijenja "
            "u stilu, ne ručno: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → "
            "Oblikovanje (Formatting) → {ocekivano}. Ako je font zadan ručno, označi naslov i "
            "pritisni Ctrl+Space."
        ),
        "R-NASLOVI.font_tema": (
            "Font naslova poglavlja je {pronadeno}, a treba biti {ocekivano}. Stil ne navodi "
            "font pa Word uzima font naslova iz teme dokumenta. Zadaj font u stilu: Početna "
            "(Home) → Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Formatting) → "
            "{ocekivano}."
        ),
        "R-NASLOVI.font_nepoznat": (
            "Font naslova poglavlja trebao bi doći iz teme dokumenta, ali tema nije zapisana u "
            "datoteci pa font nije moguće odrediti. Zadaj font izravno u stilu: Početna (Home) → "
            "Stilovi (Styles) → {stil} → Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-NASLOVI.podebljano": (
            "Podebljano (Bold) za naslov poglavlja: {pronadeno}, a treba: {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni "
            "(Modify) → Oblikovanje (Formatting) → Podebljano (Bold). Ako je zadano ručno, "
            "označi naslov i pritisni Ctrl+Space."
        ),
        "R-NASLOVI.velicina": (
            "Veličina fonta naslova poglavlja je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni je u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni "
            "(Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-NASLOVI.poravnanje": (
            "Poravnanje naslova poglavlja je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni "
            "(Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → Poravnanje (Alignment)."
        ),
        "R-NASLOVI.razmak_ispred": (
            "Razmak ispred naslova poglavlja je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni "
            "(Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → Ispred (Before)."
        ),
        "R-NASLOVI.razmak_iza": (
            "Razmak iza naslova poglavlja je {pronadeno}, a treba biti {ocekivano}. "
            "Promijeni ga u stilu: Početna (Home) → Stilovi (Styles) → {stil} → Izmijeni "
            "(Modify) → Oblikovanje (Format) → Odlomak (Paragraph) → Iza (After)."
        ),
        "pravilo.R-SAZETAK": "Sažetak",
        "R-SAZETAK.prolazi": "Sažetak je ispravno oblikovan.",
        "R-SAZETAK.nema_sazetka": (
            "U radu nije pronađen sažetak. Ispred prvog poglavlja upiši naslov „{naziv}“ "
            "i ispod njega tekst sažetka."
        ),
        "R-SAZETAK.nema_naslova": (
            "Ispred prvog poglavlja postoji tekst, ali nema naslova „{naziv}“. "
            "Upiši naslov „{naziv}“ iznad teksta sažetka."
        ),
        "R-SAZETAK.prazan_sazetak": (
            "Ispod naslova „{naziv}“ nema teksta sažetka. Upiši tekst sažetka između naslova "
            "„{naziv}“ i prvog poglavlja."
        ),
        "R-SAZETAK.krivo_mjesto": (
            "Sažetak mora biti ispred prvog poglavlja. Premjesti naslov „{naziv}“ i tekst "
            "sažetka iza naslovnice, a ispred naslova prvog poglavlja."
        ),
        "R-SAZETAK.font": (
            "Font sažetka je {pronadeno}, a treba biti {ocekivano}. Sažetak smije imati "
            "vlastiti stil (npr. „Sažetak“) ili biti u stilu Normal: označi tekst sažetka i "
            "odaberi Početna (Home) → Font → {ocekivano}, ili font promijeni u stilu sažetka: "
            "Početna (Home) → Stilovi (Styles) → desni klik na stil → Izmijeni (Modify) → "
            "Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-SAZETAK.font_tema": (
            "Font sažetka je {pronadeno}, a treba biti {ocekivano}. Stil sažetka ne navodi "
            "font pa Word uzima font teme dokumenta (u novijim verzijama Aptos). Odaberi "
            "Dizajn (Design) → Fontovi (Fonts) i skup u kojem je font tijela {ocekivano}, "
            "ili zadaj font u stilu sažetka: Početna (Home) → Stilovi (Styles) → desni klik "
            "na stil → Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-SAZETAK.font_nepoznat": (
            "Font sažetka trebao bi doći iz teme dokumenta, ali tema nije zapisana u datoteci "
            "pa font nije moguće odrediti. Zadaj font izravno u stilu sažetka: Početna (Home) "
            "→ Stilovi (Styles) → desni klik na stil → Izmijeni (Modify) → Oblikovanje "
            "(Formatting) → {ocekivano}."
        ),
        "R-SAZETAK.velicina": (
            "Veličina fonta sažetka je {pronadeno}, a treba biti {ocekivano}. Označi tekst "
            "sažetka i odaberi Početna (Home) → Veličina fonta (Font Size) → {ocekivano}, ili "
            "veličinu promijeni u vlastitom stilu sažetka."
        ),
        "R-SAZETAK.poravnanje": (
            "Poravnanje sažetka je {pronadeno}, a treba biti {ocekivano}. Stavi kursor u "
            "sažetak i odaberi Početna (Home) → Odlomak (Paragraph) → Poravnanje (Alignment) "
            "→ {ocekivano}."
        ),
        "R-SAZETAK.uvlaka_lijevo": (
            "Lijeva uvlaka sažetka je {pronadeno}, a treba biti {ocekivano}. Sažetak smije "
            "imati vlastitu uvlaku (ili vlastiti stil), za razliku od osnovnog teksta. Označi "
            "sažetak i odaberi Početna (Home) → Odlomak (Paragraph) → Uvlaka (Indentation) → "
            "Lijevo (Left): {ocekivano}."
        ),
        "R-SAZETAK.uvlaka_desno": (
            "Desna uvlaka sažetka je {pronadeno}, a treba biti {ocekivano}. Sažetak smije "
            "imati vlastitu uvlaku (ili vlastiti stil), za razliku od osnovnog teksta. Označi "
            "sažetak i odaberi Početna (Home) → Odlomak (Paragraph) → Uvlaka (Indentation) → "
            "Desno (Right): {ocekivano}."
        ),
        "pravilo.R-LITERATURA": "Literatura",
        "R-LITERATURA.prolazi": "Stavke literature su ispravno oblikovane.",
        "R-LITERATURA.nema_stavki": (
            "U radu nije pronađen popis literature: stavke se pišu ispod naslova „{naziv}“, "
            "koji je posljednje poglavlje rada. Upiši korištene izvore ispod tog naslova, "
            "svaki u svom odlomku."
        ),
        "R-LITERATURA.font": (
            "Font stavke literature je {pronadeno}, a treba biti {ocekivano}. Literatura smije "
            "imati vlastiti stil (npr. Odlomak popisa (List Paragraph)): označi stavke i "
            "odaberi Početna (Home) → Font → {ocekivano}, ili font promijeni u stilu stavki: "
            "Početna (Home) → Stilovi (Styles) → desni klik na stil → Izmijeni (Modify) → "
            "Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-LITERATURA.font_tema": (
            "Font stavke literature je {pronadeno}, a treba biti {ocekivano}. Stil stavke ne "
            "navodi font pa Word uzima font teme dokumenta (u novijim verzijama Aptos). Odaberi "
            "Dizajn (Design) → Fontovi (Fonts) i skup u kojem je font tijela {ocekivano}, ili "
            "zadaj font u stilu stavki: Početna (Home) → Stilovi (Styles) → desni klik na stil "
            "→ Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-LITERATURA.font_nepoznat": (
            "Font stavke literature trebao bi doći iz teme dokumenta, ali tema nije zapisana u "
            "datoteci pa font nije moguće odrediti. Zadaj font izravno u stilu stavki: Početna "
            "(Home) → Stilovi (Styles) → desni klik na stil → Izmijeni (Modify) → Oblikovanje "
            "(Formatting) → {ocekivano}."
        ),
        "R-LITERATURA.velicina": (
            "Veličina fonta stavke literature je {pronadeno}, a treba biti {ocekivano}. Označi "
            "stavke i odaberi Početna (Home) → Veličina fonta (Font Size) → {ocekivano}, ili "
            "veličinu promijeni u stilu stavki."
        ),
        "pravilo.R-STILOVI": "Korištenje stilova",
        "R-STILOVI.prolazi": (
            "Osnovni tekst i naslovi oblikovani su kroz stilove, bez ručnog oblikovanja."
        ),
        # Bez {pronadeno}: font teme zadan ručno može biti bez imena u temi.
        "R-STILOVI.izravni_font": (
            "Font je zadan ručno, a ne kroz stil, čak i ako je ispravan (i kad je odabran font "
            "teme, npr. „(Body)“ s popisa fontova)." + _UPUTA_STILOVI
        ),
        "R-STILOVI.izravna_velicina": (
            "Veličina fonta ({pronadeno}) zadana je ručno, a ne kroz stil, čak i ako je ispravna."
            + _UPUTA_STILOVI
        ),
        "R-STILOVI.izravno_poravnanje": (
            "Poravnanje ({pronadeno}) zadano je ručno, a ne kroz stil, čak i ako je ispravno."
            + _UPUTA_STILOVI
        ),
        "R-STILOVI.izravni_razmak": (
            "Razmak {strana} odlomka ({pronadeno}) zadan je ručno, a ne kroz stil, čak i "
            "ako je ispravan." + _UPUTA_STILOVI
        ),
        "R-STILOVI.izravni_prored": (
            "Prored ({pronadeno}) zadan je ručno, a ne kroz stil, čak i ako je ispravan."
            + _UPUTA_STILOVI
        ),
        "R-STILOVI.izravna_uvlaka": (
            "Uvlaka odlomka ({strana}: {pronadeno}) zadana je ručno, a ne kroz stil, čak i ako "
            "je ispravna." + _UPUTA_STILOVI
        ),
        "pravilo.R-BROJ-STRANICE": "Numeriranje stranica",
        "R-BROJ-STRANICE.prolazi": (
            "Broj stranice u podnožjima je ispravno postavljen."
        ),
        "R-BROJ-STRANICE.bez_sekcija": (
            "U dokumentu nisu zapisane postavke sekcija pa podnožja nije moguće provjeriti."
        ),
        "R-BROJ-STRANICE.bez_broja": (
            "Podnožje ove sekcije nema broj stranice. Dvaput klikni u podnožje stranice ove "
            "sekcije i umetni broj: Umetanje (Insert) → Broj stranice (Page Number) → Dno "
            "stranice (Bottom of Page). Word tada sam broji stranice." + _UPUTA_PODNOZJE
        ),
        "R-BROJ-STRANICE.bez_broja_prva": (
            "Sekcija ima uključenu Drukčiju prvu stranicu (Different First Page), a podnožje "
            "njezine prve stranice nema broj stranice. Dvaput klikni u podnožje prve stranice "
            "sekcije i umetni broj: Umetanje (Insert) → Broj stranice (Page Number) → Dno "
            "stranice (Bottom of Page), ili isključi Dizajn zaglavlja i podnožja (Header & "
            "Footer) → Drukčija prva stranica (Different First Page)." + _UPUTA_PODNOZJE
        ),
        "R-BROJ-STRANICE.bez_broja_parna": (
            "Dokument ima uključene Drukčije parne i neparne stranice (Different Odd & Even "
            "Pages), a podnožje parnih stranica ove sekcije nema broj stranice. Dvaput klikni "
            "u podnožje parne stranice i umetni broj: Umetanje (Insert) → Broj stranice (Page "
            "Number) → Dno stranice (Bottom of Page), ili isključi Dizajn zaglavlja i podnožja "
            "(Header & Footer) → Drukčije parne i neparne stranice (Different Odd & Even Pages)."
            + _UPUTA_PODNOZJE
        ),
        "R-BROJ-STRANICE.rucni_broj": (
            "Broj stranice u podnožju ove sekcije upisan je ručno, a ne kao Wordov broj "
            "stranice. Ručno upisan broj isti je na svakoj stranici i ne mijenja se kad se "
            "tekst pomakne. Obriši upisani broj i umetni pravi: Umetanje (Insert) → Broj "
            "stranice (Page Number) → Dno stranice (Bottom of Page)." + _UPUTA_PODNOZJE
        ),
        "R-BROJ-STRANICE.naslovnica_ima_broj": (
            "Naslovnica ne smije imati broj stranice, a njezino podnožje ga ima. Najčešće je "
            "podnožje tijela povezano s naslovnicom. Dvaput klikni u podnožje prve stranice "
            "rada nakon naslovnice i isključi Dizajn zaglavlja i podnožja (Header & Footer) → "
            "Poveži s prethodnim (Link to Previous), a zatim obriši broj iz podnožja "
            "naslovnice. Druga mogućnost je u sekciji naslovnice uključiti Dizajn zaglavlja i "
            "podnožja (Header & Footer) → Drukčija prva stranica (Different First Page)."
        ),
        "R-BROJ-STRANICE.font": (
            "Font broja stranice je {pronadeno}, a treba biti {ocekivano}. Broj stranice "
            "preuzima oblikovanje stila Podnožje (Footer): Početna (Home) → Stilovi (Styles) → "
            "desni klik na Podnožje (Footer) → Izmijeni (Modify) → Oblikovanje (Formatting) → "
            "{ocekivano}. Ako je font zadan ručno, označi broj u podnožju i pritisni Ctrl+Space."
        ),
        "R-BROJ-STRANICE.font_tema": (
            "Font broja stranice je {pronadeno}, a treba biti {ocekivano}. Stil Podnožje "
            "(Footer) ne navodi font pa Word uzima font teme dokumenta (u novijim verzijama "
            "Aptos). Odaberi Dizajn (Design) → Fontovi (Fonts) i skup u kojem je font tijela "
            "{ocekivano}, ili zadaj font u stilu: Početna (Home) → Stilovi (Styles) → desni "
            "klik na Podnožje (Footer) → Izmijeni (Modify) → Oblikovanje (Formatting) → "
            "{ocekivano}."
        ),
        "R-BROJ-STRANICE.font_nepoznat": (
            "Font broja stranice trebao bi doći iz teme dokumenta, ali tema nije zapisana u "
            "datoteci pa font nije moguće odrediti. Zadaj font izravno u stilu: Početna (Home) "
            "→ Stilovi (Styles) → desni klik na Podnožje (Footer) → Izmijeni (Modify) → "
            "Oblikovanje (Formatting) → {ocekivano}."
        ),
        "R-BROJ-STRANICE.velicina": (
            "Veličina broja stranice je {pronadeno}, a treba biti {ocekivano}. Promijeni je u "
            "stilu: Početna (Home) → Stilovi (Styles) → desni klik na Podnožje (Footer) → "
            "Izmijeni (Modify) → Oblikovanje (Formatting) → {ocekivano}. Ako je veličina "
            "zadana ručno, označi broj u podnožju i pritisni Ctrl+Space."
        ),
        "pravilo.R-PROMJENE": "Praćene promjene",
        "R-PROMJENE.prolazi": "Dokument nema praćenih promjena.",
        "R-PROMJENE.prisutne": (
            "Dokument sadrži praćene promjene (umetnut, izbrisan ili premješten tekst ili "
            "promijenjeno oblikovanje) koje nisu prihvaćene. Ono što vidiš na zaslonu možda "
            "nije ono što će se ocjenjivati. Ostale provjere ocijenile su rad kao da su sve "
            "promjene prihvaćene. Prihvati ih i isključi praćenje: Pregled (Review) → "
            "Prihvati (Accept) → Prihvati sve promjene i zaustavi praćenje (Accept All Changes "
            "and Stop Tracking)."
        ),
        "pravilo.R-OKVIRI": "Tekstni okviri",
        "R-OKVIRI.prolazi": "Naslovi i osnovni tekst nisu u tekstnim okvirima.",
        "R-OKVIRI.naslov_u_okviru": (
            "Naslov (sažetka, poglavlja ili literature) nalazi se u tekstnom okviru ili obliku, "
            "a ne u tijelu dokumenta. Tekst u okviru ne pripada toku dokumenta: ne ulazi u "
            "sadržaj (Table of Contents), ne numerira se i provjera stilova ga ne vidi. Označi "
            "tekst u okviru, izreži ga (Ctrl+X), obriši okvir, a tekst zalijepi (Ctrl+V) na "
            "pravo mjesto u tijelu dokumenta i primijeni stil kakav taj naslov treba imati."
        ),
        "R-OKVIRI.tekst_u_okviru": (
            "Osnovni tekst nalazi se u tekstnom okviru ili obliku, a ne u tijelu dokumenta. "
            "Tekst u okviru ne pripada toku dokumenta i provjera stilova ga ne vidi. Označi "
            "tekst u okviru, izreži ga (Ctrl+X), obriši okvir, a tekst zalijepi (Ctrl+V) na "
            "pravo mjesto u tijelu dokumenta i primijeni stil osnovnog teksta. Kratke oznake i "
            "opisi slika smiju ostati u okviru."
        ),
        "poravnanje.lijevo": "lijevo (Align Left)",
        "poravnanje.sredina": "centrirano (Center)",
        "poravnanje.desno": "desno (Align Right)",
        "poravnanje.obostrano": "obostrano (Justify)",
        "poravnanje.ostalo": "drugačije poravnanje",
        "prored.jednostruko": "jednostruko (Single)",
        "prored.1_5": "1,5 retka (1.5 lines)",
        "prored.dvostruko": "dvostruko (Double)",
        "prored.visestruko": "višestruko {retci} (Multiple)",
        "opce.neprovjerljivo": (
            "Ovo pravilo nije bilo moguće pouzdano provjeriti ({razlog}). "
            "Pitaj nastavnika da pregleda ovaj dio rada."
        ),
        "batch.naslov": "Batch provjera predaja",
        "batch.opis": (
            "Provjerava sve predane radove u mapi i podmapama istim pravilima kao web "
            "provjera, uz točan naziv prema zamrznutom popisu. Ništa se ne šalje na mrežu "
            "i ništa se u mapi predaja ne mijenja."
        ),
        "batch.mapa": "Mapa s predanim radovima",
        "batch.mapa_pomoc": (
            "Mapa preuzeta iz e-učenja. Wordove privremene (~$…), skrivene i sistemske "
            "datoteke se preskaču."
        ),
        "batch.mapa_prazna": "Upiši putanju mape s predanim radovima.",
        "batch.mapa_neispravna": "Mapa predaja mora biti apsolutna putanja postojeće mape.",
        "batch.mapa_u_podacima": (
            "Mapa predaja ne smije biti podatkovna mapa ni mapa unutar nje. Odaberi mapu "
            "s preuzetim radovima."
        ),
        "batch.mapa_necitljiva": "Mapa predaja (ili neka podmapa) nije čitljiva: {razlog}",
        "batch.nije_moguce": "Batch provjera nije moguća – problemi: {broj}",
        "batch.otisak_RAZLICIT": (
            "Margine trenutnog profila razlikuju se od onih u objavljenom PDF-u sa "
            "svojstvima. Studenti su možda oblikovali radove prema drugim marginama."
        ),
        "batch.otisak_NEMA_IZDANOG": (
            "PDF sa svojstvima za ovu vježbu još nije generiran, pa se ne može potvrditi da "
            "su margine iste kao objavljene."
        ),
        "batch.otisak_NECITLJIVO": (
            "Zapis o izdanom PDF-u (izdano.json) nije čitljiv, pa se ne može potvrditi da "
            "su margine iste kao objavljene."
        ),
        "batch.potvrda_otiska": "Razumijem i želim pokrenuti provjeru s trenutnim marginama.",
        "batch.pokreni": "Pokreni batch provjeru",
        "batch.u_tijeku": "Provjeravam datoteku {obradeno} od {ukupno} …",
        "batch.gotovo": "Provjereno datoteka: {broj}.",
        "batch.nema_datoteka": "U mapi predaja nema datoteka za provjeru.",
        "batch.stupac_datoteka": "Datoteka",
        "batch.stupac_student": "Student",
        "batch.stupac_status": "Status",
        "batch.stupac_razlog": "Razlog",
        "batch.student": "{rbr}. {ime} {prezime}",
        "batch.stupac_nacin": "Povezano po",
        "batch.stupac_kandidati": "Kandidati",
        "uparivanje.nacin.TOCAN": "točnom nazivu",
        "uparivanje.nacin.PRIBLIZAN": "približnom nazivu",
        "uparivanje.nacin.PODMAPA": "imenu podmape",
        "uparivanje.nacin.JMBAG": "JMBAG-u s naslovnice",
        "uparivanje.bez_podudaranja": "datoteka nije povezana ni s jednim studentom",
        "uparivanje.dvosmisleno": "dvosmisleno – datoteka odgovara više studenata, a JMBAG ih ne razlučuje",
        "uparivanje.jmbag_nije_na_popisu": "JMBAG s naslovnice nije na zamrznutom popisu",
        "uparivanje.vise_jmbagova": "na naslovnici je više JMBAG-ova s popisa",
        "uparivanje.visestruko": "višestruka predaja – student već ima bolje povezanu datoteku",
        "uparivanje.neaktivan": "datoteka pripada neaktivnom (ispisanom) studentu",
        "batch.razlog_iznimka": "neočekivana greška pri obradi ({greska})",
        "batch.odbijeno.prazna": "datoteka je prazna",
        "batch.odbijeno.neispravan_format": "datoteka nije .docx",
        "batch.odbijeno.stari_doc": "stari Wordov format .doc",
        "batch.odbijeno.makro": "dokument s makronaredbama (.docm)",
        "batch.odbijeno.sifrirana": "dokument je zaštićen lozinkom",
        "batch.odbijeno.prevelika": "datoteka je veća od dopuštene",
        "batch.odbijeno.zip_bomba": "raspakirani sadržaj je prevelik",
        "batch.odbijeno.ostecena": "datoteka je oštećena",
        "zbirna.vjezba": "Vježba",
        "zbirna.verzija": "Verzija profila",
        "zbirna.vrijeme": "Vrijeme provjere",
        "zbirna.list_rezultati": "Rezultati",
        "zbirna.list_nalazi": "Nalazi",
        "zbirna.list_nepovezano": "Nepovezano",
        "zbirna.stupac_rbr": "Rbr.",
        "zbirna.stupac_ime": "Ime",
        "zbirna.stupac_prezime": "Prezime",
        "zbirna.stupac_jmbag": "JMBAG",
        "zbirna.stupac_datoteka": "Naziv datoteke",
        "zbirna.stupac_ukupni_status": "Ukupni status",
        "zbirna.stupac_broj_nalaza": "Broj nalaza koji ne prolaze",
        "zbirna.stupac_pravilo": "Pravilo",
        "zbirna.stupac_status": "Status",
        "zbirna.stupac_lokacija": "Lokacija",
        "zbirna.stupac_ocekivano": "Očekivano",
        "zbirna.stupac_pronadeno": "Pronađeno",
        "zbirna.stupac_opis": "Opis",
        "zbirna.stupac_pojave": "Pojave",
        "zbirna.stupac_razlog": "Razlog",
        "zbirna.stupac_kandidati": "Kandidati",
        "batch.tablica_spremljena": "Zbirna tablica spremljena je u: {putanja}",
        "batch.tablica_nije_spremljena": (
            "Zbirnu tablicu nije moguće spremiti u podatkovnu mapu ({razlog}). Provjeri "
            "dopuštenja mape i pokreni provjeru ponovno."
        ),
        "ukupni_status.SPREMNO": "spremno",
        "ukupni_status.NIJE_SPREMNO": "nije spremno",
        "ukupni_status.ZA_RUCNI_PREGLED": "za ručni pregled",
        "ukupni_status.NIJE_PREDAO": "nije predao",
        "ukupni_status.NEISPRAVAN_FORMAT": "neispravan format",
        "ukupni_status.NEUSPJELA_OBRADA": "neuspjela obrada",
        "ukupni_status.NEAKTIVAN": "neaktivan",
        "ukupni_status.ikona.SPREMNO": "✅",
        "ukupni_status.ikona.NIJE_SPREMNO": "❌",
        "ukupni_status.ikona.ZA_RUCNI_PREGLED": "⚠️",
        "ukupni_status.ikona.NIJE_PREDAO": "➖",
        "ukupni_status.ikona.NEISPRAVAN_FORMAT": "🚫",
        "ukupni_status.ikona.NEUSPJELA_OBRADA": "💥",
        "ukupni_status.ikona.NEAKTIVAN": "⏸️",
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
        "izvjestaj.primjeri": "Primjeri: {primjeri}",
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
    """Prikaz vrijednosti: twipsi kao cm (razmaci kao pt), polutočke kao pt, prored u retcima."""
    if jedinica is Jedinica.TWIPS:
        return f"{_decimalni_zarez(twips_u_cm(iznos))} cm"
    if jedinica is Jedinica.POLUTOCKE:
        return f"{_decimalni_zarez(Decimal(iznos) / 2)} pt"
    if jedinica is Jedinica.TOCKE:
        return f"{_decimalni_zarez(twips_u_pt(iznos))} pt"
    if jedinica is Jedinica.RETCI:
        if iznos == RETCI_PO_RETKU:
            return poruka("prored.jednostruko")
        if iznos == RETCI_PO_RETKU * 3 // 2:
            return poruka("prored.1_5")
        if iznos == 2 * RETCI_PO_RETKU:
            return poruka("prored.dvostruko")
        return poruka("prored.visestruko", retci=_decimalni_zarez(retci_u_broj(iznos)))
    if jedinica is Jedinica.PORAVNANJE:
        return poruka(f"poravnanje.{iznos}")
    if jedinica is Jedinica.BOOL:
        return poruka("vrijednost.da" if iznos else "vrijednost.ne")
    return str(iznos)

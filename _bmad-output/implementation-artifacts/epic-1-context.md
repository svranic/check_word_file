# Epic 1 Context: Student provjerava stranicu, margine i naziv datoteke

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Student na javnoj Streamlit stranici (bez prijave) upisuje redni broj, vidi svoje individualne margine i obrazac naziva datoteke, učitava `.docx` i dobiva izvještaj za naziv datoteke, sekcije i margine, s koracima ispravka na hrvatskom i sažetkom za preuzimanje. Epic postavlja temelje cijelog sustava: projekt i ovisnosti, čistu jezgru (model sekcija, ugovor pravila, nalazi, katalog poruka), formulu margina, profil Vježbe 1, sigurni ulaz i deploy na Streamlit Community Cloud. Na tim temeljima Epic 2 dodaje pravila oblikovanja teksta, a Epici 3 i 4 nastavničke alate.

## Stories

- Story 1.1: Postavljanje projekta i objava prazne studentske stranice
- Story 1.2: Student upisuje redni broj i vidi svoje margine
- Story 1.3: Sigurno učitavanje dokumenta
- Story 1.4: Izvještaj o provjeri i pravilo naziva datoteke
- Story 1.5: Provjera sekcija, margina i stranice
- Story 1.6: Preuzimanje sažetka provjere

## Requirements & Constraints

- Sav tekst koji korisnik vidi je na hrvatskom; Wordovi izbornici pišu se „Hrvatski (English)“. Status se nikad ne prikazuje samo bojom (ikona i tekst), a sučelje je upotrebljivo tipkovnicom.
- Web provjera ne zna ništa o studentima: radi samo s Rbr. i formulom, ne prikazuje ime. Popis studenata nikad nije u repozitoriju ni u web aplikaciji.
- Učitani dokument postoji samo kao `bytes` u memoriji jednog izvođenja: ne ide na disk ni u `st.cache_*`, a u `session_state` smiju biti samo Rbr., odabrana vježba, `Izvjestaj` i UI zastavice. Logovi sadrže samo vrijeme, ID pravila i status.
- Uz polje za učitavanje uvijek je vidljiva napomena `privatnost.obrada` (obrada u SAD-u, samo u memoriji, ništa se ne sprema).
- Ulaz: samo `.docx` (nastavak bez obzira na slova), najviše 10 MB i 100 MB raspakirano; zasebne poruke za `.doc`/`.docm`/`.pdf`, šifrirane, prazne, oštećene i zip-bomb datoteke, nikad traceback.
- Statusi `prošlo` / `ne prolazi` / `neprovjerljivo`; iznimka nikad ne daje `prošlo`; „spremno“ samo kad su sva pravila `prošlo`. Pravila su neovisna, jedno ne zaustavlja druga.
- Formula margina: osnovica ± do 0,5 cm u koracima 0,1 cm, jedinstvena kombinacija za Rbr. 1–500, barem dvije pomaknute margine, nikad 2,5 cm sa svih strana; novo sjeme = novi raspored.
- Neispravan profil u webu daje samo „provjera trenutno nije dostupna“.
- Brzina: web provjera < 10 s po dokumentu; pri preopterećenju poruka „pokušaj ponovno za minutu“. Besplatni plan Streamlit Community Clouda.

## Technical Decisions

- **Stack (pinovi):** Python 3.12, streamlit 1.65.0, python-docx ==1.2.0 (lxml tranzitivno), pydantic 2.14.1, openpyxl 3.1.5 i fpdf2 2.8.9 (samo lokalno), pytest 9.1.1. `uv` s `pyproject.toml` + `uv.lock` kao jedinim izvorom ovisnosti; nema `requirements.txt`. Projekt se instalira kao paket.
- **Struktura:** `apps/student.py` (Cloud ulaz), `apps/nastavnik.py`, `provjera/jezgra/` (`model/`, `pravila/`, `formula.py`, `naziv.py`, `rbr.py`, `jedinice.py`, `profil.py`, `provjera.py`, `ulaz.py`, `poruke.py`), `provjera/adapteri/`, `profili/vjezba_1.toml`, `tests/referentni/vjezba_1/`, `tests/alati/`, `.streamlit/config.toml` u korijenu (samo tema i `maxUploadSize`).
- **Smjer ovisnosti:** `apps → adapteri → jezgra`. Jezgra ne uvozi `streamlit`, `openpyxl`, `fpdf`, ne čita sat, ne otvara datoteke osim resursa paketa, ne konfigurira logging. `apps/student.py` tranzitivno ne smije dohvatiti `provjera.adapteri`, `openpyxl` ni `fpdf`. Oba pravila čuvaju testovi.
- **Repozitorij:** `.gitignore` ignorira `samples/` te `*.xlsx`, `*.csv`, `*.docx` izvan `tests/`; test nad `git ls-files` to provjerava. Testni podaci su isključivo sintetski.
- **Ulazni ugovor:** `provjeri(docx: bytes, profil: Profil, kontekst: KontekstProvjere) -> Izvjestaj`; `KontekstProvjere` je zamrznuta dataclass s točno `naziv_datoteke`, `rbr`, `ocekivani_naziv | None`, `nacin_uparivanja | None` (web šalje `None`/`None`).
- **Model:** `.docx` se parsira jednom u nepromjenjivi `DocModel` u `jezgra/model/`; sav python-docx/lxml pristup samo tamo. Uloge sekcija (`NASLOVNICA`/`TIJELO`) dodjeljuje isključivo `jezgra/model/uloge.py`: ≥ 2 sekcije → prva je naslovnica; jedna sekcija → `TIJELO`.
- **Pravila:** `(DocModel, KontekstProvjere, Postavke) -> list[Nalaz]`, jedno po datoteci `jezgra/pravila/r_<id>.py` s klasom `Postavke` (nasljeđuje `PostavkeBaza` s `ukljuceno`), registrirano pod stabilnim ID-om. Vraća nesažete nalaze (i za prolaz barem jedan). Pokretač hvata iznimke (→ `NEPROVJERLJIVO`) i jedini sažima ponavljanja (`pojave`).
- **Nalaz/izvještaj:** `Nalaz(pravilo_id, status, lokacija, ocekivano, pronadeno, izvor, poruka_kljuc, parametri, pojave)`; `Vrijednost(iznos, jedinica)` s jedinicama `TWIPS|POLUTOCKE|TEKST|BOOL`; `Lokacija(dio, sekcija, odlomak, isjecak)` 1-bazirano; `Izvjestaj(odbijeno, nalazi, profil_verzija, rbr)`. `status_pravila` (`NEPROVJERLJIVO > NE_PROLAZI > PROSLO`), `spremnost`, `ukupni_status` postoje samo u jezgri.
- **Jedinice:** duljine u cijelim twipsima, fontovi u polutočkama, pomaci formule u mm; pretvorbe samo u `jedinice.py`; usporedba samo kroz `jedinice.unutar_tolerancije`, nikad float usporedba. Profil piše mjere kao „3 cm“ / „12 pt“.
- **Jedan izvor:** `formula.margine`, `formula.otisak` (SHA-256 + `FORMULA_VERZIJA`, 12 hex), `naziv.kanonski` / `odgovara_obrascu` / `kljuc_uparivanja`, `rbr.parsiraj -> int | GreskaUnosa`, `profil.verzija` (SHA-256 kanonskog JSON-a, 8 hex). Snapshot test zaključava margine za Rbr. 1–500.
- **Profil:** TOML (`[vjezba]` s `id`, `naziv`, `objavljeno`; `[naziv_datoteke]`; `[formula]`; `[tolerancije]`; `[pravila.<ID>]`), učitava se samo kroz `profil.ucitaj(bytes)` (tomllib + pydantic, `extra="forbid"`); greške → `GreskaProfila` s popisom svih grešaka, nikad djelomičan profil. Web nudi samo profile s `objavljeno = true`.
- **Poruke:** sav korisnički tekst iz `jezgra/poruke.py` po ključu `<pravilo_id>.<slucaj>`; vrijednosti se formatiraju samo kroz `poruke.formatiraj` (cm s decimalnim zarezom, pt). Test pokrivenosti ključeva.
- **Konvencije:** identifikatori na hrvatskom bez dijakritika; dijakritici samo u `poruke.py`. Očekivana stanja su tipizirani rezultati (`RazlogOdbijanja`, `GreskaUnosa`) ili `Greska*` iznimke. Jezgra ne čita sat; adapteri dodaju vrijeme. `uv run pytest` prije svakog pusha.
- **Deploy:** Streamlit Community Cloud iz `main`, ulaz `apps/student.py`, Python 3.12 odabran u Advanced settings pri prvom deployu (kasnija promjena traži ponovni deploy). Nema CI-ja u v1.

## UX & Interaction Patterns

- Redoslijed izvještaja: status spremnosti → nalazi koji ne prolaze → `neprovjerljivo` → prošle provjere. Svaki nalaz: ikona + tekst statusa, lokacija, očekivano/pronađeno, korak ispravka; tehnički detalji (izvor vrijednosti) u proširivom dijelu.
- Margine se prikazuju u cm s decimalnim zarezom uz uputu Izgled (Layout) → Margine (Margins) → Prilagođene margine (Custom Margins).
- Promjena Rbr. ili vježbe briše prethodnu datoteku i izvještaj.
- Sažetak za preuzimanje je HTML iz `Izvjestaj`-a (Rbr., vježba, verzija profila, vrijeme, status po pravilu), bez isječaka teksta i naziva datoteke.

## Cross-Story Dependencies

- 1.1 postavlja projekt, testove arhitekture i praznu stranicu; sve ostale priče grade na njoj.
- 1.2 uvodi `jedinice`, `profil`, `formula`, `rbr` i `profili/vjezba_1.toml`, potrebne za 1.4 i 1.5.
- 1.3 (`ulaz.py`, `RazlogOdbijanja`) prethodi pokretaču provjere iz 1.4.
- 1.4 uvodi tipove nalaza, registar pravila, pokretač i prikaz izvještaja; 1.5 dodaje `DocModel`, uloge i pravila sekcija/margina; 1.6 koristi `Izvjestaj`.
- Epic 2 proširuje `DocModel`, uloge i registar; Epici 3–4 koriste iste funkcije jezgre (`formula`, `naziv`, `profil`) iz adaptera.

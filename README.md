# Provjera Word i Excel vježbi

Alat za provjeru vježbi kolegija *Osnove geoinformatike*: tehničko oblikovanje Word
zadaća i formule u Excel trigonometrijskim obrascima.

- `apps/student.py`: javna web provjera za studente (Streamlit Community Cloud). Jedan link, a u izborniku su i Word i Excel vježbe (`profili/word/` i `profili/excel/`).
- `apps/nastavnik.py`: lokalna aplikacija za nastavnika (priprema Word vježbe, batch provjera).
- `python -m provjera.excel`: izrada Excel predložaka i provjera predaja (naredbeni redak).

## Struktura

| Mapa | Sadržaj |
|---|---|
| `provjera/zajednicko/` | naziv datoteke, sigurni ulaz (.docx i .xlsx), status provjere |
| `provjera/word/jezgra/`, `provjera/word/adapteri/` | provjera Word zadaća |
| `provjera/excel/jezgra/` | čitač .xlsx, izračun formula, tipovi zadataka, provjera |
| `provjera/excel/adapteri/` | izrada predloška (openpyxl), skupna provjera i zbirni izvještaj |
| `profili/word/`, `profili/excel/` | profili vježbi (TOML) |
| `tests/word/`, `tests/excel/`, `tests/zajednicko/` | testovi; `tests/test_arhitektura.py` čuva granice paketa |

## Pokretanje

Potreban je [uv](https://docs.astral.sh/uv/). Ovisnosti se nalaze samo u `pyproject.toml` i `uv.lock`.

```bash
uv sync                                   # instalira Python 3.12 okolinu i paket provjera
uv run pytest                             # obavezno prije svakog pusha
uv run streamlit run apps/student.py      # studentska stranica
uv run streamlit run apps/nastavnik.py    # nastavnička stranica (samo lokalno)
```

Aplikacije se pokreću iz korijena repozitorija kako bi se učitao `.streamlit/config.toml`.

## Excel vježbe (trigonometrijski obrasci)

Tipovi zadataka: `sinus` (obrazac 13), `kosinus` (obrazac 14 – cos) i `tangens` (obrazac 14 – tan).
Profil (`profili/excel/vjezba_2.toml`) određuje koji su zadaci u vježbi (svaki je zaseban list),
sjeme osobnih podataka i sufiks naziva datoteke. Profil određuje i:

- `raspodjela`: `"svi"` (svaki student rješava sve zadatke), `"redom"` (sinus, kosinus, tangens naizmjence po redoslijedu ISVU popisa) ili `"nasumicno"` (jedan zadatak prema JMBAG-u). Osobni predložak tada ima samo list dodijeljenog zadatka, a zadatak je upisan i u svojstva datoteke.
- `korak_mjerenja`: točnost mjerenih kutova u sekundama, npr. 10. Kod sinusova poučka student odstupanje fβ raspoređuje na izjednačene kutove u cijelim sekundama. Provjera traži da svaki popravak bude ⌊fβ/3⌋ ili ⌈fβ/3⌉ i da je zbroj izjednačenih kutova točno 180°.

```bash
# prazan predložak (student sam upisuje podatke)
uv run python -m provjera.excel predlozak profili/excel/vjezba_2.toml izlaz/
# osobni predložak za svakog studenta iz ISVU izvoza: vlastiti, zaključani ulazni podaci
uv run python -m provjera.excel predlozak profili/excel/vjezba_2.toml izlaz/ --popis isvu.xlsx
# predložak s referentnim formulama (nastavnikovo rješenje)
uv run python -m provjera.excel predlozak profili/excel/vjezba_2.toml izlaz/ --rjesenje
# provjera mape predaja sa zbirnim izvještajem
uv run python -m provjera.excel provjeri profili/excel/vjezba_2.toml predaje/ --popis isvu.xlsx --izvjestaj zbirno.xlsx
```

Za svaku žutu ćeliju obrasca provjera utvrđuje: (1) je li upisana formula, a ne broj,
(2) je li vrijednost točna za ulazne podatke u datoteci i (3) vrijedi li formula općenito:
formule studenta ponovno se izračunavaju s nekoliko drugih skupova ulaznih podataka
(i b > c i b < c, zatvaranje kutova obaju predznaka) i moraju i tada dati točan rezultat.
Uz osobne predloške provjera uspoređuje ulazne podatke s izdanima, otkriva predložak
izdan drugom studentu i u zbirnom izvještaju navodi parove predaja sa sličnim formulama.

Listovi su zaštićeni lozinkom: zaglavlje (retci 1–4, ime i JMBAG) i ulazni podaci su
zaključani, a struktura radne knjige (dodavanje, brisanje i preimenovanje listova) je
zaštićena. Lozinka se zadaje s `--lozinka`; bez nje naredba generira slučajnu i zapisuje
je u izlaznu mapu (`LOZINKA_ZASTITE.txt`). Provjera lozinku ne treba, a promijenjen
JMBAG u zaglavlju lista prijavljuje kao grešku.

## Privatnost

Stvarni podaci (ISVU izvozi, studentski radovi, mapa `samples/`) nikad ne ulaze u repozitorij. To osigurava `.gitignore`, a provjerava test `tests/test_arhitektura.py`. U `tests/` smiju biti samo sintetski podaci.

## Deploy na Streamlit Community Cloud

1. Na GitHubu napravi repozitorij i poveži ga lokalno: `git remote add origin <URL>`.
2. Pokreni `uv run pytest` i provjeri da `git status` ne prikazuje ništa iz `samples/`.
3. Napravi prvi commit i pošalji ga: `git push -u origin main`.
4. Na [share.streamlit.io](https://share.streamlit.io) odaberi *Create app*, zatim repozitorij, granu `main` i datoteku `apps/student.py`.
5. U *Advanced settings* odaberi **Python 3.12**. Verzija se kasnije ne može promijeniti bez brisanja i ponovnog deploya.
6. Pokreni deploy. Cloud instalira ovisnosti iz `uv.lock`.

Aplikacija se uspava nakon 12 sati bez prometa, pa je otvori na dan roka predaje.

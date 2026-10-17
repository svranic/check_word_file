# Check lista za objavu na Streamlit Community Cloudu

Na Cloud ide samo studentska aplikacija (`apps/student.py`). Nastavnička aplikacija uvijek radi lokalno.

## 1. Prije pusha (lokalno)

- [ ] `uv run pytest`: svi testovi prolaze.
- [ ] `git status` je čist i ne prikazuje ništa iz `samples/`, nijedan `.xlsx`/`.csv`/`.docx` izvan `tests/` ni podatkovnu mapu `ProvjeraWord`.
- [ ] U profilu vježbe (`profili/vjezba_1.toml`) provjereno je:
  - [ ] `objavljeno = true`
  - [ ] `fiksne_margine` ima željenu vrijednost (`true` = iste margine, bez Rbr.)
  - [ ] osnovice margina, naslovnica, naziv datoteke (`sufiks`) i pravila odgovaraju uputama za vježbu
- [ ] Ako se profil mijenjao: generator referentnog skupa (`uv run python tests/alati/generator.py`) je pokrenut i `uv run pytest` ponovno prolazi.
- [ ] Lokalna proba: `uv run streamlit run apps/student.py`. Odaberi vježbu i učitaj ispravan rad. Mora pisati „Rad je spreman za predaju.“

## 2. GitHub

- [ ] Repozitorij na GitHubu je napravljen (može biti privatan) i povezan: `git remote add origin <URL>`.
- [ ] `git push -u origin main`
- [ ] Na GitHubu provjeri da nema osobnih podataka: mapa `samples/` ne postoji, a `_bmad-output/` i `.claude/` nisu objavljeni.

## 3. Streamlit Community Cloud (prvi deploy)

- [ ] Na [share.streamlit.io](https://share.streamlit.io) se prijavi GitHub računom i odaberi **Create app**.
- [ ] Repozitorij: tvoj repo, grana `main`, datoteka **`apps/student.py`**.
- [ ] *App URL*: odaberi kratku adresu, npr. `provjera-word`.
- [ ] *Advanced settings*: **Python 3.12**. Ovo se kasnije ne može promijeniti bez brisanja aplikacije.
- [ ] Secrets: ništa, aplikacija nema tajni.
- [ ] Deploy. U logu provjeri da su ovisnosti instalirane bez greške (`streamlit==1.65.0`, `python-docx`, `pydantic`). Ako Cloud ne prepozna `uv.lock`, napravi `requirements.txt` naredbom `uv export --no-dev --no-hashes -o requirements.txt`, commitaj ga i ponovi deploy.

## 4. Nakon deploya

- [ ] Otvori javnu adresu u privatnom prozoru preglednika (bez prijave). Stranica se učitava, vidi se poruka o privatnosti, a vježba je ponuđena.
- [ ] Učitaj ispravan sintetski rad (npr. `tests/referentni/vjezba_1/ispravan.docx`, preimenovan prema obrascu naziva). Rezultat: spreman za predaju.
- [ ] Učitaj jedan pokvareni primjer (npr. `krive_margine_tijela.docx`). Rezultat: nije spreman, uz jasnu poruku.
- [ ] Preuzmi HTML sažetak i provjeri da se otvara.
- [ ] *Settings → Sharing* aplikacije: postavi da je **javna** („This app is public“), inače studenti moraju imati Streamlit račun.

## 5. Poveznica i PDF za studente

- [ ] Ako stvarna adresa nije ista kao `poveznica` u `[vjezba]` profila: ispravi `poveznica`, pokreni `uv run pytest`, pa commitaj i pushaj. Cloud se sam ponovno pokreće.
- [ ] U nastavničkoj aplikaciji pokreni **Samoprovjeru**, provjeri da je spremnost „spremno“ i **Generiraj PDF**. PDF mora sadržavati stvarnu poveznicu.
- [ ] Objavi PDF i upute u e-učenju.

## 6. Tijekom vježbe

- [ ] Na dan roka (i dan prije) otvori aplikaciju da se probudi. Spava nakon 12 sati bez prometa.
- [ ] Svaka promjena profila ide redom: `uv run pytest`, zatim commit, zatim push. Ako se promijene margine, ponovno generiraj i objavi PDF.
- [ ] Nakon predaje: batch provjera radi lokalno u nastavničkoj aplikaciji, a ne na Cloudu.

# Provjera Word dokumenata

Alat za provjeru tehničkog oblikovanja Word zadaća kolegija *Osnove geoinformatike*.

- `apps/student.py`: javna web provjera za studente (Streamlit Community Cloud).
- `apps/nastavnik.py`: lokalna aplikacija za nastavnika (priprema vježbe, batch provjera).

## Pokretanje

Potreban je [uv](https://docs.astral.sh/uv/). Ovisnosti se nalaze samo u `pyproject.toml` i `uv.lock`.

```bash
uv sync                                   # instalira Python 3.12 okolinu i paket provjera
uv run pytest                             # obavezno prije svakog pusha
uv run streamlit run apps/student.py      # studentska stranica
uv run streamlit run apps/nastavnik.py    # nastavnička stranica (samo lokalno)
```

Aplikacije se pokreću iz korijena repozitorija kako bi se učitao `.streamlit/config.toml`.

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

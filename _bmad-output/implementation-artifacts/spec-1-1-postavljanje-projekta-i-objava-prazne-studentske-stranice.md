---
title: 'Postavljanje projekta i objava prazne studentske stranice'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: 'NO_VCS'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Repozitorij nema koda ni okruženja, pa nijedna priča ne može početi. Student nema poveznicu na stranicu za provjeru, a invarijante privatnosti i čiste jezgre (AD-1, AD-2) nisu zaštićene testovima.

**Approach:** Postaviti uv projekt (Python 3.12, pinovi iz spinea) sa strukturom iz spinea, testove arhitekture i privatnosti te praznu studentsku stranicu s naslovom i napomenom o privatnosti iz kataloga poruka, spremnu za deploy na Streamlit Community Cloud.

## Boundaries & Constraints

**Always:** `pyproject.toml` + `uv.lock` jedini su izvor ovisnosti; paket `provjera` instalira se kao paket (`build-system`), pa ga `apps/` uvoze bez diranja `sys.path`. Sav tekst stranice dolazi iz `provjera/jezgra/poruke.py`. Identifikatori na hrvatskom bez dijakritika. `.streamlit/config.toml` u korijenu sadrži samo temu i `maxUploadSize`. Testni podaci samo sintetski.

**Odluka (git i deploy):** lokalni `git init` na grani `main`, bez commita i bez remotea. Test privatnosti pada ako git repozitorij ne postoji. Push na GitHub i deploy na Cloud (Python 3.12 u Advanced settings) izvodi korisnik prema listi koraka u README-u.

**Never:** nema `requirements.txt`, `runtime.txt` ni `sys.path` hackova; nema logike provjere, profila, formule ni polja za Rbr./učitavanje (priče 1.2–1.6); ne dirati `samples/`, `_bmad/`, `_bmad-output/` osim ovog speca; nijedna datoteka iz `samples/` ne smije ući u git.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Čisto stablo | `uv run pytest` | svi testovi prolaze | N/A |
| Praćen osobni podatak | `.docx`/`.xlsx`/`.csv` izvan `tests/` ili bilo što iz `samples/` u `git ls-files` | test privatnosti pada i navodi putanje | N/A |
| Studentska app povlači zabranjeno | `apps/student.py` tranzitivno uvozi `provjera.adapteri`, `openpyxl` ili `fpdf` | test grafa uvoza pada i navodi modul | N/A |
| Jezgra krši AD-1 | modul u `provjera/jezgra/` uvozi `streamlit`, `openpyxl`, `fpdf`, `time`, `logging.config` ili poziva `datetime.now`/`today`/`utcnow`, `date.today` | test jezgre pada s datotekom i retkom | N/A |
| Student otvori stranicu | `uv run streamlit run apps/student.py` | naslov alata i napomena `privatnost.obrada`, sve na hrvatskom | N/A |

</frozen-after-approval>

## Code Map

- `samples/` -- stvarni podaci (ISVU `.xlsx`, studentski `.docx`); samo `.gitignore`, nikad čitati u testovima
- `_bmad-output/implementation-artifacts/epic-1-context.md` -- stack, struktura i konvencije epica
- Okruženje: uv 0.11.28 (spine navodi 0.13.0; ne postavljati `required-version` iznad instalirane), lokalni CPython 3.12.8, git 2.45
- Nema postojećeg koda; sve datoteke su nove

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- projekt `provjera-word`, `requires-python = ">=3.12,<3.13"`, ovisnosti točno: `streamlit==1.65.0`, `python-docx==1.2.0`, `pydantic==2.14.1`, `openpyxl==3.1.5`, `fpdf2==2.8.9`; grupa `dev`: `pytest==9.1.1`; `hatchling` build s paketom `provjera`; `[tool.pytest.ini_options] testpaths = ["tests"]` -- jedini izvor ovisnosti
- [x] `.python-version` -- `3.12` -- lokalni uv bira 3.12
- [x] `uv.lock` -- generirati `uv lock` -- zaključane verzije za Cloud
- [x] `provjera/__init__.py`, `provjera/jezgra/__init__.py`, `provjera/jezgra/model/__init__.py`, `provjera/jezgra/pravila/__init__.py`, `provjera/adapteri/__init__.py` -- prazni paketi (docstring) -- struktura iz spinea
- [x] `provjera/jezgra/poruke.py` -- `KATALOG: Mapping[str, str]` s ključevima `app.naslov`, `app.podnaslov`, `privatnost.obrada` (obrada na poslužiteljima u SAD-u, samo u memoriji, ništa se ne sprema) i `poruka(kljuc, **parametri) -> str` koja baca `KeyError` za nepoznat ključ -- AD-11 temelj; `formatiraj` dolazi u 1.2
- [x] `apps/student.py` -- `st.set_page_config` + `st.title`, podnaslov i `st.info` s `privatnost.obrada`, sve preko `poruke.poruka` -- prazna studentska stranica
- [x] `apps/nastavnik.py` -- naslov lokalne nastavničke stranice iz kataloga (`nastavnik.naslov`) -- mjesto za Epic 3/4
- [x] `profili/.gitkeep`, `tests/referentni/vjezba_1/.gitkeep`, `tests/alati/.gitkeep`, `provjera/resursi/fontovi/.gitkeep` -- prazne mape iz spinea
- [x] `.streamlit/config.toml` -- `[server] maxUploadSize = 10` i `[theme]` (svijetla, neutralna) -- dijele ga obje aplikacije
- [x] `.gitignore` -- `samples/`, `*.xlsx`, `*.csv`, `*.docx` uz `!tests/**/` iznimke, `.venv/`, `__pycache__/`, `.pytest_cache/` -- AD-2
- [x] `tests/test_arhitektura.py` -- (1) AST test jezgre: zabranjeni uvozi i pozivi sata iz matrice; (2) test grafa uvoza: u podprocesu `uv`-ovog interpretera (`sys.executable`) izvesti `apps/student.py` kroz `runpy` i provjeriti da `sys.modules` ne sadrži `provjera.adapteri*`, `openpyxl*`, `fpdf*`; (3) test `git ls-files` iz matrice; (4) testovi kataloga: ključevi iz `apps/student.py` postoje, `poruka` baca `KeyError` za nepoznat ključ -- čuvari AD-1, AD-2, AD-11
- [x] `.git/` -- `git init -b main` u korijenu projekta (bez commita) -- preduvjet testa privatnosti
- [x] `README.md` -- kratko: `uv sync`, `uv run pytest`, `uv run streamlit run apps/student.py`, koraci deploya -- upute za pokretanje

**Acceptance Criteria:**
- Given svježi klon, when `uv sync` pa `uv run pytest`, then svi testovi prolaze bez mreže osim instalacije, a `requirements.txt` ne postoji
- Given namjerno dodan `import openpyxl` u `provjera/jezgra/poruke.py`, when `uv run pytest`, then test jezgre i test grafa uvoza padaju (provjera se izvodi i vraća)
- Given pokrenuta `apps/student.py`, when se stranica otvori, then nema greške u konzoli i vidi se naslov i napomena o obradi u SAD-u

## Implementation Notes

- Implementirano izravno u glavnoj sesiji (bez podagenta). `uv lock` je razriješio 54 paketa na lokalnom CPythonu 3.12.8; `uv run pytest`: 21 test prolazi.
- Test `git ls-files` koristi `--cached --others --exclude-standard`, pa provjerava i datoteke koje bi `git add .` dodao. Tako štiti i prije prvog commita.
- Kriterij prihvaćanja provjeren: ubačen `import openpyxl` u `poruke.py` ruši `test_jezgra_ne_krsi_ad1` i `test_student_ne_uvozi_zabranjene_module`, a datoteka je zatim vraćena. Uz to, `streamlit run apps/student.py --server.headless true` vraća health `ok`.
- Uočeno: pravilo `*.csv` iz AD-2 ignorira i CSV datoteke BMAD alata (`_bmad/`, `.agents/`, `.claude/`). To nisu osobni podaci, ali neće ući u commit ako se ti alati budu verzionirali.

## Spec Change Log

## Review Triage Log

| # | Izvor | Nalaz | Presuda | Dokaz / odluka |
|---|-------|-------|---------|----------------|
| 1 | blind | `uv.lock` nedostaje | false | `uv.lock` postoji (103 kB), samo nije bio u popisu datoteka diffa; `uv lock --check` prolazi |
| 2 | blind, edge | `provjera` se možda ne uvozi na Cloudu; test grafa uvoza radi iz korijena pa to ne bi uhvatio | medium (test) / maybe-false (Cloud) | patch: test sada radi iz privremenog direktorija i oslanja se na instalirani paket. Ponašanje Clouda odgođeno u deferred-work |
| 3 | blind | provjera AD-1 propušta `provjera.adapteri` i relativne uvoze | medium | patch: zabranjen `provjera.adapteri`, relativni uvozi se razrješavaju, dodani testni slučajevi |
| 4 | blind | AD-1 ne provjerava I/O (`open`, `os`, `socket`…) | low | odbijeno: matrica namjerno navodi popis; provjera bi tražila nove grane, a `open` će trebati za resurse paketa |
| 5 | blind, edge | popis osobnih formata ne pokriva `.pdf`, `.doc`, `.xls`, `.xlsm` | low | patch: proširen `.gitignore` i `OSOBNI_NASTAVCI` (izravna korekcija) |
| 6 | blind, edge | bez gita test baca `FileNotFoundError`; README ne spominje `git init` | low | odbijeno: test i dalje glasno pada; repozitorij je inicijaliziran, a klon ga ima |
| 7 | blind | telemetrija Streamlita nije isključena | low | odbijeno: ne šalje sadržaj dokumenta; konvencija spinea ograničava `config.toml` na temu i `maxUploadSize` |
| 8 | blind, edge | test kataloga ne hvata doslovni tekst ni dinamičke ključeve | low | odbijeno: nema takvih poziva; zahtijevalo bi dodatnu složenost |
| 9 | blind, edge | `poruka` ne razlikuje nedostajući parametar od nepoznatog ključa | low | odbijeno: katalog još nema parametara; ulazi u `formatiraj` (priča 1.2) |
| 10 | blind | savjet o spavanju aplikacije je krhak | low | odbijeno: operativna napomena, izvan koda |
| 11 | edge | `from logging import basicConfig` prolazi | low | patch: `logging.basicConfig` dodan u zabranjene uvoze (jedna stavka) |
| 12 | edge | dinamički `__import__` / `import_module` prolazi | low | odbijeno: malo vjerojatno, fix dodaje granu |
| 13 | edge | prazan stdout daje neprozirni `IndexError` | low | odbijeno: test i dalje pada; `returncode` provjera hvata rušenje |
| 14 | edge | dekodiranje stderr-a na Windowsima može baciti `UnicodeDecodeError` | low | patch: `errors="replace"` (izravna korekcija) |
| 15 | edge | `Samples/` s velikim slovom nije označen | low | patch: usporedba prefiksa bez obzira na veličinu slova |
| 16 | verification | napomena o privatnosti provjerena samo statički, ne iscrtavanjem | medium | patch: dodan `AppTest` koji provjerava naslov i `st.info` s `privatnost.obrada` |

## Design Notes

Test grafa uvoza je dinamički (stvarni `sys.modules` nakon izvođenja skripte), a ne statički AST, jer hvata i tranzitivne uvoze iz biblioteka. Streamlit izvan `streamlit run` radi u „bare mode“ i samo ispisuje upozorenja, pa je `runpy.run_path` siguran. Izvođenje u podprocesu sprječava da drugi testovi već napune `sys.modules`.

## Verification

**Commands:**
- `uv lock --check` -- expected: lock usklađen s `pyproject.toml`
- `uv run pytest -q` -- expected: svi testovi prolaze
- `uv run streamlit run apps/student.py --server.headless true` (kratko, pa zaustaviti) -- expected: server se pokreće bez traceback-a

**Manual checks (if no CLI):**
- `git status --ignored` -- `samples/` je na popisu ignoriranih

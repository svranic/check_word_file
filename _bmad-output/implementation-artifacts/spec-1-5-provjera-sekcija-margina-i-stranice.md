---
title: 'Provjera sekcija, margina i stranice'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: 'b06c1dbf4bb3ddabdbdcb00ce3eca422ae1e5f6c'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `DocModel` je prazan, pa provjera ne zna je li naslovnica zasebna sekcija ni odgovaraju li margine i stranica Rbr. studenta. To su glavni zahtjevi Vježbe 1 za izgled stranice.

**Approach:** Model čita sekcije (margine, gutter, veličinu i orijentaciju stranice, tip početka sekcije) i zrcalne margine, a `uloge.py` dodjeljuje `NASLOVNICA`/`TIJELO`. Pravila R-SEKCIJE i R-MARGINE provjeravaju FR-17 i FR-18. Uz njih dolazi sintetski referentni skup s generatorom pokvarenih varijanti.

## Boundaries & Constraints

**Always:**
- Sav pristup python-docx/lxml je u `jezgra/model/`. Preferira se dokumentirani API python-docx-a (`Section.*_margin`, `gutter`, `page_width/height`, `orientation`, `start_type`); `settings.xml` se čita samo za `w:mirrorMargins`.
- Duljine su cijeli twipsi i uspoređuju se kroz `unutar_tolerancije`.
- Očekivane margine tijela daje isključivo `formula.margine(kontekst.rbr, profil.formula)`.
- Dimenzije A4 i tolerancije dolaze iz profila.
- Dokument koji python-docx ne može otvoriti (`BadZipFile`, nedostajući dio, neispravan XML) daje `Izvjestaj` s `odbijeno = OSTECENA`.
- Testni `.docx` dokumenti su sintetski.

**Never:**
- nema odlomaka, stilova ni podnožja (Epic 2);
- pravila ne čitaju XML;
- `samples/` se ne commita, a test nad stvarnim uzorkom preskače se ako uzorak ne postoji.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Ispravan rad | 2 sekcije: naslovnica 2,5 cm, sekcija 2 „Sljedeća stranica“ s marginama za Rbr. 54, A4 uspravno | R-SEKCIJE i R-MARGINE `PROSLO` | N/A |
| Jedna sekcija | jedna sekcija s marginama za Rbr. 54 | sekcija je `TIJELO`; R-SEKCIJE `NE_PROLAZI` s uputom Izgled (Layout) → Prijelomi (Breaks) → Sljedeća stranica (Next Page); R-MARGINE `PROSLO` | N/A |
| Drugi tip prijeloma | sekcija 2 „Neprekinuto“ (continuous) | R-SEKCIJE `NE_PROLAZI` | N/A |
| Krive margine | tijelo ili naslovnica izvan tolerancije | R-MARGINE `NE_PROLAZI`: broj sekcije, sve četiri margine (pronađeno i očekivano, u cm) i tolerancija | N/A |
| Unutar tolerancije | margina odstupa ≤ tolerancije (17 twipsa) | `PROSLO` | N/A |
| Stranica | Letter, pejzažno, gutter > 0, zrcalne margine | R-MARGINE `NE_PROLAZI` s odgovarajućim nalazom | N/A |
| Oštećen dokument | prošao je `ulaz`, ali ga python-docx ne može otvoriti | `odbijeno = OSTECENA` | bez traceback-a |
| Stvarni uzorak | `samples/Lucija_Šimek_GiG_OG_Vjezba_1.docx` (samo lokalno) | R-SEKCIJE `NE_PROLAZI` | `skip` ako ne postoji |

</frozen-after-approval>

## Code Map

- `provjera/jezgra/model/__init__.py` -- privremeni `DocModel` i `procitaj`: zamijeniti
- `provjera/jezgra/provjera.py` -- `provjeri`: `model.procitaj` u `try`; dodati `NeispravanDokument` → `odbijeno=OSTECENA`
- `provjera/jezgra/profil.py` -- `Duljina`/`DuljinaMm`/`_mjera` premjestiti u `jezgra/tipovi.py` (pravila ih trebaju, a uvoz iz `profil` bio bi kružan); `Tolerancije` dobiva `stranica`
- `provjera/jezgra/nalaz.py` -- `Nalaz.parametri`: dopustiti `Vrijednost` kao vrijednost
- `provjera/jezgra/poruke.py` -- `tekst_nalaza`: formatirati i `Vrijednost` iz `parametri`
- `provjera/jezgra/pravila/r_naziv.py` -- uzorak za nova pravila (registracija, `Postavke`, poruke)
- `_bmad-output/implementation-artifacts/deferred-work.md` -- stavka o raspakiranim bajtovima: `zipfile` čita najviše deklariranu veličinu i zatim baca `BadZipFile` (provjereno), pa je pretvaranje u `OSTECENA` dovoljno

## Tasks & Acceptance

**Execution:**
- [x] `provjera/jezgra/tipovi.py` -- `Duljina`, `DuljinaMm` (premješteno iz `profil.py`) -- dijeljeni tipovi mjera
- [x] `provjera/jezgra/model/uloge.py` -- `Uloga` (`NASLOVNICA`, `TIJELO`), `uloge_sekcija(broj) -> tuple[Uloga, ...]` -- AD-13
- [x] `provjera/jezgra/model/__init__.py` -- `TipPocetka` (`SLJEDECA_STRANICA`, `NEPREKINUTO`, `PARNA`, `NEPARNA`, `NOVI_STUPAC`), `Sekcija(indeks, uloga, gore, dolje, lijevo, desno, gutter, sirina, visina, pejzazno, pocetak)` u twipsima (EMU / 635, cijeli broj; nedostajuća vrijednost → `None`), `DocModel(sekcije, zrcalne_margine)`, `NeispravanDokument`, `procitaj(docx)` (greške otvaranja → `NeispravanDokument`) -- AD-3
- [x] `provjera/jezgra/provjera.py` -- `NeispravanDokument` → `Izvjestaj(odbijeno=OSTECENA)`; ostale greške modela ostaju kao u 1.4 -- AD-12
- [x] `provjera/jezgra/pravila/r_sekcije.py` -- R-SEKCIJE prema matrici; `Lokacija(Dio.DOKUMENT, sekcija=…)`; ključevi `R-SEKCIJE.prolazi`, `R-SEKCIJE.jedna_sekcija`, `R-SEKCIJE.krivi_prijelom` -- FR-17
- [x] `provjera/jezgra/pravila/r_margine.py` -- `Postavke(sirina_stranice="21 cm", visina_stranice="29,7 cm")` (`Duljina`). Po sekciji jedan nalaz: `PROSLO`, ili `NE_PROLAZI` s `parametri` = `sekcija`, `<strana>_pronadeno`, `<strana>_ocekivano` (kao `Vrijednost` u twipsima) i `tolerancija`. Naslovnica se uspoređuje s `formula.naslovnica` sa svih strana, a tijelo s `formula.margine`. Dodatni nalazi: `R-MARGINE.nije_a4` (tolerancija `tolerancije.stranica`), `R-MARGINE.pejzazno`, `R-MARGINE.gutter` (po sekciji) i `R-MARGINE.zrcalne` (dokument). Vrijednost `None` u sekciji → `NEPROVJERLJIVO` (`R-MARGINE.nedostaje`) -- FR-18
- [x] `provjera/jezgra/pravila/__init__.py`, `profili/vjezba_1.toml`, `provjera/jezgra/poruke.py` -- registracija redom R-NAZIV, R-SEKCIJE, R-MARGINE; profilu dodati `[tolerancije] stranica = "0,1 cm"` i odjeljke pravila; poruke s uputama Izgled (Layout) → … i `pravilo.<ID>` -- AD-11
- [x] `tests/alati/generator.py` -- `ispravan(rbr, profil) -> bytes` (python-docx) i `VARIJANTE: dict[str, Callable[[int, Profil], bytes]]` (`jedna_sekcija`, `neprekinuti_prijelom`, `krive_margine_tijela`, `krive_margine_naslovnice`, `unutar_tolerancije`, `letter`, `pejzazno`, `gutter`, `zrcalne`); `python -m tests.alati.generator` zapisuje `.docx` u `tests/referentni/vjezba_1/` -- referentni skup
- [x] `tests/referentni/vjezba_1/ocekivano.toml` + generirani `.docx` -- `rbr = 54`, `naziv = "Ana_Horvat_GiG_OG_Vjezba_1.docx"`, `[primjeri.<ime>] padaju = [...]` -- referentni skup
- [x] `tests/test_model.py`, `tests/test_r_sekcije_margine.py`, `tests/test_referentni.py` -- model (EMU → twipsi, uloge, `NeispravanDokument`); redci matrice; svaki primjer iz `ocekivano.toml` pada točno na svom skupu (skup pravila sa statusom ≠ `PROSLO`), a svaki `.docx` u mapi ima zapis; test uzorka sa `skip`; pokrivenost poruka novih pravila -- testovi

**Acceptance Criteria:**
- Given `uv run pytest`, when se pokrene, then svi testovi prolaze, uključujući testove arhitekture (python-docx samo u `jezgra/model/`; test AD-1 i dalje zelen)
- Given generirani referentni skup, when se ponovno pokrene generator, then `ocekivano.toml` i dalje odgovara svim primjerima

## Implementation Notes

- Implementirano izravno u glavnoj sesiji; 250 testova prolazi.
- Kružni uvoz `profil` → `pravila` → `r_margine` → `formula` → `profil` riješen je tako da su `ParametriFormule`, `NAJVISE_KOMBINACIJA` i `kanonski_json` premješteni u `formula.py`. `profil` ih uvozi odande, a otisak formule ostao je isti (`888f585e36ac`).
- Generator se pokreće s `uv run python tests/alati/generator.py`, ne kao modul, jer `tests/` nije paket. Pytest ga uvozi kao `alati` (`pythonpath = ["tests"]`). Testove ispravnog rada u `test_provjera.py` i `test_student_app.py` sada hrani `generator.ispravan` (python-docxov prazan dokument je Letter s jednom sekcijom).
- Rubni slučajevi pokriveni su u `test_model.py` i `test_referentni.py`, umjesto u zasebnom `test_r_sekcije_margine.py` iz Tasks.
- Odgođeni rad iz priče 1.3 (stvarno raspakirani bajtovi) je riješen: `zipfile` čita najviše deklariranu veličinu pa baca `BadZipFile` (provjereno skriptom), a model to pretvara u `odbijeno = OSTECENA`.
- Stvarni uzorak (`samples/…Šimek…`) daje R-SEKCIJE `ne prolazi` (jedna sekcija), ali i R-MARGINE `ne prolazi`, jer margine nisu one za Rbr. 54 i stranica nije A4.
- Nakon pregleda:
  - `NeispravanDokument` nastaje samo kad se paket ne može otvoriti; greške pri čitanju postavki čine pravila neprovjerljivima;
  - pejzaž se određuje po dimenzijama;
  - uveden je zaseban ključ za veličinu stranice koja nedostaje i za dokument bez sekcija;
  - preciznija poruka za krivi tip prijeloma;
  - usporedba veličine stranice ne ovisi o redoslijedu dimenzija u profilu;
  - registracija pravila zaštićena je od preslagivanja uvoza.

## Spec Change Log

## Review Triage Log

| # | Izvor | Nalaz | Presuda | Dokaz / odluka |
|---|-------|-------|---------|----------------|
| 1 | blind, verification | referentni `.docx` nedostaju u diffu | false | namjerno izostavljeni iz tekstualnog diffa; commitaju se s pričom |
| 2 | blind, edge | parni/neparni prijelom dobiva netočnu poruku „ne počinje na novoj stranici“ | low | patch: poruka govori o tipu prijeloma; FR-17 i dalje traži „Sljedeća stranica“ |
| 3 | blind, edge | `procitaj` svaku grešku pretvara u `OSTECENA` | medium | patch: samo otvaranje paketa; test s greškom u `_sekcija` |
| 4 | blind | isort može preslagati registraciju pravila | low | patch: zasebni redci uz `isort: off` |
| 5 | blind, edge | veličina stranice iz profila uspoređuje se ovisno o redoslijedu dimenzija | low | patch: obje strane sortirane |
| 6 | blind | `Tolerancije.stranica` je obavezna bez migracije | low | odbijeno: postoji samo jedan profil i ažuriran je |
| 7 | blind | gutter bez tolerancije; `gutterAtTop`/`bookFold` se ne čitaju | low | odbijeno: rijetko u studentskim radovima |
| 8 | blind, edge | dva jednaka nalaza `nedostaje` u sekciji | low | patch: zaseban ključ `nedostaje_stranica` |
| 9 | blind | „margine su ispravne“ uz nalaz o krivoj stranici | low | odbijeno: margine jesu ispravne, nalazi su odvojeni |
| 10 | blind, edge | dokument bez sekcija dobiva poruku „jedna sekcija“ ili generičku | low | patch: `bez_sekcija` u oba pravila; test |
| 11 | edge | Rbr. izvan formule ruši cijelo pravilo | low | odbijeno: web ograničava Rbr., a batch ga dobiva s provjerenog popisa (3.3) |
| 12 | edge | `orient=landscape` s uspravnim dimenzijama se prijavljuje | low | patch: pejzaž po dimenzijama; test |
| 13 | blind | prednost `ocekivano`/`pronadeno` u `tekst_nalaza` | low | odbijeno: namjerno, vrijednosti nalaza imaju prednost |
| 14 | blind | `kanonski_json` u `formula.py`; neiskorišteni uvozi | low | uvozi očišćeni; smještaj odbijen (izbjegava kružni uvoz) |
| 15 | blind | uvoz `alati` ovisi o načinu uvoza u pytestu | low | patch: `pythonpath = ["tests"]` |
| 16 | edge | nema zasebnog `test_r_sekcije_margine.py`; razlika u pokretanju generatora | low | zapisano u Implementation Notes; pokrivenost je u `test_model.py` |
| 17 | verification | pejzažna A4 ne smije dati i `nije_a4` | medium | patch: test skupa ključeva |
| 18 | verification | pejzaž samo iz dimenzija nije testiran | medium | patch: test |
| 19 | verification | `mirrorMargins` s `val=0/false` nije testiran | medium | patch: parametrizirani test |
| 20 | blind | testovi nedostaju (tik izvan tolerancije, treća sekcija) | low | patch: dodani |

## Design Notes

`w:type` u `sectPr` sekcije N opisuje kako sekcija N počinje. Zato je „naslovnica završava prijelomom Sljedeća stranica“ isto što i `sekcije[1].pocetak == SLJEDECA_STRANICA`; bez elementa vrijedi `nextPage`.

R-MARGINE vraća jedan nalaz po sekciji sa sve četiri margine u `parametri` (kao `Vrijednost`, formatira ih `tekst_nalaza`), jer FR-18 traži sve četiri margine u nalazu. `ocekivano`/`pronadeno` tog nalaza su `None`. Ovo je malo proširenje AD-5 (`parametri` smije sadržavati `Vrijednost`).

## Verification

**Commands:**
- `uv run pytest -q` -- expected: svi testovi prolaze
- `uv run python tests/alati/generator.py` -- expected: zapisuje `.docx` primjere bez greške

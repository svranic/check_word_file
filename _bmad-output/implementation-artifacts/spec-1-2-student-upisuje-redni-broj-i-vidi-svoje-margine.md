---
title: 'Student upisuje redni broj i vidi svoje margine'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: '940cccbdc025f0170693b578b6db713b180b0baa'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Student još ne može saznati svoje individualne margine, a jezgra nema profil zadatka, jedinice ni formulu margina na koje se oslanjaju sve kasnije priče.

**Approach:** Dodati u jezgru `jedinice`, `profil` (TOML + pydantic), `formula` i `rbr`, te `profili/vjezba_1.toml`. Na studentskoj stranici student bira objavljenu vježbu, upisuje Rbr. i vidi četiri margine i obrazac naziva datoteke.

## Boundaries & Constraints

**Always:** sve duljine u jezgri su cijeli brojevi (twipsi; formula u mm); pretvorbe samo u `jedinice.py`, bez usporedbe floatova (`Decimal` pri parsiranju). Formula ovisi samo o Rbr. i `[formula]` profila. Prikaz vrijednosti samo kroz `poruke.formatiraj`; sav tekst iz kataloga. `GreskaProfila` nosi sve greške odjednom, nikad djelomičan `Profil`. U `session_state` samo Rbr., vježba i UI zastavice.

**Never:** nema imena studenta ni popisa; nema `st.cache_*`; nema učitavanja dokumenta, registra pravila ni `[pravila.*]` odjeljka (priča 1.4 ga uvodi; do tada je nepoznat odjeljak greška); jezgra ne čita datoteke (profile čita `apps/student.py`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Ispravan unos | „54“, „54.“, „ 054“ | Rbr. 54: četiri margine („3,2 cm“), uputa Izgled (Layout) → Margine (Margins) → Prilagođene margine (Custom Margins), obrazac `Ime_Prezime_GiG_OG_Vjezba_1.docx`; nema imena | N/A |
| Neispravan unos | „“, „0“, „-3“, „5,5“, „5.5“, „abc“ | `GreskaUnosa`; poruka o ispravnom obliku (pozitivan cijeli broj) | bez traceback-a |
| Rbr. izvan formule | Rbr. > `formula.najveci_rbr` | poruka da Rbr. ne postoji | bez traceback-a |
| Neispravan profil | nepoznat ključ, „3 inch“, korak 0, tolerancija ≥ pola koraka | `GreskaProfila` s popisom svih grešaka; web: samo „provjera trenutno nije dostupna“ | bez detalja na webu |
| Promjena Rbr./vježbe | `session_state` ima `izvjestaj`/`datoteka` | ključevi obrisani | N/A |
| Neobjavljen profil | `objavljeno = false` | ne nudi se na webu | N/A |

</frozen-after-approval>

## Code Map

- `provjera/jezgra/poruke.py` -- `KATALOG`, `poruka()`: proširiti ključevima i dodati `formatiraj`
- `apps/student.py` -- postojeća prazna stranica (naslov, `privatnost.obrada`); nadograditi
- `tests/test_arhitektura.py` -- AD-1 skener (zabranjen `time`, `.now()`…), test grafa uvoza, `AppTest` primjer; mora ostati zelen
- `epic-1-context.md` -- osnovice 3/2,5/2,5/2,5 cm (lijevo/desno/gore/dolje), naslovnica 2,5 cm, tolerancija 0,03 cm

## Tasks & Acceptance

**Execution:**
- [x] `provjera/jezgra/jedinice.py` -- `Jedinica` enum (`TWIPS`, `POLUTOCKE`, `TEKST`, `BOOL`); `parsiraj_duljinu(str) -> twips` i `parsiraj_mm(str) -> mm` (prihvaća „3 cm“, „2,5 cm“, „0.5 cm“, „25 mm“, „12 pt“; mm mora biti cijeli broj), `parsiraj_velicinu_fonta(str) -> polutocke`, `mm_u_twips`, `unutar_tolerancije(a, b, tol)`; neispravno → `ValueError` -- AD-6
- [x] `provjera/jezgra/profil.py` -- pydantic (`extra="forbid"`, frozen) `Profil` s `vjezba` (`id`, `naziv`, `objavljeno`), `naziv_datoteke` (`sufiks`, `nastavak`; `obrazac` = `Ime_Prezime` + sufiks + nastavak), `formula` (`osnovica_lijevo/desno/gore/dolje`, `raspon`, `korak`, `naslovnica` u mm; `sjeme: int ≥ 0`), `tolerancije` (`margine` u twipsima); validacija: korak > 0, raspon višekratnik koraka, osnovica − raspon > 0, tolerancija < pola koraka; `ucitaj(bytes) -> Profil` (TOML i pydantic greške → `GreskaProfila(greske: tuple[str, ...])` s putanjom ključa); `verzija(profil)` = SHA-256 kanonskog JSON-a (`sort_keys`, `separators=(",", ":")`), prvih 8 hex -- AD-7, AD-8
- [x] `provjera/jezgra/formula.py` -- `FORMULA_VERZIJA = 1`; `Margine` (frozen: `gore`, `dolje`, `lijevo`, `desno` u mm; `u_twips()`); algoritam iz Design Notes; `margine(rbr, parametri)`, `najveci_rbr(parametri)`, `otisak(parametri)` (SHA-256 kanonskog JSON-a parametara + `FORMULA_VERZIJA`, 12 hex); Rbr. < 1 ili > najveći → `ValueError` -- FR-4, AD-7
- [x] `provjera/jezgra/rbr.py` -- `GreskaUnosa` (frozen, `poruka_kljuc`); `parsiraj(unos) -> int | GreskaUnosa` -- FR-9
- [x] `provjera/jezgra/poruke.py` -- `formatiraj(iznos, jedinica)`: twipsi → cm s decimalnim zarezom (zaokruženo na 0,01, bez završnih nula: „3,2 cm“, „3,17 cm“), polutočke → „12 pt“; ključevi `profil.nedostupno`, `rbr.*`, `margine.*` (oznake, uputa), `naziv.obrazac`, `vjezba.odabir` -- AD-11
- [x] `profili/vjezba_1.toml` -- `objavljeno = true`, sufiks `_GiG_OG_Vjezba_1`, nastavak `.docx`, osnovice 3/2,5/2,5/2,5 cm, raspon 0,5 cm, korak 0,1 cm, naslovnica 2,5 cm, `sjeme = 20261012`, tolerancija 0,03 cm -- profil Vježbe 1
- [x] `apps/student.py` -- čita `profili/*.toml` uz datoteku (`Path(__file__).parents[1]`), nudi objavljene po `naziv`; neispravan profil → `profil.nedostupno`; `st.text_input` za Rbr.; prikaz margina redom Gore, Dolje, Lijevo, Desno + uputa + obrazac; `on_change` briše `izvjestaj` i `datoteka` iz `session_state` -- FR-9
- [x] `tests/test_jedinice.py`, `tests/test_profil.py`, `tests/test_formula.py`, `tests/test_rbr.py`, `tests/test_student_app.py` -- redci matrice; profil: verzija stabilna pri promjeni redoslijeda ključeva i komentara, sve greške odjednom; formula: Rbr. 1–500 jedinstveni, unutar ±raspon u koraku, ≥ 2 pomaknute, ≠ naslovnica, drugo sjeme → drukčiji raspored, `otisak` se mijenja s `FORMULA_VERZIJA`; snapshot `tests/snapshot/formula_vjezba_1.json` (`formula_verzija` + margine 1–500; test pada ako se `FORMULA_VERZIJA` ne slaže); student app (`AppTest`): unos „54.“ prikazuje četiri margine i obrazac, neispravan unos poruku, promjena Rbr. briše ključeve -- testovi

**Acceptance Criteria:**
- Given `profili/vjezba_1.toml`, when `profil.ucitaj`, then dobiva se `Profil` s mjerama u twipsima i mm, a `formula.margine(54, profil.formula)` daje iste vrijednosti kao snapshot
- Given `uv run pytest`, when se pokrene, then svi testovi, uključujući testove arhitekture, prolaze

## Implementation Notes

- Implementirano izravno u glavnoj sesiji. Profil Vježbe 1: verzija `c6be32cc`, otisak formule `888f585e36ac`, `najveci_rbr` = 14 600; Rbr. 54 → 2,4 / 2,9 / 2,6 / 2,7 cm (gore/dolje/lijevo/desno).
- Snapshot `tests/snapshot/formula_vjezba_1.json` sadrži i otisak. Regeneracija je kratka skripta preko `formula.margine` za Rbr. 1–500, potrebna samo uz novu `FORMULA_VERZIJA`.
- Rbr. se potvrđuje kroz `st.form`, jer bi prazan unos inače javljao grešku već pri otvaranju stranice.
- Tolerancija se uspoređuje u zaokruženim twipsima: „0,05 cm“ = 28 twipsa < pola koraka (28,35), pa je dopuštena.
- Nakon pregleda dodano: Rbr. najviše 9 znamenki (Python odbija `int()` dulji od 4300 znamenki), gornja granica 21⁴ kombinacija u profilu, čitanje TOML-a s BOM-om, duplikat `vjezba.id` broji se kao neispravan, zasebna poruka za djelomično nedostupne vježbe (`profil.djelomicno_nedostupno`), „da“/„ne“ i placeholder iz kataloga.

## Spec Change Log

## Review Triage Log

| # | Izvor | Nalaz | Presuda | Dokaz / odluka |
|---|-------|-------|---------|----------------|
| 1 | edge | Rbr. dulji od 4300 znamenki ruši `int()` u callbacku | medium | patch: regex dopušta najviše 9 znamenki; test s 5000 znamenki |
| 2 | edge, blind | velik raspon/korak blokira `_dopustene` (v⁴ iteracija) | medium | patch: `NAJVISE_KOMBINACIJA = 21⁴` u validaciji profila; test |
| 3 | edge, blind | duplikat `vjezba.id` tiho skriva vježbu | low | patch: `objavljeni` broji duplikat kao neispravan; test |
| 4 | edge, blind, verification | uz djelomično neispravne profile prikazuje se „provjera nije dostupna“, a stranica radi; slučaj nije testiran | medium | patch: zasebna poruka `profil.djelomicno_nedostupno`, `nedostupno` samo bez ijednog profila; `AppTest` za oba slučaja |
| 5 | edge | `OSError` pri čitanju `.toml` | low | odbijeno: profili su u repozitoriju i čitaju se samo za čitanje |
| 6 | edge | TOML s BOM-om odbačen | low | patch: dekodiranje `utf-8-sig` (izravna korekcija); test |
| 7 | edge | zastarjela vrijednost `vjezba` u sesiji | low | odbijeno: profili se mijenjaju samo deployem, koji resetira sesije |
| 8 | blind | greške profila se ne logiraju | low | odbijeno: nastavnik ih vidi u pregledu spremnosti (priča 3.3) |
| 9 | blind | abecedni poredak vježbi (1, 10, 2) | low | odbijeno: v1 ima jednu vježbu |
| 10 | blind | placeholder „54“ i „da“/„ne“ izvan kataloga | low | patch: ključevi `rbr.primjer`, `vrijednost.da/ne` |
| 11 | blind | nema generatora snapshota | low | odbijeno: rijetko (samo nova `FORMULA_VERZIJA`); postupak zapisan u Implementation Notes |
| 12 | blind | nedostaju negativni testovi jedinica, `False`, puni tekst `rbr.prevelik` | low | patch: dodani testovi |
| 13 | blind | `verzija` i `otisak` nisu prikazani; različite duljine | false | duljine (8 i 12) propisuje AD-7; prikaz verzije pripada pričama 1.4 i 1.6 |
| 14 | verification | natpis margina naslovnice nije provjeren | medium | patch: test čita `at.caption` za `margine.naslovnica` i `margine.usporedi` |
| 15 | verification | pravila osnovica > raspon i naslovnica > 0 nisu testirana | medium | patch: dva nova slučaja u parametrizaciji |

## Design Notes

Formula (iz addenduma PRD-a): `v = 2·raspon/korak + 1` vrijednosti po margini (11), `N = v⁴` (14 641). Indeks `k` u bazi `v` daje četiri znamenke (gore, dolje, lijevo, desno), a pomak je `(znamenka − raspon/korak) · korak` mm. Iz sjemena: `h = sha256(f"{sjeme}")`; `a` = najmanji broj ≥ `int(h[:8], 16) % N` koji je uzajamno prost s `N` (ne 0), a `b = int(h[8:16], 16) % N`. Permutacija je `k_i = (a·i + b) mod N` za `i = 0, 1, …`. Isključuju se kombinacije s manje od dvije pomaknute margine i kombinacija jednaka naslovnici. Rbr. n dobiva n-ti dopušteni `k_i`. Linearni prolaz je dovoljno brz (≤ N koraka). `najveci_rbr` = broj dopuštenih kombinacija.

Duljina iz profila u mm: „3 cm“ → 30, „0,1 cm“ → 1; „0,15 cm“ → greška. Twipsi: `round(Decimal(cm) · 1440 / 2,54)`, uz zaokruživanje na najbliži cijeli broj (`ROUND_HALF_UP`).

## Verification

**Commands:**
- `uv run pytest -q` -- expected: svi testovi prolaze
- `uv run python -c "from pathlib import Path; from provjera.jezgra import profil, formula; p = profil.ucitaj(Path('profili/vjezba_1.toml').read_bytes()); print(profil.verzija(p), formula.otisak(p.formula), formula.margine(54, p.formula))"` -- expected: verzija (8 hex), otisak (12 hex), margine u mm

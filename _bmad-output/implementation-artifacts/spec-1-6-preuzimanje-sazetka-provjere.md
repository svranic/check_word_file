---
title: 'Preuzimanje sažetka provjere'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: 'ce9f08ef40804d134ca3b85f426264a934781075'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Student nakon provjere nema zapis kojim može pokazati da je rad provjerio prije predaje.

**Approach:** Uz prikazan izvještaj stranica nudi gumb „Preuzmi sažetak“. Preuzima se samostalna HTML datoteka izrađena iz `Izvjestaj`-a: Rbr., naziv vježbe, verzija profila, vrijeme provjere i status po pravilu. Sažetak ne sadrži sadržaj rada ni naziv datoteke.

## Boundaries & Constraints

**Always:** HTML gradi čista funkcija u jezgri (`jezgra/sazetak.py`) iz `Izvjestaj`-a, naziva vježbe i vremena koje predaje stranica. Jezgra ne čita sat. Vrijeme je trenutak provjere (zagrebačko vrijeme, `dd.mm.gggg. hh:mm`) i čuva se u `session_state` uz izvještaj. Status pravila računa `status_pravila`, a prikazuje se ikonom i tekstom iz kataloga. Sav umetnuti tekst prolazi `html.escape`. Naziv preuzete datoteke ne sadrži ime studenta.

**Never:** u sažetak ne ulaze `ocekivano`/`pronadeno`, `isjecak`, lokacija ni naziv datoteke; nema vanjskih resursa (CSS/JS/fontovi) u HTML-u; za odbijenu datoteku gumba nema.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Spreman rad | izvještaj sa svim pravilima `PROSLO` | HTML: naslov, Rbr., vježba, verzija profila, vrijeme, „spreman za predaju“, redak po pravilu s „✅ prošlo“ | N/A |
| Nespreman rad | barem jedno pravilo `NE_PROLAZI` ili `NEPROVJERLJIVO` | „nije spreman“; status svakog pravila prema `status_pravila` | N/A |
| Privatnost | nalaz R-NAZIV s pronađenim nazivom „Tajna_Studentica_…“, isječak u lokaciji | ni naziv ni isječak nisu u HTML-u | N/A |
| Posebni znakovi | naziv vježbe s `<`, `&` | escapirano | N/A |
| Odbijena datoteka | `Izvjestaj.odbijeno` postavljen | nema gumba | N/A |
| Preuzimanje | izvještaj prikazan | gumb „Preuzmi sažetak“, `text/html`, naziv `sazetak_provjere_rbr_<rbr>.html` | N/A |

</frozen-after-approval>

## Code Map

- `provjera/jezgra/provjera.py` -- `status_pravila`, `spremnost`
- `provjera/jezgra/pravila/osnova.py` -- `REGISTAR` (redoslijed pravila u sažetku)
- `apps/student.py` -- `ucitaj_dokument` sprema `izvjestaj`, `prikazi_izvjestaj` ga prikazuje; `KLJUCEVI_PROVJERE`
- `provjera/jezgra/poruke.py` -- `status.*`, `pravilo.*`, `izvjestaj.spremno/nije_spremno`

## Tasks & Acceptance

**Execution:**
- [x] `provjera/jezgra/sazetak.py` -- `html_sazetka(izvjestaj, naziv_vjezbe, vrijeme) -> str`: samostalan HTML (`lang="hr"`, `charset=utf-8`, ugrađen CSS), tablica pravilo/status za pravila iz izvještaja redom registra, uz napomenu da sažetak ne sadrži sadržaj rada -- FR-12, AD-10
- [x] `provjera/jezgra/poruke.py` -- ključevi `sazetak.*` (naslov, oznake polja, stupci, napomena, gumb, naziv datoteke) -- AD-11
- [x] `apps/student.py` -- pri obradi zapisati `vrijeme_provjere` (`zoneinfo` „Europe/Zagreb“); `KLJUCEVI_PROVJERE` ga briše; uz neodbijen izvještaj `st.download_button` prema matrici -- FR-12
- [x] `tests/test_sazetak.py` i `tests/test_student_app.py` -- redci matrice; jezgra: sadržaj, escapiranje, privatnost; stranica: gumb postoji s ispravnom oznakom za neodbijen izvještaj, ne postoji za odbijen, a `vrijeme_provjere` se briše pri promjeni Rbr. -- testovi

**Acceptance Criteria:**
- Given `uv run pytest`, when se pokrene, then svi testovi prolaze, uključujući testove arhitekture

## Implementation Notes

- Implementirano izravno u glavnoj sesiji; 263 testa prolaze.
- `AppTest` daje oznaku gumba za preuzimanje, ali ne i sadržaj ni naziv datoteke. Zato se argumenti predani `html_sazetka` hvataju spijunom, a sadržaj se provjerava u testovima jezgre.
- Nakon pregleda:
  - `tzdata==2026.5` je izravna ovisnost (prije je dolazila samo tranzitivno);
  - vrijeme se bilježi tek nakon uspješne provjere i uz njega stoji „po zagrebačkom vremenu“;
  - greška pri izradi sažetka samo skriva gumb;
  - ukupni status sažetka (s ikonom) dolazi iz kataloga;
  - HTML ima viewport i `scope="col"`.

## Spec Change Log

## Review Triage Log

| # | Izvor | Nalaz | Presuda | Dokaz / odluka |
|---|-------|-------|---------|----------------|
| 1 | edge, blind | `tzdata` nije izravna ovisnost; `ZoneInfo` pri učitavanju stranice | medium | patch: `tzdata==2026.5` u `pyproject.toml`, lock osvježen |
| 2 | edge | vrijeme se bilježi i kad provjera ne uspije | low | patch: tek nakon uspjeha |
| 3 | edge | sažetak bez nalaza | low | odbijeno: moguće samo sa svim pravilima isključenima |
| 4 | edge | pravilo izvan registra ispada iz tablice | low | odbijeno: nalaze stvaraju samo registrirana pravila (provjera u pokretaču) |
| 5 | edge, blind | prazno vrijeme ako ključ nedostaje | low | patch: ključ se čita izravno, a postavlja se zajedno s izvještajem |
| 6 | edge, blind | greška sažetka prikazuje „provjera nije uspjela“ | low | patch: zaseban `try`, gumb se skriva; test |
| 7 | blind | ikone u kodu jezgre (AD-11) | low | patch: `sazetak.spremno/nije_spremno` u katalogu |
| 8 | blind | slab test privatnosti (isječak, „cm“) | medium | patch: test s isječkom i stvarnim formatiranim vrijednostima |
| 9 | blind, verification | sadržaj gumba (vježba, vrijeme, naziv datoteke) nije provjeren na stranici | medium | patch: spijun nad `html_sazetka`, provjera naziva datoteke kroz katalog |
| 10 | blind | gumb testiran samo za spreman rad | low | patch: test za nespreman rad |
| 11 | blind | status NEPROVJERLJIVO u sažetku nije testiran | low | patch: test |
| 12 | blind | vrijeme nije provjereno determinističkim testom zone | low | patch: usporedba sa zagrebačkim vremenom (±1 min) |
| 13 | blind | nema oznake vremenske zone | low | patch: „po zagrebačkom vremenu“ |
| 14 | blind | nema viewporta, ispisnih stilova ni `scope` | low | patch: viewport i `scope`; ispisni stilovi odbijeni (zadani ispis je čitljiv) |

## Verification

**Commands:**
- `uv run pytest -q` -- expected: svi testovi prolaze

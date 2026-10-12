---
title: 'Izvještaj o provjeri i pravilo naziva datoteke'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: 'a5ef58d350f5a78b57f02d980b5dcdaed1922c04'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Jezgra nema tipove nalaza, registar pravila ni pokretač, pa student nakon učitavanja ne dobiva izvještaj. Ne provjerava se ni naziv datoteke.

**Approach:** Uvesti tipove iz AD-5, `KontekstProvjere` iz AD-1, registar pravila s postavkama iz profila (AD-4, AD-8), pokretač `provjeri()` s izolacijom iznimki i sažimanjem, te prvo pravilo R-NAZIV s funkcijama `naziv.*`. Studentska stranica nakon učitavanja prikazuje izvještaj redoslijedom iz FR-11.

## Boundaries & Constraints

**Always:** pravilo vraća nesažete nalaze, a za prolaz barem jedan. Pokretač je jedini koji hvata iznimke (→ `NEPROVJERLJIVO` s razlogom) i sažima ponavljanja. `status_pravila` koristi poredak `NEPROVJERLJIVO > NE_PROLAZI > PROSLO`. `spremnost` je istinita samo kad postoji barem jedan nalaz i kad su svi `PROSLO`. Odbijena datoteka daje `Izvjestaj` s `odbijeno` i bez nalaza. Usporedba naziva ne ovisi o NFC/NFD. Status se prikazuje ikonom i tekstom. Sav tekst ide kroz katalog i `formatiraj`. U `session_state` je samo `Izvjestaj`.

**Never:** nema parsiranja sekcija ni pravila R-SEKCIJE/R-MARGINE (priča 1.5); nema `ukupni_status` ni `kljuc_uparivanja` (priče 4.2 i 4.3); pravila se ne pozivaju međusobno; nema logiranja naziva datoteke.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Web, ispravan naziv | `Lucija_Šimek_GiG_OG_Vjezba_1.docx` (NFC i NFD), `ocekivani_naziv=None` | R-NAZIV `PROSLO` | N/A |
| Web, neispravan naziv | razmak, bez `_GiG_OG_Vjezba_1`, jedan dio imena, `.doc`, znamenka u imenu | `NE_PROLAZI`, očekivano = obrazac `Ime_Prezime_GiG_OG_Vjezba_1.docx` | N/A |
| Batch, točan | `ocekivani_naziv` jednak (NFC/NFD), `nacin_uparivanja=TOCAN` | `PROSLO` | N/A |
| Batch, drugi način | isti naziv, `nacin_uparivanja` ≠ `TOCAN`, ili drugi naziv | `NE_PROLAZI` s očekivanim nazivom | N/A |
| Kanonski naziv | „Ana Marija“ + „Horvat-Kovač“; „IVA“ + „Horvat“ | `AnaMarija_HorvatKovač_…`; `Iva_Horvat_…` | N/A |
| Iznimka u pravilu | pravilo baci iznimku ili vrati prazan popis | taj rezultat je `NEPROVJERLJIVO` s razlogom, a ostala pravila se izvode | nikad `PROSLO` |
| Ponavljanja | isto pravilo vrati 3 jednaka nalaza | jedan nalaz s `pojave=3` | N/A |
| Isključeno pravilo | `[pravila.R-NAZIV] ukljuceno = false` | nema nalaza za R-NAZIV | N/A |
| Prikaz | izvještaj s nalazima svih statusa | status spremnosti → ne prolazi → neprovjerljivo → prošlo; ikona i tekst; očekivano/pronađeno; korak ispravka; izvor u proširivom dijelu | N/A |
| Preopterećenje | `provjeri` baci `MemoryError` | poruka „pokušaj ponovno za minutu“; stranica ostaje upotrebljiva | bez traceback-a |

</frozen-after-approval>

## Code Map

- `provjera/jezgra/ulaz.py` -- `provjeri_ulaz`, `RazlogOdbijanja`, `NAJVECA_*_MB`: `provjeri()` ga poziva prvog
- `provjera/jezgra/profil.py` -- `Profil` s `extra="forbid"`, `objavljeni`, `verzija`, `NazivDatoteke.obrazac`: dodati `pravila`
- `provjera/jezgra/model/__init__.py` -- trenutno samo docstring; ovdje ide privremeni `DocModel`
- `apps/student.py` -- `ucitaj_dokument()` sprema `rezultat_ulaza` i prikazuje ga: zamijeniti `Izvjestaj`-om; `KLJUCEVI_PROVJERE`, `VELICINA_PO_RAZLOGU`
- `tests/test_student_app.py` -- testovi učitavanja provjeravaju `rezultat_ulaza` i `ulaz.*` poruke: uskladiti s `izvjestaj`
- `tests/test_profil.py` -- slučaj `[pravila.R-MARGINE]` kao nepoznat odjeljak: promijeniti u nepostojeći ID

## Tasks & Acceptance

**Execution:**
- [x] `provjera/jezgra/nalaz.py` -- `Status` (`PROSLO`, `NE_PROLAZI`, `NEPROVJERLJIVO`), `Dio`, `Lokacija(dio, sekcija=None, odlomak=None, isjecak=None)`, `Vrijednost(iznos, jedinica)`, `VrstaIzvora` + `Izvor(vrsta, stil=None)`, `Nalaz` (polja iz AD-5, `parametri` kao `MappingProxyType`, `pojave=1`), `NacinUparivanja` (`TOCAN`, `PRIBLIZAN`, `PODMAPA`, `JMBAG`), `KontekstProvjere` (točno četiri polja iz AD-1), `Izvjestaj(odbijeno, nalazi, profil_verzija, rbr)`; sve zamrznuto -- AD-1, AD-5
- [x] `provjera/jezgra/pravila/osnova.py` -- `PostavkeBaza` (pydantic, `extra="forbid"`, frozen, `ukljuceno: bool = True`), `Pravilo(id, funkcija, postavke, poruke)`, `REGISTAR` (redoslijed registracije), dekorator `registriraj(id, postavke, poruke)` -- AD-4
- [x] `provjera/jezgra/pravila/__init__.py` -- izvozi `REGISTAR` i uvozi module pravila (`r_naziv`) -- registracija
- [x] `provjera/jezgra/naziv.py` -- `kanonski(ime, prezime, profil)` (dijelovi odvojeni razmakom ili spojnicom spajaju se; dio pisan samo velikim slovima → veliko početno slovo; rezultat NFC), `odgovara_obrascu(naziv, profil)` (NFC; dva dijela samo od slova, uključujući hrvatske znakove, odvojena `_`, pa točno `sufiks + nastavak`) -- AD-7, FR-16
- [x] `provjera/jezgra/pravila/r_naziv.py` -- R-NAZIV prema matrici; `Lokacija(Dio.NAZIV)`, očekivano i pronađeno kao `TEKST`; ključevi `R-NAZIV.prolazi`, `R-NAZIV.ne_odgovara_obrascu`, `R-NAZIV.ne_odgovara_ocekivanom`, `R-NAZIV.nije_tocno_upareno` -- FR-16
- [x] `provjera/jezgra/model/__init__.py` -- privremeni zamrznuti `DocModel` bez polja i `procitaj(docx) -> DocModel`; priča 1.5 ga puni -- AD-3
- [x] `provjera/jezgra/provjera.py` -- `provjeri(docx, profil, kontekst)`: `ulaz.provjeri_ulaz` → odbijeno; inače `model.procitaj`, pa svako uključeno pravilo iz `REGISTAR` redom. Iznimka ili prazan rezultat → nalaz `NEPROVJERLJIVO` s ključem `opce.neprovjerljivo` i parametrom `razlog`. Sažimanje po (`pravilo_id`, `status`, `poruka_kljuc`, `ocekivano`, `pronadeno`, `izvor`) uz prvu lokaciju i zbroj pojava. Plus `status_pravila(nalazi, id) -> Status | None` i `spremnost(izvjestaj) -> bool` -- FR-14, FR-15
- [x] `provjera/jezgra/profil.py` -- `pravila: dict[str, SerializeAsAny[PostavkeBaza]]`. `before` validator: nepoznat ID je greška, svaki odjeljak se validira klasom iz registra, a nedostajući dobiva zadane postavke -- AD-8
- [x] `profili/vjezba_1.toml` -- `[pravila.R-NAZIV] ukljuceno = true` -- profil
- [x] `provjera/jezgra/poruke.py` -- ključevi R-NAZIV, `opce.neprovjerljivo`, `pravilo.<ID>` (naziv pravila), `status.<STATUS>` (ikona + tekst), `izvjestaj.*` (spremno/nije spremno, naslovi grupa, očekivano/pronađeno, pojave, tehnički detalji, preopterećenje); `tekst_nalaza(nalaz)` (umeće `ocekivano`/`pronadeno` formatirane kroz `formatiraj` + `parametri`) i `opis_lokacije(lokacija)` -- AD-11
- [x] `apps/student.py` -- prihvaćena ili odbijena datoteka ide kroz `provjeri()` (kontekst web: `None`/`None`), a rezultat se sprema u `session_state["izvjestaj"]`. Odbijeno → postojeća `ulaz.*` poruka. Inače prikaz prema matrici. `MemoryError` → `izvjestaj.preopterecenje`, druga iznimka → `izvjestaj.greska`; `rezultat_ulaza` se uklanja -- FR-11, NFR-7
- [x] `tests/test_naziv.py`, `tests/test_provjera.py`, `tests/test_poruke.py` i uskladiti `tests/test_student_app.py`, `tests/test_profil.py` -- redci matrice. Pokretač se testira privremenim pravilima registriranim kroz `monkeypatch` na `REGISTAR` (iznimka, prazan rezultat, ponavljanja, neovisnost). Test pokrivenosti: svaki ključ iz `Pravilo.poruke` svakog registriranog pravila postoji u katalogu, a svaki `poruka_kljuc` koji R-NAZIV vrati u testovima nalazi se u `Pravilo.poruke` -- testovi

**Acceptance Criteria:**
- Given `uv run pytest`, when se pokrene, then svi testovi prolaze, uključujući testove arhitekture (jezgra ostaje bez zabranjenih uvoza)

## Implementation Notes

- Implementirano izravno u glavnoj sesiji; 206 testova prolazi.
- Potpis pravila proširen je profilom (vidi Design Notes). Pokretač za pravilo bez odjeljka u profilu (npr. privremeno pravilo u testu) koristi zadane postavke.
- Streamlit početni emoji iz `st.error`/`st.success` pretvara u ikonu, pa poruke spremnosti nemaju emoji u katalogu, nego dobivaju izričit `icon=`. Statusi nalaza ostaju „ikona + tekst“ u katalogu, jer se prikazuju kroz `st.markdown`.
- Nalaz se u Markdownu escapira (`bez_markdowna`), jer nazivi datoteka sadrže `_`, `*`, `$` i slične znakove.
- Nakon pregleda dodano:
  - sažimanje uključuje `parametri`;
  - `MemoryError` se propušta do stranice („pokušaj ponovno za minutu“);
  - neispravan izlaz pravila daje `NEPROVJERLJIVO`;
  - neuspjelo čitanje modela ne ruši pravila koja model ne trebaju;
  - `naziv.kanonski` uzima samo slova (pa uvijek odgovara obrascu) i odbija prazno ime;
  - `KontekstProvjere` traži da se oba batch polja zadaju zajedno;
  - prikaz izvještaja zaštićen je od iznimki.

## Spec Change Log

## Review Triage Log

| # | Izvor | Nalaz | Presuda | Dokaz / odluka |
|---|-------|-------|---------|----------------|
| 1 | blind, edge | ključ sažimanja ne uključuje `parametri`, pa se gube razlozi | medium | patch: `parametri` u ključu; test |
| 2 | blind | ime iznimke (npr. `KeyError`) vidi student | low | odbijeno: FR-11 traži objašnjenje uz neprovjerljivo; poruka upućuje na nastavnika |
| 3 | blind | `MemoryError` u pravilu postaje neprovjerljivo umjesto preopterećenja | medium | patch: propušta se; test |
| 4 | blind | greške se ne logiraju | low | odbijeno: AD-10 ograničava logove; dijagnostika ide kroz samoprovjeru (3.4) |
| 5 | blind, edge | `model.procitaj` izvan obrade grešaka | medium | patch: neuspjeh → `dokument=None`, pravila koja ga trebaju postaju neprovjerljiva; test |
| 6 | blind, edge | `kanonski` zadržava apostrof, točku i znamenke, pa ne odgovara obrascu | medium | patch: dijelovi su samo slova; test „D'Angelo“ |
| 7 | blind, edge | prazno ime daje `_Prezime…` | low | patch: `ValueError` (jedan uvjet); test |
| 8 | blind, edge | `KontekstProvjere` ne provjerava parove polja | low | patch: `__post_init__`; test |
| 9 | blind, edge | sudar `ocekivano`/`pronadeno` u `parametri`; nedostajući placeholder | low | odbijeno izravno; prikaz je sada zaštićen (#11) |
| 10 | blind | poredak grupa u prikazu ≠ poredak ozbiljnosti | false | FR-11 propisuje redoslijed prikaza, AD-5 poredak `status_pravila`; to su dvije namjerne stvari |
| 11 | edge | iznimka pri prikazu izvještaja daje traceback | medium | patch: `try` oko `prikazi_izvjestaj` → `izvjestaj.greska` |
| 12 | blind | izvještaj bez nalaza nema objašnjenja | low | odbijeno: moguće samo uz profil sa svim pravilima isključenima |
| 13 | blind | „…“ uvijek nakon isječka; granica od 60 znakova se ne provjerava | low | odbijeno: isječak dodjeljuje model u priči 1.5 |
| 14 | blind | zastarjeli popis prefiksa u docstringu `poruke.py` | low | patch |
| 15 | blind | `FunkcijaPravila` je netipizirana | low | odbijeno: tipovi bi uveli kružni uvoz; ugovor provjeravaju testovi |
| 16 | edge | izlaz pravila koji nije `Nalaz` ruši `provjeri` | medium | patch: provjera tipa i `pravilo_id` unutar `try`; test |
| 17 | edge | `$` i `:` u nazivu tumače se kao LaTeX/emoji | low | patch: dodani u escapiranje |
| 18 | edge | sufiks iz profila nije NFC | low | patch: `nfc` nad cijelim rezultatom |
| 19 | edge | verzija profila mijenja se kad se doda novo pravilo | false | namjerno: verzija opisuje efektivnu konfiguraciju, a novo pravilo je mijenja |
| 20 | edge | `pojave` ≤ 0 | low | odbijeno: nalaze stvaraju samo pravila i pokretač |
| 21 | verification | escapiranje Markdowna nije testirano | medium | patch: `AppTest` s „moj__rad*1*.docx“ |
| 22 | verification | ponovno učitavanje nakon greške ne briše grešku (netestirano) | medium | patch: `AppTest` greška → uspjeh |

## Design Notes

**Proširenje AD-4:** potpis pravila je `(DocModel, KontekstProvjere, Postavke, Profil) -> list[Nalaz]`. Zajednički odjeljci profila (`[naziv_datoteke]`, `[formula]`, `[tolerancije]`) ne pripadaju postavkama nijednog pravila, a pravila ih trebaju: AD-1 traži `formula.margine(rbr, profil.formula)` u R-MARGINE, a R-NAZIV treba obrazac. Profil je nepromjenjiv i pravila ga samo čitaju.

Izbjegavanje kružnog uvoza: `profil` → `pravila` → `r_naziv` → `naziv`; `naziv` i `r_naziv` uvoze `Profil` samo pod `TYPE_CHECKING`.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: svi testovi prolaze

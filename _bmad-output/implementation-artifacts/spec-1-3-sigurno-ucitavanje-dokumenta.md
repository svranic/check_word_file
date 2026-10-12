---
title: 'Sigurno učitavanje dokumenta'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: 'f6d17f3468342b5f4928e40ebc095a64f0b588c8'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Student još ne može učitati rad. Kad bude mogao, neprihvatljiva ili zlonamjerna datoteka ne smije srušiti aplikaciju ni ostati spremljena.

**Approach:** Jezgra (`ulaz.py`) prije parsiranja provjerava nastavak, potpis, veličinu, raspakiranu veličinu i osnovnu strukturu, a vraća `RazlogOdbijanja` ili `None`. Studentska stranica nakon unosa Rbr. nudi polje za učitavanje i za svaki razlog prikazuje vlastitu poruku iz kataloga. Učitana datoteka postoji samo tijekom jednog izvođenja.

## Boundaries & Constraints

**Always:** ograničenja 10 MB i 100 MB raspakirano su konstante u `ulaz.py`. Nastavak se uspoređuje bez obzira na velika i mala slova. ZIP se ne raspakirava: veličina se čita iz `infolist()`, a čita se samo `[Content_Types].xml` (najviše 1 MB). Nakon obrade polje za učitavanje dobiva novi ključ (`datoteka_<n>`), pa Streamlit odbacuje datoteku. U `session_state` ostaje samo oznaka ishoda (`rezultat_ulaza`).

**Never:** nema zapisivanja na disk ni `st.cache_*`; nema logiranja naziva datoteke ni Rbr. `type=` filter u `st.file_uploader` se ne koristi, jer bi Streamlit tada prikazao vlastitu englesku poruku umjesto naše. Nema provjere pravila (priča 1.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Ispravan dokument | `Rad.DOCX`, valjani .docx | `None`; stranica: „ispravan Word dokument“ | N/A |
| Stari Word | `.doc`, ili OLE datoteka preimenovana u `.docx` | `STARI_DOC`; uputa Spremi kao (Save As) → Word dokument (.docx) | bez traceback-a |
| Makro dokument | `.docm`, ili `.docx` s `macroEnabled` u `[Content_Types].xml` | `MAKRO` + ista uputa | bez traceback-a |
| Drugi format | `.pdf`, `.txt`, PDF preimenovan u `.docx` | `NEISPRAVAN_FORMAT` + ista uputa | bez traceback-a |
| Šifrirana | OLE s `EncryptionInfo`, nastavak `.docx` | `SIFRIRANA`; uputa za uklanjanje lozinke | bez traceback-a |
| Prazna | 0 bajtova | `PRAZNA` | bez traceback-a |
| Prevelika | > 10 MB | `PREVELIKA` | bez traceback-a |
| Zip bomba | raspakirano > 100 MB | `ZIP_BOMBA` | bez traceback-a |
| Oštećena | ZIP potpis bez valjanog ZIP-a ili bez `word/document.xml` | `OSTECENA` | bez traceback-a |
| Nakon obrade | bilo koja datoteka | `session_state` nema bajtova ni `UploadedFile`; logovi bez naziva datoteke | N/A |

</frozen-after-approval>

## Code Map

- `apps/student.py` -- `ocisti_provjeru`, `KLJUCEVI_PROVJERE`, `prikazi_margine`; polje za učitavanje ide nakon margina, samo uz valjan Rbr.
- `provjera/jezgra/poruke.py` -- dodati ključeve `ulaz.*`
- `tests/test_student_app.py` -- `_posalji` helper; testovi brisanja koriste ključeve `izvjestaj` i `datoteka`, koje treba uskladiti s novim ključevima
- `tests/test_arhitektura.py` -- dodati AST provjeru da `apps/student.py` ne koristi `st.cache_data`/`st.cache_resource`

## Tasks & Acceptance

**Execution:**
- [x] `provjera/jezgra/ulaz.py` -- `RazlogOdbijanja` (StrEnum: `prazna`, `neispravan_format`, `stari_doc`, `makro`, `sifrirana`, `prevelika`, `zip_bomba`, `ostecena`), `NAJVECA_VELICINA = 10 MiB`, `NAJVECA_RASPAKIRANA = 100 MiB`, `provjeri_ulaz(naziv, sadrzaj) -> RazlogOdbijanja | None`. Redoslijed: prazna → nastavak → veličina → potpis (OLE: `EncryptionInfo` u UTF-16LE → šifrirana, inače stari doc; bez `PK\x03\x04` → drugi format) → ZIP (`BadZipFile` → oštećena) → raspakirana veličina → `[Content_Types].xml` i `word/document.xml` → `macroEnabled` -- FR-10, AD-12
- [x] `provjera/jezgra/poruke.py` -- `ulaz.oznaka`, `ulaz.prihvaceno` i po jedan ključ `ulaz.<razlog>` za svaki razlog; tekst sadrži „Spremi kao (Save As) → Word dokument (.docx)“ gdje je primjenjivo; veličine kroz parametar `mb` -- AD-11
- [x] `apps/student.py` -- uz valjan Rbr. prikazati `st.file_uploader(..., key=f"datoteka_{n}", max_upload_size=10)`. Kad stigne datoteka: `provjeri_ulaz(naziv, getvalue())`, zatim `rezultat_ulaza` = vrijednost razloga ili `"prihvaceno"`, `n += 1`, `st.rerun()`. Ishod prikazati iz `rezultat_ulaza` (`st.error` / `st.success`). `ocisti_provjeru` briše `izvjestaj` i `rezultat_ulaza` te podiže `n` -- FR-10, AD-10
- [x] `tests/test_ulaz.py` -- svi redci matrice na sintetskim bajtovima: valjan docx iz `python-docx` (`Document().save(BytesIO)`), OLE zaglavlje sa i bez `EncryptionInfo`, PDF zaglavlje, ZIP bez `word/document.xml`, `macroEnabled` content type, zip bomba (101 MiB nula u ZIP-u, `ZIP_DEFLATED`), skraćeni ZIP; svaki razlog ima ključ u katalogu -- testovi jezgre
- [x] `tests/test_student_app.py` -- `AppTest` s `file_uploader().set_value(...)`: ispravan docx → poruka o prihvaćanju; `.doc` → poruka sa „Spremi kao (Save As)“; nakon obrade nijedna vrijednost u `session_state` nije `bytes` ni `UploadedFile`; `caplog` ne sadrži naziv datoteke; promjena Rbr. briše `rezultat_ulaza`. Uskladiti postojeće testove brisanja -- testovi stranice
- [x] `tests/test_arhitektura.py` -- test da `apps/student.py` ne poziva `cache_data` ni `cache_resource` -- AD-10

**Acceptance Criteria:**
- Given `uv run pytest`, when se pokrene, then svi testovi prolaze, uključujući testove arhitekture i studentske stranice iz priče 1.2

## Implementation Notes

- Implementirano izravno u glavnoj sesiji; 153 testa prolaze.
- Polje za učitavanje nakon svake obrade dobiva novi ključ (`polje_ucitavanja`). Mutacijski test potvrdio je da test o bajtovima pada ako se ključ ne promijeni.
- Nakon pregleda: `max_upload_size` je 11 MB (granica jezgre + 1), da bi datoteku od 10 do 11 MB odbila jezgra našom porukom. Za veće datoteke i dalje se prikazuje Streamlitova poruka. Hvataju se i `zlib.error` i `RuntimeError` (šifrirana stavka ZIP-a). Dodana je granica od 10 000 stavki, a `word/vbaProject.bin` se tretira kao makro. Poruka o prihvaćanju sada kaže „prošla je provjeru formata“.

## Spec Change Log

## Review Triage Log

| # | Izvor | Nalaz | Presuda | Dokaz / odluka |
|---|-------|-------|---------|----------------|
| 1 | blind, edge, verification | `zlib.error` / `RuntimeError` iz `arhiva.read` ruše stranicu | high | patch: dodane u `except`; testovi s oštećenim deflateom i šifriranom stavkom (potvrđeni tipovi iznimki) |
| 2 | blind | zaštita od zip bombe vjeruje deklariranim veličinama; nema granice broja stavki | medium | patch: granica od 10 000 stavki. Ograničenje stvarno raspakiranih bajtova odgođeno je u deferred-work (parser u priči 1.5) |
| 3 | blind | poruka `prevelika` nedostižna jer widget odbija na 10 MB | medium | patch: widget 11 MB; test na `proto.max_upload_size_mb` |
| 4 | blind | nastavak se provjerava prije sadržaja (.docx preimenovan u .doc → „stari format“) | low | odbijeno: uputa (Spremi kao → .docx) i dalje rješava problem |
| 5 | blind | `vbaProject.bin` bez `macroEnabled`; .dotx preimenovan | low | patch za `vbaProject.bin` (jedan uvjet); predložak odbijen, pravila ga hvataju kasnije |
| 6 | blind, edge | `EncryptionInfo` kao podniz može dati lažni pozitiv | low | odbijeno: rijetko; parsiranje OLE direktorija traži novu ovisnost |
| 7 | blind | „ispravan Word dokument“ pretjeruje | low | patch: tekst „prošla je provjeru formata“ |
| 8 | blind | nema testa resetiranja polja; drugi spremnici | low | odbijeno: mutacijski test pokazuje da postojeći test hvata reset; drugi spremnici ne postoje |
| 9 | blind | test predmemorije je uzak | low | odbijeno: dovoljan za stvarne obrasce u aplikaciji |
| 10 | blind, verification | nedostaju testovi (prevelik `[Content_Types].xml`, bez njega, velika slova, granice) | low | patch: dodani testovi |
| 11 | edge | nepoznata vrijednost `rezultat_ulaza` daje `ValueError` | low | odbijeno: vrijednost postavlja samo naš kod |
| 12 | edge | test fraze „Spremi kao“ koristi .pdf, a ne .doc | low | patch: dodan test za `.doc` |
| 13 | verification | vrijednost `mb` u porukama `prevelika`/`zip_bomba` nije provjerena na stranici | medium | patch: parametrizirani `AppTest` s 10 i 100 MB |

## Verification

**Commands:**
- `uv run pytest -q` -- expected: svi testovi prolaze

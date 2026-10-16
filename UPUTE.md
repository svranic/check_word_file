# Kratke upute za korištenje

Aplikacija provjerava tehničko oblikovanje Word zadaća (margine, naziv datoteke, stilovi, naslovi, broj stranice, literatura …) prema profilu vježbe iz mape `profili/`.

Sastoji se od dva dijela:

| Aplikacija | Tko je koristi | Gdje radi |
|---|---|---|
| `apps/nastavnik.py` | nastavnik | samo lokalno, na tvom računalu |
| `apps/student.py` | studenti | javno, na Streamlit Community Cloudu |

## Pokretanje

Potreban je [uv](https://docs.astral.sh/uv/). Naredbe se pokreću iz korijena repozitorija:

```bash
uv sync                                   # prvi put: instalacija okoline
uv run streamlit run apps/nastavnik.py    # nastavnička aplikacija
uv run streamlit run apps/student.py      # studentska aplikacija (lokalni test)
```

---

## Nastavnik: tijek jedne vježbe

### 1. Priprema profila

Uredi ili kopiraj `profili/vjezba_1.toml`. Za novu vježbu promijeni `id`, `naziv`, `sufiks` naziva datoteke, `poveznica` i **`sjeme`**: novo sjeme daje nove margine studentima. Dok je `objavljeno = false`, studenti tu vježbu ne vide.

Ako profil ima grešku, aplikacija prikazuje sve greške i ne dopušta nastavak.

**Fiksne margine.** Ako svi studenti trebaju imati iste margine, u odjeljak `[formula]` dodaj `fiksne_margine = true`. Margine sekcija rada nakon naslovnice tada su osnovice iz profila (`osnovica_gore`, `osnovica_dolje`, `osnovica_lijevo`, `osnovica_desno`), a `raspon`, `korak` i `sjeme` nisu potrebni. Student na web provjeri ne upisuje Rbr., nego odmah vidi margine i učitava rad. PDF navodi margine u zajedničkim zahtjevima, a tablica ima samo Rbr., ime, prezime i naziv datoteke. Spremnost ne provjerava jedinstvenost margina, ali popis i dalje treba zamrznuti jer batch po njemu uparuje datoteke.

### 2. Podatkovna mapa

Na vrhu stranice upiši mapu u koju se spremaju podaci (zadano `~/ProvjeraWord`). Mapa **ne smije biti unutar repozitorija**, jer sadrži osobne podatke studenata. Za svaku vježbu nastaje podmapa, npr. `ProvjeraWord/vjezba_1/`.

### 3. Popis studenata iz ISVU-a

1. Na dnu stranice učitaj ISVU izvoz (`.xlsx`).
2. Ako je popis ispravan, klikni **Zamrzni popis**. Time svaki student trajno dobiva svoj **Rbr.**, a o njemu ovise njegove margine. Zamrznuti popis (`popis.csv`) ne uređuj ručno.
3. Kasnije promjene (kasni upisi, ispisi): učitaj novi izvoz, pregledaj razlike i klikni **Primijeni promjene**. Novi studenti dobivaju sljedeći slobodni Rbr., a postojeći zadržavaju svoj.

### 4. Spremnost i samoprovjera

- **Samoprovjera** provjerava profil na referentnim primjerima iz `tests/referentni/`. Pokreni je nakon svake promjene profila.
- **Spremnost** pokazuje je li sve u redu: postoji popis, ima aktivnih studenata, margine su jedinstvene i samoprovjera prolazi.

### 5. PDF sa svojstvima

Kad je spremnost „spremno“, klikni **Generiraj PDF** i zatim **Preuzmi PDF**. PDF sadrži Rbr., ime, prezime, očekivani naziv datoteke i margine svakog studenta, zajedničke zahtjeve i poveznicu na web provjeru. JMBAG-ovi nisu u PDF-u. Objavi ga u e-učenju.

Prije generiranja provjeri poveznicu na web provjeru. Mijenja se u profilu (`[vjezba] poveznica`).

### 6. Batch provjera predaja

1. Preuzmi predane radove iz e-učenja u jednu mapu.
2. U odjeljku **Batch provjera predaja** upiši putanju te mape. Ona ne smije biti unutar podatkovne mape.
3. Klikni **Pokreni batch provjeru**. Ako su se margine u profilu promijenile od izdavanja PDF-a, aplikacija upozorava i traži potvrdu.
4. Rezultat je tablica u aplikaciji i Excel zbirna tablica za bodovanje (`rezultati_<vjezba>.xlsx` u podmapi vježbe).

Batch provjera ništa ne šalje na mrežu i ne mijenja datoteke u mapi predaja.

---

## Student: provjera rada prije predaje

1. Otvori poveznicu iz PDF-a sa svojstvima.
2. Odaberi vježbu.
3. Upiši svoj **Rbr.** iz PDF-a i klikni **Prikaži moje margine**. Prikazat će se tvoje margine (gore, dolje, lijevo, desno) i obrazac naziva datoteke.
4. Učitaj svoj `.docx`.
5. Pročitaj izvještaj:
   - ✅ „Rad je spreman za predaju.“ ili ❌ „Rad nije spreman za predaju.“
   - nalazi su grupirani na: *Ne prolazi*, *Neprovjerljivo*, *Prošlo*
   - uz svaku grešku piše očekivana i pronađena vrijednost te mjesto u dokumentu
6. Ispravi greške u Wordu i ponovno učitaj datoteku dok sve ne prođe.
7. Po želji preuzmi HTML sažetak provjere.

Datoteka se obrađuje samo u memoriji i ne sprema se.

---

## Napomene

- Prije svakog pusha pokreni `uv run pytest`.
- Stvarni podaci (ISVU izvozi, radovi, mapa `samples/`) nikad ne idu u repozitorij.
- Javna aplikacija na Cloudu uspava se nakon 12 sati bez prometa, pa je otvori na dan roka predaje.
- Detalji o deployu nalaze se u [README.md](README.md).

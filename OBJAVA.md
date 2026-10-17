# Objava studentske aplikacije na Streamlit Community Cloudu

Na Cloud ide samo studentska aplikacija (`apps/student.py`). Nastavnička aplikacija (`apps/nastavnik.py`) uvijek radi lokalno, jer radi s osobnim podacima studenata.

Kako to radi: Streamlit Community Cloud čita kod izravno s GitHuba. Ovisnosti instalira iz `uv.lock`, a aplikaciju pokreće iz korijena repozitorija, pa učitava i `.streamlit/config.toml`. Svaki push na granu `main` automatski osvježava aplikaciju. Ručni „redeploy“ nije potreban.

---

## Korak 1: Priprema (lokalno)

1. Provjeri profil vježbe `profili/vjezba_1.toml`:
   - `objavljeno = true`, inače studenti vježbu neće vidjeti;
   - `fiksne_margine` ima željenu vrijednost (`true` = iste margine za sve, bez unosa Rbr.);
   - osnovice margina, `naslovnica`, `sufiks` naziva datoteke i vrijednosti pravila odgovaraju uputama za vježbu.
2. Ako si mijenjao profil, ponovno generiraj referentni skup:
   ```bash
   uv run python tests/alati/generator.py
   ```
3. Pokreni testove. Svi moraju proći:
   ```bash
   uv run pytest
   ```
4. Isprobaj aplikaciju lokalno:
   ```bash
   uv run streamlit run apps/student.py
   ```
   Otvori `http://localhost:8501`, odaberi vježbu i učitaj ispravan rad. Mora pisati „Rad je spreman za predaju.“
5. Provjeri da u commitu nema osobnih podataka:
   ```bash
   git status
   git ls-files | grep -Ei "\.(xlsx|csv|docx)$" | grep -v "^tests/"
   ```
   Druga naredba ne smije ništa ispisati. To provjerava i test `tests/test_arhitektura.py`.

## Korak 2: GitHub repozitorij (samo prvi put)

1. Na [github.com/new](https://github.com/new) napravi novi repozitorij, npr. `provjera-word`.
   - **Javan ili privatan:** oboje radi. Privatan je bolji jer se ne vidi kod ni profil. Aplikaciju svejedno treba ručno učiniti javnom (korak 5).
   - Ne dodaj README, `.gitignore` ni licencu, jer ih repozitorij već ima.
2. Poveži lokalni repozitorij i pošalji kod:
   ```bash
   git remote add origin https://github.com/<korisnik>/provjera-word.git
   git push -u origin main
   ```
3. Na GitHubu provjeri sadržaj repozitorija:
   - postoje `apps/`, `provjera/`, `profili/`, `tests/`, `.streamlit/config.toml`, `pyproject.toml` i `uv.lock`;
   - **ne postoje** `samples/`, `_bmad-output/`, `.claude/` ni ikakvi stvarni radovi ili ISVU izvozi.

## Korak 3: Streamlit račun (samo prvi put)

1. Otvori [share.streamlit.io](https://share.streamlit.io) i prijavi se **GitHub računom** (*Continue with GitHub*).
2. Dopusti Streamlitu pristup repozitorijima. Za privatan repozitorij potreban je pristup privatnim repozitorijima: Streamlit to traži pri prvom deployu ili u *Settings → Linked accounts → GitHub*.

## Korak 4: Prvi deploy

1. U radnom prostoru (*workspace*) klikni **Create app** u gornjem desnom kutu.
2. Na pitanje imaš li već aplikaciju odaberi **Yup, I have an app**.
3. Ispuni polja:
   | Polje | Vrijednost |
   |---|---|
   | Repository | `<korisnik>/provjera-word` |
   | Branch | `main` |
   | Main file path | `apps/student.py` |
   | App URL | npr. `provjera-word`. Adresa je tada `https://provjera-word.streamlit.app` |
4. Klikni **Advanced settings**:
   - **Python version: 3.12.** Projekt traži točno 3.12 (`requires-python = ">=3.12,<3.13"`). Verzija se kasnije ne može promijeniti bez brisanja i ponovnog deploya.
   - **Secrets:** ostavi prazno, aplikacija nema tajni.
   - Klikni **Save**.
5. Klikni **Deploy**.
6. Prati log na desnoj strani:
   - Cloud pronalazi `uv.lock` u korijenu repozitorija i instalira ovisnosti iz njega, uključujući paket `provjera`. Prvi deploy traje nekoliko minuta.
   - Na kraju se aplikacija prikaže lijevo od loga.
   - Ako instalacija padne, pročitaj grešku u logu. Najčešći uzrok je pogrešna verzija Pythona: obriši aplikaciju i deployaj je ponovno s 3.12.
7. Kao zamjenu, ako Cloud iz nekog razloga ne prihvati `uv.lock`, napravi `requirements.txt`:
   ```bash
   uv export --no-dev --no-hashes -o requirements.txt
   ```
   Zatim obriši `uv.lock` iz repozitorija, jer `uv.lock` ima prednost pred `requirements.txt`, pa commitaj i pushaj.

## Korak 5: Učini aplikaciju javnom

Aplikacija nasljeđuje vidljivost repozitorija: **privatan repozitorij daje privatnu aplikaciju**, koju studenti ne mogu otvoriti bez pozivnice. Besplatni plan dopušta samo jednu privatnu aplikaciju.

1. U aplikaciji klikni **Share** u gornjem desnom kutu.
2. Klikni **Make this app public**.
   - Isto možeš u *App settings → Sharing → Who can view this app → This app is public and searchable*.
3. Provjeri: otvori adresu u **privatnom prozoru** preglednika, bez prijave. Stranica se mora otvoriti.

## Korak 6: Provjera javne aplikacije

U privatnom prozoru:

1. Vidi se naslov i poruka o privatnosti (obrada u SAD-u, ništa se ne sprema).
2. Odaberi vježbu. Uz fiksne margine odmah se vide margine i polje za učitavanje. Uz individualne margine traži se Rbr.
3. Učitaj `tests/referentni/vjezba_1/ispravan.docx` preimenovan prema obrascu, npr. `Ana_Anić_GiG_OG_Vjezba_1.docx`. Rezultat mora biti „Rad je spreman za predaju.“
4. Učitaj `tests/referentni/vjezba_1/krive_margine_tijela.docx`. Rezultat mora biti „Rad nije spreman za predaju.“, uz nalaz o marginama.
5. Preuzmi HTML sažetak i otvori ga.

## Korak 7: Poveznica u PDF-u za studente

1. Usporedi stvarnu adresu aplikacije s `poveznica` u odjeljku `[vjezba]` profila. Trenutno je to `https://provjera-word.streamlit.app/`.
2. Ako se razlikuju, ispravi `poveznica`, pa:
   ```bash
   uv run pytest
   git commit -am "chore: poveznica na web provjeru"
   git push
   ```
   Cloud za minutu sam preuzima promjenu.
3. Pokreni nastavničku aplikaciju (`uv run streamlit run apps/nastavnik.py`):
   - pokreni **Samoprovjeru**;
   - provjeri da spremnost pokazuje „spremno“;
   - klikni **Generiraj PDF** i provjeri da PDF sadrži ispravnu poveznicu.
4. Objavi PDF i upute u e-učenju.

## Korak 8: Održavanje tijekom vježbe

- **Spavanje:** aplikacija se uspava nakon 12 sati bez prometa. Prvi student tada vidi gumb za buđenje i čeka oko minutu. Otvori je sam dan prije i na dan roka.
- **Promjena profila ili koda** uvijek ide istim redom: `uv run pytest`, zatim commit, zatim `git push`. Cloud se osvježava sam.
  - Ako promjena mijenja margine, ponovno generiraj PDF i objavi ga. Nastavnička aplikacija na to upozorava.
- **Log i ponovno pokretanje:** u radnom prostoru na share.streamlit.io otvori izbornik **⋮** pored aplikacije. Ondje su *Logs*, *Reboot app* (ako aplikacija zapne), *Settings* i *Delete*.
- **Batch provjera** predanih radova radi lokalno u nastavničkoj aplikaciji, nikad na Cloudu.

## Brzi pregled

- [ ] `uv run pytest` prolazi, a `git status` je bez osobnih podataka
- [ ] profil: `objavljeno = true`, ispravne margine i naziv datoteke
- [ ] `git push` na `main`
- [ ] Create app: repozitorij, `main`, `apps/student.py`, App URL, **Python 3.12**
- [ ] deploy prošao (log bez greške)
- [ ] aplikacija **javna** i radi u privatnom prozoru
- [ ] ispravan rad prolazi, pokvareni ne prolazi
- [ ] `poveznica` u profilu jednaka stvarnoj adresi
- [ ] samoprovjera „spremno“, PDF generiran i objavljen

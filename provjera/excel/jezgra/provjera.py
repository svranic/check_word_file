"""Provjera predane Excel vježbe: formule, vrijednosti i općenitost formula.

Za svaki rezultat obrasca provjeravaju se tri stvari:

1. **formula** – u ćeliji je formula, a ne upisan broj;
2. **vrijednost** – rezultat (koji je Excel spremio) odgovara referentnom izračunu iz
   ulaznih podataka u istoj datoteci;
3. **općenitost** – formule studenta izvode se i na nekoliko drugih skupova ulaznih
   podataka (``zadaci.kontrolni_podaci``); rezultat mora i tada biti točan. Time se
   otkrivaju prepisani brojevi, reference na pogrešne ćelije i formule koje su
   „slučajno“ točne samo za vlastite podatke.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from provjera.excel.jezgra import dodjela, formule, xlsx
from provjera.excel.jezgra.formule import ExcelGreska, Nepodrzano, Racunalo
from provjera.excel.jezgra.profil import ProfilExcel
from provjera.excel.jezgra.zadaci import (
    ZADACI,
    Rezultat,
    Vrsta,
    Zadatak,
    dms_u_stupnjeve,
    kontrolni_podaci,
    osobni_podaci,
)
from provjera.zajednicko import naziv, ulaz
from provjera.zajednicko.status import Status
from provjera.zajednicko.ulaz import RazlogOdbijanja

# Prilagođena svojstva koja predložak upisuje u datoteku.
SVOJSTVO_JMBAG = "provjera_jmbag"
SVOJSTVO_STUDENT = "provjera_student"
SVOJSTVO_VJEZBA = "provjera_vjezba"
SVOJSTVO_ZADATAK = "provjera_zadatak"  # dodijeljeni zadaci, odvojeni zarezom
# Zaglavlje svakog lista osobnog predloška (zaključano): ime i prezime te JMBAG studenta.
ADRESA_STUDENTA, ADRESA_JMBAG = "D3", "D4"

# Brojevi koji se smiju pojaviti u formuli (pretvorbe kutova, polovine…).
_UOBICAJENI = {0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 10.0, 60.0, 90.0, 100.0, 180.0, 360.0, 3600.0}
_TOL_ULAZA = 1e-6


@dataclass(frozen=True)
class Stavka:
    zadatak: str  # id zadatka; "" za provjere cijele datoteke
    kljuc: str
    opis: str
    adresa: str
    formula: Status
    vrijednost: Status
    opcenito: Status
    poruke: tuple[str, ...] = ()

    @property
    def status(self) -> Status:
        statusi = (self.formula, self.vrijednost, self.opcenito)
        if Status.NE_PROLAZI in statusi:
            return Status.NE_PROLAZI
        if Status.NEPROVJERLJIVO in statusi:
            return Status.NEPROVJERLJIVO
        return Status.PROSLO


@dataclass(frozen=True)
class IzvjestajExcel:
    naziv_datoteke: str
    odbijeno: RazlogOdbijanja | None
    stavke: tuple[Stavka, ...] = ()
    jmbag_iz_datoteke: str | None = None
    svojstva: xlsx.Svojstva | None = None
    # „list!adresa=formula“ svih formula; za usporedbu sličnosti predaja.
    otisak: frozenset[str] = field(default_factory=frozenset)

    @property
    def status(self) -> Status:
        if self.odbijeno is not None:
            return Status.NE_PROLAZI
        statusi = {s.status for s in self.stavke}
        if Status.NE_PROLAZI in statusi:
            return Status.NE_PROLAZI
        if Status.NEPROVJERLJIVO in statusi:
            return Status.NEPROVJERLJIVO
        return Status.PROSLO

    def broj(self, status: Status) -> int:
        return sum(1 for s in self.stavke if s.status is status)


# --- Oblikovanje ---------------------------------------------------------------


def broj_hr(x: float, decimale: int) -> str:
    return f"{x:.{decimale}f}".replace(".", ",").replace("-", "−")


def kratki_hr(x: float) -> str:
    """Broj bez suvišnih nula, s decimalnim zarezom (``189,48``)."""
    return f"{x:.10g}".replace(".", ",").replace("-", "−")


def kut_hr(stupnjevi: float) -> str:
    znak = "−" if stupnjevi < 0 else ""
    sekunde = round(abs(stupnjevi) * 3600, 1)
    st, ostatak = divmod(sekunde, 3600)
    mi, se = divmod(ostatak, 60)
    return f"{znak}{int(st)}° {int(mi):02d}′ {broj_hr(se, 1)}″"


def _vrijednost_hr(r: Rezultat, x: float) -> str:
    return kut_hr(x) if r.vrsta is Vrsta.KUT else broj_hr(x, r.decimale)


def _adresa_hr(r: Rezultat) -> str:
    adrese = ((r.predznak,) if r.predznak else ()) + r.adrese
    return adrese[0] if len(adrese) == 1 else f"{adrese[0]}:{adrese[-1]}"


# --- Čitanje vrijednosti ---------------------------------------------------------


def _u_broj(v: formule.Vrijednost) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, float | int):
        return float(v)
    try:
        return float(v.strip().replace(",", "."))
    except ValueError:
        return None


def _negativan_predznak(v: formule.Vrijednost) -> bool:
    return isinstance(v, str) and v.strip() in ("-", "−", "–")


def vrijednost_rezultata(r: Rezultat, citaj) -> float | None:
    """``citaj(adresa)`` vraća vrijednost ćelije; ``None`` ako rezultat nije broj."""
    dijelovi = [_u_broj(citaj(a)) for a in r.adrese]
    if any(d is None for d in dijelovi):
        return None
    if r.vrsta is Vrsta.BROJ:
        return dijelovi[0]
    st, mi, se = dijelovi
    negativan = any(d < 0 for d in dijelovi) or (r.predznak is not None and _negativan_predznak(citaj(r.predznak)))
    iznos = dms_u_stupnjeve(abs(st), abs(mi), abs(se))
    return -iznos if negativan else iznos


def necijele_sekunde(r: Rezultat, citaj) -> bool:
    """Sekunde kuta koji mora imati raspoređene popravke nisu cijeli broj."""
    if not r.cijele_sekunde:
        return False
    se = _u_broj(citaj(r.adrese[2]))
    return se is not None and abs(se - round(se)) > 1e-6


_PORUKA_SEKUNDI = ("popravke treba rasporediti na kutove u cijelim sekundama tako da je "
                   "njihov zbroj jednak fβ")


def _odstupa(r: Rezultat, pronadeno: float, ocekivano: float) -> bool:
    razlika = abs(pronadeno - ocekivano)
    if r.vrsta is Vrsta.KUT:
        razlika *= 3600
    return razlika > r.tolerancija + 1e-9


# --- Lanac formula -------------------------------------------------------------


def _ovisnosti(listovi: dict[str, dict[str, xlsx.Celija]], list_: str, adrese: Iterable[str]) -> set[tuple[str, str]]:
    """Sve ćelije o kojima ovise zadane ćelije (prijelazno), uključujući njih same."""
    vidjeno: set[tuple[str, str]] = set()
    stog = [(list_, a) for a in adrese]
    while stog:
        kljuc = stog.pop()
        if kljuc in vidjeno:
            continue
        vidjeno.add(kljuc)
        celija = listovi.get(kljuc[0], {}).get(kljuc[1])
        if celija is None or celija.formula is None:
            continue
        try:
            stablo = formule.parsiraj(celija.formula)
        except Nepodrzano:
            continue
        for ref in formule.reference(stablo):
            if isinstance(ref, formule.Ref):
                stog.append((ref.list or kljuc[0], ref.adresa))
            else:
                (r0, s0), (r1, s1) = xlsx.rastavi_adresu(ref.od.adresa), xlsx.rastavi_adresu(ref.do.adresa)
                cilj = ref.od.list or kljuc[0]
                stog += [
                    (cilj, xlsx.adresa(r, s))
                    for r in range(min(r0, r1), max(r0, r1) + 1)
                    for s in range(min(s0, s1), max(s0, s1) + 1)
                ]
    return vidjeno


def _decimale_literala(x: float) -> int:
    tekst = repr(x)
    return len(tekst.split(".")[1]) if "." in tekst and not tekst.endswith(".0") else 0


def _sumnjivo_u_lancu(
    listovi: dict[str, dict[str, xlsx.Celija]],
    list_zadatka: str,
    zadatak: Zadatak,
    r: Rezultat,
    poznate: list[float],
) -> list[str]:
    """Objašnjenje zašto formula ne slijedi ulaze: upisani brojevi u lancu formula."""
    ulazne = {(list_zadatka, u.adresa) for u in zadatak.ulazi}
    nalazi: list[str] = []
    for list_, adr in sorted(_ovisnosti(listovi, list_zadatka, r.adrese)):
        celija = listovi.get(list_, {}).get(adr)
        if celija is None or (list_, adr) in ulazne:
            continue
        if celija.formula is None:
            if adr not in r.adrese and _u_broj(celija.vrijednost) is not None and not isinstance(celija.vrijednost, str):
                nalazi.append(f"ćelija {adr} sadrži upisan broj {kratki_hr(celija.vrijednost)} umjesto formule")
            continue
        try:
            stablo = formule.parsiraj(celija.formula)
        except Nepodrzano:
            continue
        for lit in formule.brojevi(stablo):
            if lit in _UOBICAJENI:
                continue
            d = _decimale_literala(lit)
            if any(round(p, d) == lit or abs(p - lit) < 1e-9 for p in poznate):
                nalazi.append(f"formula u {adr} sadrži prepisanu vrijednost {kratki_hr(lit)}")
    return nalazi


# --- Provjera jednog zadatka ---------------------------------------------------


def _list_zadatka(knjiga: xlsx.RadnaKnjiga, vrste: tuple[str, ...], zadatak: Zadatak) -> str | None:
    if zadatak.list in knjiga.listovi:
        return zadatak.list
    # Preimenovan list: prihvaća se samo ako se listovi i dalje mogu upariti po redoslijedu.
    # List koji nosi ime drugog zadatka nije preimenovani list ovog zadatka.
    if len(knjiga.redoslijed) == len(vrste):
        kandidat = knjiga.redoslijed[vrste.index(zadatak.id)]
        if kandidat not in {z.list for z in ZADACI.values()}:
            return kandidat
    return None


def _neprovjerljivo(zadatak: Zadatak, kljuc: str, opis: str, adresa: str, poruka: str) -> Stavka:
    n = Status.NEPROVJERLJIVO
    return Stavka(zadatak.id, kljuc, opis, adresa, n, n, n, (poruka,))


def _provjeri_ulaze(
    zadatak: Zadatak, celije: dict[str, xlsx.Celija], ocekivani: dict[str, float] | None
) -> tuple[dict[str, float] | None, Stavka]:
    ulazi: dict[str, float] = {}
    nedostaju = []
    for u in zadatak.ulazi:
        celija = celije.get(u.adresa)
        v = _u_broj(celija.vrijednost) if celija is not None else None
        if v is None:
            nedostaju.append(f"{u.opis} ({u.adresa})")
        else:
            ulazi[u.kljuc] = v
    adresa = f"{zadatak.ulazi[0].adresa}…{zadatak.ulazi[-1].adresa}"
    if nedostaju:
        s = Status.NE_PROLAZI
        return None, Stavka(zadatak.id, "ulazi", "Ulazni podaci", adresa, s, s, s,
                            ("Nedostaju ulazni podaci: " + ", ".join(nedostaju) + ".",))
    if ocekivani is None:
        n, p = Status.NEPROVJERLJIVO, Status.PROSLO
        return ulazi, Stavka(zadatak.id, "ulazi", "Ulazni podaci", adresa, p, n, p,
                             ("Nije poznato kojem je studentu zadatak izdan; ulazni podaci nisu uspoređeni.",))
    razlike = [
        f"{u.opis} ({u.adresa}): {kratki_hr(ulazi[u.kljuc])} umjesto {kratki_hr(ocekivani[u.kljuc])}"
        for u in zadatak.ulazi
        if abs(ulazi[u.kljuc] - ocekivani[u.kljuc]) > _TOL_ULAZA
    ]
    p = Status.PROSLO
    if razlike:
        return ulazi, Stavka(zadatak.id, "ulazi", "Ulazni podaci", adresa, p, Status.NE_PROLAZI, p,
                             ("Ulazni podaci nisu podaci izdani ovom studentu: " + "; ".join(razlike) + ".",))
    return ulazi, Stavka(zadatak.id, "ulazi", "Ulazni podaci", adresa, p, p, p)


def _provjeri_rezultat(
    zadatak: Zadatak,
    r: Rezultat,
    listovi: dict[str, dict[str, xlsx.Celija]],
    list_: str,
    referentno: float,
    kontrole: list[tuple[dict[tuple[str, str], float], dict[str, float]]],
    poznate: list[float],
) -> Stavka:
    celije = listovi[list_]
    poruke: list[str] = []
    adresa = _adresa_hr(r)

    # 1. Formula u svakoj ćeliji rezultata
    prazne = [a for a in r.adrese if a not in celije]
    bez_formule = [a for a in r.adrese if a in celije and celije[a].formula is None]
    if prazne and len(prazne) == len(r.adrese):
        s = Status.NE_PROLAZI
        return Stavka(zadatak.id, r.kljuc, r.opis, adresa, s, s, s, ("Ćelija je prazna.",))
    if prazne or bez_formule:
        st_formule = Status.NE_PROLAZI
        if bez_formule:
            poruke.append(f"Upisan broj umjesto formule u {', '.join(bez_formule)}.")
        if prazne:
            poruke.append(f"Prazno: {', '.join(prazne)}.")
    else:
        st_formule = Status.PROSLO

    # 2. Vrijednost: spremljena u Excelu; ako je nema, izračunata iz formula
    racunalo = Racunalo(listovi, list_)
    spremljena = vrijednost_rezultata(r, lambda a: celije[a].vrijednost if a in celije else None)
    greske = [celije[a].greska for a in r.adrese if a in celije and celije[a].greska]
    izracunata: float | None = None
    greska_izracuna: str | None = None
    try:
        izracunata = vrijednost_rezultata(r, racunalo.celija)
    except ExcelGreska as e:
        greska_izracuna = e.kod
    except Nepodrzano as e:
        greska_izracuna = f"nepodržano ({e})"
    pronadeno = spremljena if spremljena is not None else izracunata
    citaj_pronadeno = (lambda a: celije[a].vrijednost if a in celije else None) if spremljena is not None         else racunalo.celija
    if greske:
        st_vrijednosti = Status.NE_PROLAZI
        poruke.append(f"Excel prikazuje grešku {greske[0]}.")
    elif pronadeno is None:
        st_vrijednosti = Status.NE_PROLAZI
        poruke.append("Rezultat nije broj.")
    elif _odstupa(r, pronadeno, referentno):
        st_vrijednosti = Status.NE_PROLAZI
        poruke.append(
            f"Vrijednost {_vrijednost_hr(r, pronadeno)}, očekivano {_vrijednost_hr(r, referentno)}."
        )
    elif necijele_sekunde(r, citaj_pronadeno):
        st_vrijednosti = Status.NE_PROLAZI
        poruke.append(f"Sekunde nisu cijeli broj ({_vrijednost_hr(r, pronadeno)}): {_PORUKA_SEKUNDI}.")
    else:
        st_vrijednosti = Status.PROSLO

    # 3. Općenitost: iste formule na drugim ulaznim podacima
    if st_formule is not Status.PROSLO:
        st_opcenito = Status.NE_PROLAZI
    elif greska_izracuna is not None and greska_izracuna.startswith("nepodržano"):
        st_opcenito = Status.NEPROVJERLJIVO
        poruke.append(f"Formulu nije moguće izračunati izvan Excela: {greska_izracuna}.")
    elif spremljena is not None and izracunata is not None and _odstupa(r, izracunata, spremljena):
        st_opcenito = Status.NEPROVJERLJIVO
        poruke.append("Spremljena vrijednost ne odgovara formuli (je li Excel preračunao radnu knjigu?).")
    else:
        st_opcenito = Status.PROSLO
        for zamjene, ocekivano in kontrole:
            kontrolno = Racunalo(listovi, list_, zamjene)
            try:
                dobiveno = vrijednost_rezultata(r, kontrolno.celija)
            except ExcelGreska as e:
                st_opcenito = Status.NE_PROLAZI
                poruke.append(f"S drugim ulaznim podacima formula daje grešku {e.kod}.")
                break
            except Nepodrzano as e:
                st_opcenito = Status.NEPROVJERLJIVO
                poruke.append(f"Formulu nije moguće izračunati izvan Excela: {e}.")
                break
            if dobiveno is None or _odstupa(r, dobiveno, ocekivano[r.kljuc]):
                st_opcenito = Status.NE_PROLAZI
                nadeno = "ne-broj" if dobiveno is None else _vrijednost_hr(r, dobiveno)
                poruke.append(
                    "Formula ne vrijedi općenito: s drugim ulaznim podacima daje "
                    f"{nadeno} umjesto {_vrijednost_hr(r, ocekivano[r.kljuc])}."
                )
                poruke += [s[0].upper() + s[1:] + "." for s in _sumnjivo_u_lancu(listovi, list_, zadatak, r, poznate)]
                break
            if necijele_sekunde(r, kontrolno.celija):
                st_opcenito = Status.NE_PROLAZI
                poruke.append(f"S drugim ulaznim podacima sekunde nisu cijeli broj: {_PORUKA_SEKUNDI}.")
                break
    return Stavka(zadatak.id, r.kljuc, r.opis, adresa, st_formule, st_vrijednosti, st_opcenito, tuple(poruke))


def provjeri_zadatak(
    knjiga: xlsx.RadnaKnjiga, profil: ProfilExcel, zadatak: Zadatak, jmbag: str | None,
    vrste: tuple[str, ...] | None = None,
) -> list[Stavka]:
    """``vrste``: svi zadaci koje student rješava (za uparivanje preimenovanih listova)."""
    list_ = _list_zadatka(knjiga, vrste or profil.zadaci.vrste, zadatak)
    if list_ is None:
        s = Status.NE_PROLAZI
        return [Stavka(zadatak.id, "list", zadatak.naziv, "", s, s, s,
                       (f"Radna knjiga nema list „{zadatak.list}“ (dodijeljeni zadatak).",))]
    celije = knjiga.listovi[list_]
    korak = profil.zadaci.korak_mjerenja
    ocekivani = (
        osobni_podaci(zadatak, profil.zadaci.sjeme, jmbag, korak) if jmbag and profil.zadaci.osobni_podaci else None
    )
    ulazi, stavka_ulaza = _provjeri_ulaze(zadatak, celije, ocekivani)
    stavke = [stavka_ulaza]
    if ulazi is None:
        return stavke + [
            _neprovjerljivo(zadatak, r.kljuc, r.opis, _adresa_hr(r), "Bez ulaznih podataka rezultat se ne može provjeriti.")
            for r in zadatak.rezultati
        ]
    referentno = zadatak.izracun(ulazi)
    kontrole = []
    for podaci in kontrolni_podaci(zadatak, korak):
        zamjene = {(list_, u.adresa): podaci[u.kljuc] for u in zadatak.ulazi}
        kontrole.append((zamjene, zadatak.izracun(podaci)))
    poznate = [v for v in ulazi.values() if v not in _UOBICAJENI] + list(referentno.values())
    neispravne: list[tuple[str, set[tuple[str, str]]]] = []  # (adresa za poruku, ćelije rezultata)
    for r in zadatak.rezultati:
        stavka = _provjeri_rezultat(zadatak, r, knjiga.listovi, list_, referentno[r.kljuc], kontrole, poznate)
        if stavka.status is Status.NE_PROLAZI:
            lanac = _ovisnosti(knjiga.listovi, list_, r.adrese) - {(list_, a) for a in r.adrese}
            uzroci = [adr for adr, celije_r in neispravne if lanac & celije_r]
            if uzroci:
                stavka = replace(stavka, poruke=stavka.poruke + (
                    f"Moguća posljedica greške u {', '.join(uzroci)} (ova formula koristi taj rezultat).",))
            neispravne.append((stavka.adresa, {(list_, a) for a in r.adrese}))
        stavke.append(stavka)
    return stavke


def _otisak(knjiga: xlsx.RadnaKnjiga) -> frozenset[str]:
    return frozenset(
        f"{ime}!{adr}={c.formula.replace(' ', '').upper()}"
        for ime, celije in knjiga.listovi.items()
        for adr, c in celije.items()
        if c.formula
    )


def _vrste_iz_datoteke(knjiga: xlsx.RadnaKnjiga, profil: ProfilExcel) -> tuple[str, ...]:
    """Zadaci koje je upisao osobni predložak, a bez toga oni čiji listovi postoje u datoteci."""
    upisano = tuple(v.strip() for v in knjiga.svojstva.prilagodena.get(SVOJSTVO_ZADATAK, "").split(",") if v.strip())
    if upisano and all(v in profil.zadaci.vrste for v in upisano):
        return upisano
    return tuple(v for v in profil.zadaci.vrste if ZADACI[v].list in knjiga.listovi)


def dodijeljeni_zadaci(
    knjiga: xlsx.RadnaKnjiga, profil: ProfilExcel, jmbag: str | None, redni_broj: int | None
) -> tuple[str, ...]:
    iz_datoteke = _vrste_iz_datoteke(knjiga, profil)
    jmbag_datoteke = knjiga.svojstva.prilagodena.get(SVOJSTVO_JMBAG) or None
    # Kod raspodjele "redom" vrijedi zadatak upisan u studentov vlastiti predložak, pa
    # naknadna promjena popisa (upis ili ispis studenta) ne mijenja dodijeljene zadatke.
    if profil.zadaci.raspodjela == "redom" and iz_datoteke and jmbag_datoteke and jmbag_datoteke == (
            jmbag or jmbag_datoteke) and SVOJSTVO_ZADATAK in knjiga.svojstva.prilagodena:
        return iz_datoteke
    return dodjela.dodijeljeni(profil, jmbag or jmbag_datoteke, redni_broj) or iz_datoteke


def _tekst_celije(celija: xlsx.Celija | None) -> str:
    if celija is None or celija.vrijednost is None:
        return ""
    v = celija.vrijednost
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip()


def _provjeri_zaglavlje(
    knjiga: xlsx.RadnaKnjiga, profil: ProfilExcel, vrste: tuple[str, ...], jmbag: str | None
) -> Stavka | None:
    """JMBAG u zaglavlju listova mora biti JMBAG kojem je predložak izdan."""
    if not jmbag:
        return None
    p, n = Status.PROSLO, Status.NE_PROLAZI
    razlike = []
    for vrsta in vrste:
        list_ = _list_zadatka(knjiga, vrste, ZADACI[vrsta])
        if list_ is None:
            continue
        upisano = _tekst_celije(knjiga.listovi[list_].get(ADRESA_JMBAG))
        if upisano != jmbag:
            razlike.append(f"„{list_}“: {upisano or 'prazno'}")
    if razlike:
        return Stavka("", "zaglavlje", "JMBAG u zaglavlju", ADRESA_JMBAG, p, n, p,
                      (f"JMBAG u zaglavlju nije {jmbag} ({'; '.join(razlike)}).",))
    return Stavka("", "zaglavlje", "JMBAG u zaglavlju", ADRESA_JMBAG, p, p, p)


def provjeri(
    naziv_datoteke: str, sadrzaj: bytes, profil: ProfilExcel, jmbag: str | None = None,
    redni_broj: int | None = None,
) -> IzvjestajExcel:
    """``jmbag`` i ``redni_broj`` (položaj u popisu) dolaze iz popisa; bez njih se koristi
    JMBAG upisan u predložak."""
    razlog = ulaz.provjeri_ulaz(naziv_datoteke, sadrzaj, ulaz.EXCEL)
    if razlog is not None:
        return IzvjestajExcel(naziv_datoteke, razlog)
    try:
        knjiga = xlsx.ucitaj(sadrzaj)
    except xlsx.GreskaPaketa:
        return IzvjestajExcel(naziv_datoteke, RazlogOdbijanja.OSTECENA)

    stavke: list[Stavka] = []
    p, n = Status.PROSLO, Status.NE_PROLAZI
    if naziv.odgovara_obrascu(naziv_datoteke, profil):
        stavke.append(Stavka("", "naziv", "Naziv datoteke", "", p, p, p))
    else:
        stavke.append(Stavka("", "naziv", "Naziv datoteke", "", p, n, p,
                             (f"Naziv mora biti oblika {profil.naziv_datoteke.obrazac}.",)))

    iz_datoteke = knjiga.svojstva.prilagodena.get(SVOJSTVO_JMBAG) or None
    if jmbag and iz_datoteke and jmbag != iz_datoteke:
        stavke.append(Stavka("", "izdano", "Izdani predložak", "", p, n, p,
                             ("Predložak je izdan drugom studentu (JMBAG u datoteci se ne podudara s popisom).",)))
    vrste = dodijeljeni_zadaci(knjiga, profil, jmbag, redni_broj)
    if not vrste:
        stavke.append(Stavka("", "list", "Listovi zadataka", "", n, n, n,
                             ("Radna knjiga nema nijedan list zadatka vježbe.",)))
    stavka_zaglavlja = _provjeri_zaglavlje(knjiga, profil, vrste, jmbag or iz_datoteke)
    if stavka_zaglavlja is not None:
        stavke.append(stavka_zaglavlja)
    for vrsta in vrste:
        stavke += provjeri_zadatak(knjiga, profil, ZADACI[vrsta], jmbag or iz_datoteke, vrste)
    return IzvjestajExcel(
        naziv_datoteke=naziv_datoteke,
        odbijeno=None,
        stavke=tuple(stavke),
        jmbag_iz_datoteke=iz_datoteke,
        svojstva=knjiga.svojstva,
        otisak=_otisak(knjiga),
    )


def slicnost(a: IzvjestajExcel, b: IzvjestajExcel) -> float:
    """Jaccardov indeks skupova formula dviju predaja (0 – ništa zajedničko, 1 – iste)."""
    if not a.otisak or not b.otisak:
        return 0.0
    return len(a.otisak & b.otisak) / len(a.otisak | b.otisak)

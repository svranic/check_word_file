"""ISVU popis studenata (AD-1): jedini čitač ISVU ``.xlsx`` izvoza (openpyxl) i
jedini vlasnik formata zamrznutog popisa ``<podatkovna mapa>/<vjezba>/popis.csv``.

``ucitaj_isvu`` sam pronalazi zaglavlje ispod metapodataka izvoza, normalizira
vrijednosti i vraća studente zajedno s potpunim popisom pogrešaka po retku.
``zamrzni``, ``procitaj_zamrznuti``, ``usporedi``, ``primijeni`` i ``spremi``
upravljaju zamrznutim popisom: Rbr. se nikad ne mijenja, a novi izvoz ne prepisuje
postojeći popis nego se s njim uspoređuje po JMBAG-u.
``zapisi_izdano`` i ``procitaj_izdano`` vlasnici su formata ``izdano.json`` (otisak formule
i verzija profila zapisani pri generiranju PDF-a sa svojstvima).
Osobni podaci se ne zapisuju u log.
"""

import csv
import io
import json
import logging
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from zoneinfo import ZoneInfo

import openpyxl

from provjera.word.jezgra import formula
from provjera.word.jezgra import profil as profil_modul
from provjera.word.jezgra import rbr as rbr_unos
from provjera.zajednicko.naziv import nfc

log = logging.getLogger(__name__)

STUPAC_RBR = "Rbr."
STUPAC_JMBAG = "JMBAG"
STUPAC_IME = "Ime"
STUPAC_PREZIME = "Prezime"
STUPAC_STATUS = "Status upisa"
STUPCI = (STUPAC_RBR, STUPAC_JMBAG, STUPAC_IME, STUPAC_PREZIME, STUPAC_STATUS)
NAJVISE_REDAKA_DO_ZAGLAVLJA = 50
ZNAMENKE_JMBAG = 10
PREFIKS_ISPISAN = "ispisan"


@dataclass(frozen=True)
class Student:
    rbr: int
    jmbag: str
    ime: str
    prezime: str
    aktivan: bool


@dataclass(frozen=True)
class GreskaRetka:
    """Pogreška popisa; ``redak`` je broj retka u Excelu (1-bazirano) ili ``None`` za cijelu datoteku."""

    redak: int | None
    poruka_kljuc: str
    parametri: Mapping[str, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parametri", MappingProxyType(dict(self.parametri)))


@dataclass(frozen=True)
class UcitaniPopis:
    studenti: tuple[Student, ...]
    greske: tuple[GreskaRetka, ...]

    @property
    def moze_zamrznuti(self) -> bool:
        return not self.greske

    @property
    def broj_neaktivnih(self) -> int:
        return sum(not s.aktivan for s in self.studenti)


def _kljuc_stupca(vrijednost: object) -> str:
    return " ".join(nfc(str(vrijednost)).split()).casefold() if vrijednost is not None else ""


def _tekst(vrijednost: object) -> str:
    """Tekst ćelije bez rubnih i višestrukih razmaka, u NFC obliku."""
    if vrijednost is None:
        return ""
    return " ".join(nfc(str(vrijednost)).split())


def _cijeli_broj(vrijednost: object) -> int | None:
    """Brojčana ćelija s cijelim brojem (``78`` ili ``78.0``); inače ``None``."""
    if isinstance(vrijednost, bool):
        return None
    if isinstance(vrijednost, int):
        return vrijednost
    if isinstance(vrijednost, float) and vrijednost.is_integer():
        return int(vrijednost)
    return None


def _rbr(vrijednost: object) -> int | None:
    if isinstance(vrijednost, (int, float)) and not isinstance(vrijednost, bool):
        broj = _cijeli_broj(vrijednost)
        # Broj ide kroz isti tumač kao tekst, pa vrijede ista ograničenja (pozitivan, ≤ 9 znamenki).
        vrijednost = str(broj) if broj is not None else "-"
    rezultat = rbr_unos.parsiraj("" if vrijednost is None else str(vrijednost))
    return rezultat if isinstance(rezultat, int) else None


def _jmbag(vrijednost: object) -> str:
    """Tekst i broj normaliziraju se jednako: bez razmaka, samo znamenke nadopunjene do 10."""
    broj = _cijeli_broj(vrijednost)
    tekst = str(broj) if broj is not None else _tekst(vrijednost).replace(" ", "")
    if tekst.isascii() and tekst.isdigit():
        return tekst.zfill(ZNAMENKE_JMBAG)
    return tekst


def _jmbag_valjan(jmbag: str) -> bool:
    return len(jmbag) == ZNAMENKE_JMBAG and jmbag.isascii() and jmbag.isdigit()


def _ucitaj_listove(sadrzaj: bytes) -> list[list[tuple[object, ...]]] | None:
    """Retci svakog radnog lista, redom kojim su listovi u knjizi."""
    try:
        knjiga = openpyxl.load_workbook(io.BytesIO(sadrzaj), data_only=True)
        return [list(list_.iter_rows(values_only=True)) for list_ in knjiga.worksheets]
    except Exception:  # noqa: BLE001 — svaka pogreška čitanja znači nečitljivu datoteku
        log.info("ISVU izvoz nije čitljiv .xlsx")
        return None


def _pronadi_zaglavlje(
    retci: list[tuple[object, ...]],
) -> tuple[int, dict[str, int]] | tuple[None, tuple[str, ...]]:
    """Vraća (indeks retka, stupci) ili (None, stupci koji nedostaju u najboljem kandidatu)."""
    trazeni = {_kljuc_stupca(s): s for s in STUPCI}
    nedostaju = STUPCI
    for indeks, redak in enumerate(retci[:NAJVISE_REDAKA_DO_ZAGLAVLJA]):
        stupci: dict[str, int] = {}
        for polozaj, vrijednost in enumerate(redak):
            kljuc = _kljuc_stupca(vrijednost)
            if kljuc in trazeni and trazeni[kljuc] not in stupci:
                stupci[trazeni[kljuc]] = polozaj
        if len(stupci) == len(STUPCI):
            return indeks, stupci
        ovdje_nedostaju = tuple(s for s in STUPCI if s not in stupci)
        if len(ovdje_nedostaju) < len(nedostaju):
            nedostaju = ovdje_nedostaju
    return None, nedostaju


def ucitaj_isvu(sadrzaj: bytes) -> UcitaniPopis:
    """Čita ISVU ``.xlsx`` izvoz; vraća sve studente i sve pogreške (nikad ne baca)."""
    listovi = _ucitaj_listove(sadrzaj)
    if listovi is None:
        return UcitaniPopis((), (GreskaRetka(None, "popis.necitljiv"),))
    nedostaju = STUPCI
    for retci in listovi:  # prvi list sa zaglavljem
        indeks_zaglavlja, stupci = _pronadi_zaglavlje(retci)
        if indeks_zaglavlja is not None:
            break
        if len(stupci) < len(nedostaju):
            nedostaju = stupci
    else:
        parametri = {"stupci": ", ".join(nedostaju), "najvise": NAJVISE_REDAKA_DO_ZAGLAVLJA}
        return UcitaniPopis((), (GreskaRetka(None, "popis.bez_zaglavlja", parametri),))

    studenti: list[Student] = []
    greske: list[GreskaRetka] = []
    redak_rbr: dict[int, int] = {}
    redak_jmbag: dict[str, int] = {}
    for indeks in range(indeks_zaglavlja + 1, len(retci)):
        redak = retci[indeks]

        def celija(stupac: str) -> object:
            polozaj = stupci[stupac]
            return redak[polozaj] if polozaj < len(redak) else None

        # Prazan redak ili redak zbroja/podnožja s vrijednostima samo u drugim stupcima.
        if all(not _tekst(celija(s)) for s in STUPCI):
            continue
        broj_retka = indeks + 1  # Excel broji od 1

        greske_retka: list[GreskaRetka] = []
        broj = _rbr(celija(STUPAC_RBR))
        if broj is None:
            greske_retka.append(GreskaRetka(broj_retka, "popis.rbr_neispravan"))
        elif broj in redak_rbr:
            greske_retka.append(
                GreskaRetka(broj_retka, "popis.dupli_rbr", {"rbr": broj, "prvi": redak_rbr[broj]})
            )
        else:
            redak_rbr[broj] = broj_retka

        jmbag = _jmbag(celija(STUPAC_JMBAG))
        if not jmbag:
            greske_retka.append(GreskaRetka(broj_retka, "popis.prazan_jmbag"))
        elif not _jmbag_valjan(jmbag):
            greske_retka.append(GreskaRetka(broj_retka, "popis.jmbag_neispravan"))
        elif jmbag in redak_jmbag:
            greske_retka.append(
                GreskaRetka(broj_retka, "popis.dupli_jmbag", {"prvi": redak_jmbag[jmbag]})
            )
        else:
            redak_jmbag[jmbag] = broj_retka

        ime = _tekst(celija(STUPAC_IME))
        prezime = _tekst(celija(STUPAC_PREZIME))
        if not ime:
            greske_retka.append(GreskaRetka(broj_retka, "popis.prazno_ime"))
        if not prezime:
            greske_retka.append(GreskaRetka(broj_retka, "popis.prazno_prezime"))

        if greske_retka:
            greske += greske_retka
            continue
        status = _tekst(celija(STUPAC_STATUS)).casefold()
        studenti.append(
            Student(broj, jmbag, ime, prezime, aktivan=not status.startswith(PREFIKS_ISPISAN))
        )

    if not studenti and not greske:
        greske.append(GreskaRetka(None, "popis.bez_studenata"))
    log.info("ISVU izvoz: %d studenata, %d pogrešaka", len(studenti), len(greske))
    return UcitaniPopis(tuple(studenti), tuple(greske))


# --- Zamrznuti popis (priča 3.2) ----------------------------------------------

DATOTEKA_POPISA = "popis.csv"
STUPCI_ZAMRZNUTOG = ("rbr", "jmbag", "ime", "prezime", "aktivan")
KODIRANJE = "utf-8-sig"  # UTF-8 s BOM-om, da ga Excel ispravno otvori
ISTINA, LAZ = "true", "false"
ZNAKOVI_FORMULE = ("=", "+", "-", "@", "\t", "\r")
PREFIKS_TEKSTA = "'"


class GreskaZamrznutog(Exception):
    """Zamrznuti popis nije čitljiv; ``redak`` je redak u CSV-u (1 = zaglavlje) ili ``None``."""

    def __init__(
        self,
        redak: int | None,
        poruka_kljuc: str,
        parametri: Mapping[str, str | int] | None = None,
    ) -> None:
        super().__init__(poruka_kljuc)
        self.redak = redak
        self.poruka_kljuc = poruka_kljuc
        self.parametri: Mapping[str, str | int] = MappingProxyType(dict(parametri or {}))


class PopisVecZamrznut(Exception):
    """``popis.csv`` već postoji; novi izvoz ga nikad ne prepisuje."""


@dataclass(frozen=True)
class PromjenaImena:
    zamrznuti: Student
    izvoz: Student


@dataclass(frozen=True)
class Razlike:
    """Razlike zamrznutog popisa i novog izvoza, uspoređene po JMBAG-u (nikad po Rbr.)."""

    novi: tuple[Student, ...] = ()  # iz izvoza, redoslijedom izvoza (Rbr. je ISVU-ov)
    ispisani: tuple[Student, ...] = ()  # iz zamrznutog popisa
    ponovno_upisani: tuple[Student, ...] = ()  # iz zamrznutog popisa
    promijenjeno_ime: tuple[PromjenaImena, ...] = ()  # samo upozorenje, ne primjenjuje se

    @property
    def ima_promjena(self) -> bool:
        """Ima li promjena koje ``primijeni`` zapisuje (promjena imena se ne primjenjuje)."""
        return bool(self.novi or self.ispisani or self.ponovno_upisani)


def putanja_popisa(mapa_vjezbe: Path) -> Path:
    return mapa_vjezbe / DATOTEKA_POPISA


def _zasticeno(vrijednost: str) -> str:
    """Prefiks ``'`` sprječava da Excel vrijednost protumači kao formulu.

    Prefiks dobiva i vrijednost koja već počinje s ``'``, pa je kružni put bez gubitaka.
    """
    if vrijednost.startswith((*ZNAKOVI_FORMULE, PREFIKS_TEKSTA)):
        return PREFIKS_TEKSTA + vrijednost
    return vrijednost


def _bez_zastite(vrijednost: str) -> str:
    if vrijednost.startswith(PREFIKS_TEKSTA) and vrijednost[1:].startswith(
        (*ZNAKOVI_FORMULE, PREFIKS_TEKSTA)
    ):
        return vrijednost[1:]
    return vrijednost


def _provjeri_studente(studenti: Sequence[Student]) -> None:
    """Zapisuje se samo popis koji se može ponovno pročitati (inače je to pogreška u kodu)."""
    if not studenti:
        raise ValueError("popis bez studenata se ne zapisuje")
    if len({s.rbr for s in studenti}) != len(studenti):
        raise ValueError("Rbr. u popisu nisu jedinstveni")
    if len({s.jmbag for s in studenti}) != len(studenti):
        raise ValueError("JMBAG-ovi u popisu nisu jedinstveni")
    for s in studenti:
        if s.rbr < 1 or not _jmbag_valjan(s.jmbag) or not s.ime.strip() or not s.prezime.strip():
            raise ValueError("student u popisu nije ispravan")


def _zapisi(studenti: Sequence[Student], putanja: Path, *, iskljucivo: bool) -> None:
    """Zapisuje privremenu datoteku u istoj mapi pa je atomski postavlja na ``putanja``.

    ``iskljucivo`` (prvo zamrzavanje) koristi ``os.link``, koji ne uspijeva ako datoteka
    već postoji, pa ni istodobno zamrzavanje ne može prepisati postojeći popis.
    """
    _provjeri_studente(studenti)
    putanja.parent.mkdir(parents=True, exist_ok=True)
    izlaz = io.StringIO()
    pisac = csv.writer(izlaz, lineterminator="\r\n")
    pisac.writerow(STUPCI_ZAMRZNUTOG)
    for s in studenti:
        pisac.writerow(
            (
                s.rbr,
                _zasticeno(s.jmbag),
                _zasticeno(s.ime),
                _zasticeno(s.prezime),
                ISTINA if s.aktivan else LAZ,
            )
        )
    opisnik, privremena = tempfile.mkstemp(
        prefix=f".{DATOTEKA_POPISA}.", suffix=".tmp", dir=putanja.parent
    )
    sadrzaj = izlaz.getvalue().encode(KODIRANJE)
    try:
        with os.fdopen(opisnik, "wb") as datoteka:
            datoteka.write(sadrzaj)
            datoteka.flush()
            os.fsync(datoteka.fileno())
        if iskljucivo:
            try:
                os.link(privremena, putanja)
            except FileExistsError as greska:
                raise PopisVecZamrznut(str(putanja)) from greska
            except OSError:
                # Datotečni sustav bez tvrdih poveznica (FAT, neki mrežni diskovi).
                _stvori_iskljucivo(putanja, sadrzaj)
        else:
            os.replace(privremena, putanja)
    finally:
        Path(privremena).unlink(missing_ok=True)
    log.info("Zamrznuti popis zapisan: %d studenata", len(studenti))


def _stvori_iskljucivo(putanja: Path, sadrzaj: bytes) -> None:
    """Zamjena za ``os.link``: stvaranje koje ne uspijeva ako datoteka već postoji (``"xb"``)."""
    try:
        datoteka = open(putanja, "xb")  # noqa: SIM115 — zatvara se odmah ispod
    except FileExistsError as greska:
        raise PopisVecZamrznut(str(putanja)) from greska
    try:
        with datoteka:
            datoteka.write(sadrzaj)
            datoteka.flush()
            os.fsync(datoteka.fileno())
    except BaseException:
        putanja.unlink(missing_ok=True)  # nedovršen popis koji je stvorio ovaj poziv
        raise


def spremi(studenti: Sequence[Student], putanja: Path) -> None:
    """Atomski zapisuje (i prepisuje) popis: privremena datoteka pa ``os.replace``."""
    _zapisi(studenti, putanja, iskljucivo=False)


def zamrzni(studenti: Sequence[Student], mapa_vjezbe: Path) -> Path:
    """Prvo zamrzavanje; postojeći ``popis.csv`` se nikad ne prepisuje (``PopisVecZamrznut``).

    Pozivatelj zamrzava samo popis za koji je ``UcitaniPopis.moze_zamrznuti``.
    """
    putanja = putanja_popisa(mapa_vjezbe)
    if putanja.exists():
        raise PopisVecZamrznut(str(putanja))
    _zapisi(studenti, putanja, iskljucivo=True)
    return putanja


def procitaj_zamrznuti(putanja: Path) -> tuple[Student, ...]:
    """Čita i provjerava ``popis.csv``; neispravna datoteka baca ``GreskaZamrznutog``."""
    try:
        tekst = putanja.read_bytes().decode(KODIRANJE)
    except (FileNotFoundError, UnicodeDecodeError) as greska:
        raise GreskaZamrznutog(None, "popis.zamrznuti_necitljiv") from greska
    except OSError as greska:  # npr. datoteka zaključana u Excelu
        raise GreskaZamrznutog(None, "popis.zamrznuti_zakljucan") from greska

    citac = csv.reader(io.StringIO(tekst, newline=""), strict=True)
    studenti: list[Student] = []
    try:
        zaglavlje = next(citac, None)
        if zaglavlje is None:
            raise GreskaZamrznutog(None, "popis.zamrznuti_prazan")
        if tuple(zaglavlje) != STUPCI_ZAMRZNUTOG:
            raise GreskaZamrznutog(
                1, "popis.zamrznuti_zaglavlje", {"stupci": ",".join(STUPCI_ZAMRZNUTOG)}
            )
        redak_rbr: dict[int, int] = {}
        redak_jmbag: dict[str, int] = {}
        for redak in citac:
            broj_retka = citac.line_num
            if not redak:
                continue  # prazan redak (npr. na kraju datoteke)
            if len(redak) != len(STUPCI_ZAMRZNUTOG):
                raise GreskaZamrznutog(
                    broj_retka,
                    "popis.zamrznuti_broj_stupaca",
                    {"ocekivano": len(STUPCI_ZAMRZNUTOG), "pronadeno": len(redak)},
                )
            rbr_tekst, jmbag, ime, prezime, aktivan = (_bez_zastite(v) for v in redak)
            if not (rbr_tekst.isascii() and rbr_tekst.isdigit()) or int(rbr_tekst) < 1:
                raise GreskaZamrznutog(broj_retka, "popis.rbr_neispravan")
            broj = int(rbr_tekst)
            if broj in redak_rbr:
                raise GreskaZamrznutog(
                    broj_retka, "popis.dupli_rbr", {"rbr": broj, "prvi": redak_rbr[broj]}
                )
            if not _jmbag_valjan(jmbag):
                raise GreskaZamrznutog(broj_retka, "popis.jmbag_neispravan")
            if jmbag in redak_jmbag:
                raise GreskaZamrznutog(
                    broj_retka, "popis.dupli_jmbag", {"prvi": redak_jmbag[jmbag]}
                )
            if not ime.strip():
                raise GreskaZamrznutog(broj_retka, "popis.prazno_ime")
            if not prezime.strip():
                raise GreskaZamrznutog(broj_retka, "popis.prazno_prezime")
            if aktivan not in (ISTINA, LAZ):
                raise GreskaZamrznutog(broj_retka, "popis.zamrznuti_aktivan")
            redak_rbr[broj] = broj_retka
            redak_jmbag[jmbag] = broj_retka
            studenti.append(Student(broj, jmbag, ime, prezime, aktivan == ISTINA))
    except csv.Error as greska:
        raise GreskaZamrznutog(citac.line_num or None, "popis.zamrznuti_necitljiv") from greska
    if not studenti:
        raise GreskaZamrznutog(None, "popis.zamrznuti_prazan")
    return tuple(studenti)


def usporedi(zamrznuti: Sequence[Student], izvoz: Sequence[Student]) -> Razlike:
    """Uspoređuje po JMBAG-u; Rbr. iz izvoza se zanemaruje (ISVU prenumerira)."""
    po_jmbagu_izvoz = {s.jmbag: s for s in izvoz}
    zamrznuti_jmbag = {s.jmbag for s in zamrznuti}
    novi = tuple(s for s in izvoz if s.aktivan and s.jmbag not in zamrznuti_jmbag)
    ispisani: list[Student] = []
    ponovno: list[Student] = []
    imena: list[PromjenaImena] = []
    for s in zamrznuti:
        u_izvozu = po_jmbagu_izvoz.get(s.jmbag)
        aktivan_u_izvozu = u_izvozu is not None and u_izvozu.aktivan
        if s.aktivan and not aktivan_u_izvozu:
            ispisani.append(s)
        elif not s.aktivan and aktivan_u_izvozu:
            ponovno.append(s)
        if u_izvozu is not None and (u_izvozu.ime, u_izvozu.prezime) != (s.ime, s.prezime):
            imena.append(PromjenaImena(s, u_izvozu))
    return Razlike(novi, tuple(ispisani), tuple(ponovno), tuple(imena))


def sljedeci_rbr(zamrznuti: Sequence[Student]) -> int:
    """Rbr. koji dobiva prvi kasno upisani student: ``max(rbr)+1``."""
    return max((s.rbr for s in zamrznuti), default=0) + 1


def primijeni(zamrznuti: Sequence[Student], razlike: Razlike) -> tuple[Student, ...]:
    """Novi dobivaju ``max(rbr)+1``, ``+2``…; postojećima se mijenja samo ``aktivan``."""
    ispisani = {s.jmbag for s in razlike.ispisani}
    ponovno = {s.jmbag for s in razlike.ponovno_upisani}
    postojeci = {s.jmbag for s in zamrznuti}
    rezultat: list[Student] = []
    for s in zamrznuti:
        if s.jmbag in ispisani:
            s = Student(s.rbr, s.jmbag, s.ime, s.prezime, aktivan=False)
        elif s.jmbag in ponovno:
            s = Student(s.rbr, s.jmbag, s.ime, s.prezime, aktivan=True)
        rezultat.append(s)
    sljedeci = sljedeci_rbr(zamrznuti)
    for s in razlike.novi:
        if s.jmbag in postojeci:
            continue
        postojeci.add(s.jmbag)
        rezultat.append(Student(sljedeci, s.jmbag, s.ime, s.prezime, aktivan=True))
        sljedeci += 1
    return tuple(rezultat)


# --- Izdano (priča 3.5) -------------------------------------------------------

DATOTEKA_IZDANO = "izdano.json"
PREFIKS_PDF = "svojstva_"
ZONA = ZoneInfo("Europe/Zagreb")


class GreskaIzdanog(Exception):
    """``izdano.json`` postoji, ali nije čitljiv ili ispravan."""

    poruka_kljuc = "popis.izdano_necitljivo"


@dataclass(frozen=True)
class Izdano:
    formula_otisak: str
    profil_verzija: str
    vrijeme: datetime  # s vremenskom zonom Europe/Zagreb


def putanja_izdanog(mapa_vjezbe: Path) -> Path:
    return mapa_vjezbe / DATOTEKA_IZDANO


def putanja_pdf(mapa_vjezbe: Path, id_vjezbe: str) -> Path:
    """``<mapa>/<vjezba>/svojstva_<vjezba.id>.pdf``."""
    return mapa_vjezbe / f"{PREFIKS_PDF}{id_vjezbe}.pdf"


def zapisi_atomski(putanja: Path, sadrzaj: bytes) -> None:
    """Privremena datoteka u istoj mapi pa ``os.replace``: čitatelj nikad ne vidi pola datoteke."""
    putanja.parent.mkdir(parents=True, exist_ok=True)
    opisnik, privremena = tempfile.mkstemp(
        prefix=f".{putanja.name}.", suffix=".tmp", dir=putanja.parent
    )
    try:
        with os.fdopen(opisnik, "wb") as datoteka:
            datoteka.write(sadrzaj)
            datoteka.flush()
            os.fsync(datoteka.fileno())
        os.replace(privremena, putanja)
    finally:
        Path(privremena).unlink(missing_ok=True)


def zapisi_izdano(
    mapa_vjezbe: Path, profil: profil_modul.Profil, vrijeme: datetime
) -> Path:
    """Atomski zapisuje (i prepisuje) ``izdano.json``; ``vrijeme`` mora imati vremensku zonu."""
    if vrijeme.tzinfo is None or vrijeme.utcoffset() is None:
        raise ValueError("vrijeme mora imati vremensku zonu")
    podaci = {
        "formula_otisak": formula.otisak(profil.formula),
        "profil_verzija": profil_modul.verzija(profil),
        "vrijeme": vrijeme.astimezone(ZONA).isoformat(timespec="seconds"),
    }
    putanja = putanja_izdanog(mapa_vjezbe)
    sadrzaj = json.dumps(podaci, ensure_ascii=False, indent=2) + "\n"
    zapisi_atomski(putanja, sadrzaj.encode("utf-8"))
    log.info("izdano.json zapisan")
    return putanja


def procitaj_izdano(mapa_vjezbe: Path) -> Izdano | None:
    """``None`` ako PDF još nije generiran; neispravna datoteka baca ``GreskaIzdanog``."""
    putanja = putanja_izdanog(mapa_vjezbe)
    if not putanja.exists():
        return None
    try:
        podaci = json.loads(putanja.read_bytes().decode("utf-8"))
        otisak, verzija = podaci["formula_otisak"], podaci["profil_verzija"]
        vrijeme = datetime.fromisoformat(podaci["vrijeme"])
        if not (isinstance(otisak, str) and otisak and isinstance(verzija, str) and verzija):
            raise ValueError("otisak i verzija moraju biti neprazan tekst")
        if vrijeme.tzinfo is None:
            raise ValueError("vrijeme nema vremensku zonu")
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as greska:
        raise GreskaIzdanog(str(putanja)) from greska
    return Izdano(otisak, verzija, vrijeme.astimezone(ZONA))

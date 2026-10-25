"""Tipovi zadataka (trigonometrijski obrasci 13, 14-cos i 14-tan): jedini izvor adresa ćelija,
referentnog izračuna i generatora ulaznih podataka.

Predložak (``provjera.excel.adapteri.predlozak``) crta obrazac oko ovih adresa, a
provjera čita iste adrese. Kutovi su u decimalnim stupnjevima, ``f`` i ``v`` u sekundama.
"""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class Vrsta(Enum):
    BROJ = "broj"
    KUT = "kut"  # tri ćelije: stupnjevi, minute, sekunde (+ opcionalna ćelija predznaka)


@dataclass(frozen=True)
class Ulaz:
    kljuc: str
    adresa: str
    opis: str
    decimale: int = 0  # za predložak i poruke


@dataclass(frozen=True)
class Rezultat:
    kljuc: str
    opis: str
    adrese: tuple[str, ...]  # BROJ: jedna adresa; KUT: (°, ′, ″)
    vrsta: Vrsta = Vrsta.BROJ
    tolerancija: float = 0.01  # BROJ: u jedinici rezultata; KUT: u lučnim sekundama
    decimale: int = 2
    predznak: str | None = None  # KUT: ćelija s „+“/„-“ (kut može biti negativan)
    formula: str = ""  # zapis formule koji predložak prikazuje kao uputu
    cijele_sekunde: bool = False  # KUT: sekunde moraju biti cijeli broj (raspoređeni popravci)


@dataclass(frozen=True)
class Zadatak:
    id: str
    naziv: str
    list: str  # ime lista u radnoj knjizi
    obrazac: str
    ulazi: tuple[Ulaz, ...]
    kutovi_ulaza: tuple[str, ...]  # ključevi kutova čiji su ulazi kljuc_st/_min/_sek
    rezultati: tuple[Rezultat, ...]
    izracun: Callable[[dict[str, float]], dict[str, float]]
    # (rng, varijanta, korak mjerenja u sekundama) → ulazni podaci
    generator: Callable[[random.Random, int, int], dict[str, float]]

    def rezultat(self, kljuc: str) -> Rezultat:
        return next(r for r in self.rezultati if r.kljuc == kljuc)


# --- Pomoćno -----------------------------------------------------------------


def dms_u_stupnjeve(st: float, mi: float, se: float) -> float:
    return st + mi / 60 + se / 3600


def stupnjevi_u_dms(kut: float) -> tuple[int, int, int]:
    """Na cijele sekunde; predznak nosi samo prvi različit od nule dio."""
    ukupno = round(abs(kut) * 3600)
    st, ostatak = divmod(ukupno, 3600)
    mi, se = divmod(ostatak, 60)
    if kut < 0:
        return (-st, mi, se) if st else ((0, -mi, se) if mi else (0, 0, -se))
    return st, mi, se


def _kut(u: dict[str, float], k: str) -> float:
    return dms_u_stupnjeve(u[f"{k}_st"], u[f"{k}_min"], u[f"{k}_sek"])


def _dms_ulazi(kljuc: str, opis: str, redak: int, stupac0: str) -> tuple[Ulaz, ...]:
    s = ord(stupac0)
    return (
        Ulaz(f"{kljuc}_st", f"{chr(s)}{redak}", f"{opis} (°)"),
        Ulaz(f"{kljuc}_min", f"{chr(s + 1)}{redak}", f"{opis} (′)"),
        Ulaz(f"{kljuc}_sek", f"{chr(s + 2)}{redak}", f"{opis} (″)"),
    )


def _dms_adrese(redak: int, stupac0: str) -> tuple[str, str, str]:
    s = ord(stupac0)
    return (f"{chr(s)}{redak}", f"{chr(s + 1)}{redak}", f"{chr(s + 2)}{redak}")


def _postavi_kut(u: dict[str, float], k: str, kut: float) -> None:
    st, mi, se = stupnjevi_u_dms(kut)
    u[f"{k}_st"], u[f"{k}_min"], u[f"{k}_sek"] = float(st), float(mi), float(se)


def _duljina(rng: random.Random, od: float, do: float) -> float:
    return round(rng.uniform(od, do), 2)


# --- Sinusov poučak (obrazac 13) ---------------------------------------------
#
# Stupci: B oznaka | C–E mjereni kut | F–H izjednačeni kut | I sinus | J b·cos γ / c·cos β | K duljine


def _izracun_sinus(u: dict[str, float]) -> dict[str, float]:
    alfa, beta, gama = (_kut(u, k) for k in ("alfa", "beta", "gama"))
    zbroj = alfa + beta + gama
    f = (180 - zbroj) * 3600
    v = f / 3
    a1, b1, g1 = (k + v / 3600 for k in (alfa, beta, gama))
    sa, sb, sg = (math.sin(math.radians(k)) for k in (a1, b1, g1))
    m = u["a"] / sa
    b, c = m * sb, m * sg
    bcg, ccb = b * math.cos(math.radians(g1)), c * math.cos(math.radians(b1))
    return {
        "zbroj_mjerenih": zbroj, "f": f, "v": v,
        "alfa_izj": a1, "beta_izj": b1, "gama_izj": g1, "zbroj_izj": a1 + b1 + g1,
        "sin_alfa": sa, "sin_beta": sb, "sin_gama": sg,
        "m": m, "b": b, "c": c, "b_cos_gama": bcg, "c_cos_beta": ccb, "a_kontrola": bcg + ccb,
    }


def _generator_sinus(rng: random.Random, varijanta: int, korak: int) -> dict[str, float]:
    while True:
        alfa = rng.uniform(35, 95)
        beta = rng.uniform(35, min(100, 145 - alfa))
        if 180 - alfa - beta >= 30:
            break
    pravi = [round(alfa * 3600), round(beta * 3600)]
    pravi.append(180 * 3600 - sum(pravi))
    # Mjerenja (u sekundama) zaokružena na korak instrumenta, uz mjerni šum. Varijanta određuje
    # predznak zatvaranja f ≠ 0 i, kad je to moguće, ostatak |f| pri dijeljenju s 3 (1 ili 2),
    # tako da kontrolni podaci provjere raspored popravaka u oba slučaja.
    pozitivno, ostatak = varijanta % 2 == 0, 1 + (varijanta // 2) % 2
    while True:
        mjereni = [korak * round((p + rng.randint(-20, 20)) / korak) for p in pravi]
        f = 180 * 3600 - sum(mjereni)
        if f == 0 or (f > 0) != pozitivno or (korak % 3 and abs(f) % 3 != ostatak):
            continue
        break
    u: dict[str, float] = {}
    for k, sekunde in zip(("alfa", "beta", "gama"), mjereni):
        _postavi_kut(u, k, sekunde / 3600)
    u["a"] = _duljina(rng, 120, 650)
    return u


_KUT_TOL = 1.0
# Popravak pojedinog kuta je ⌊f/3⌋ ili ⌈f/3⌉ cijelih sekundi: odstupanje od α + f/3 najviše 2/3″.
_KUT_TOL_IZJ = 0.67
_SINUS = Zadatak(
    id="sinus",
    naziv="Sinusov poučak",
    list="Sinusov poučak",
    obrazac="Trigonometrijski obrazac br. 13 – Računanje trokuta po sinusovom poučku",
    ulazi=(
        *_dms_ulazi("alfa", "Mjereni kut α", 8, "C"),
        *_dms_ulazi("beta", "Mjereni kut β", 9, "C"),
        *_dms_ulazi("gama", "Mjereni kut γ", 10, "C"),
        Ulaz("a", "K8", "Mjerena duljina a", 2),
    ),
    kutovi_ulaza=("alfa", "beta", "gama"),
    rezultati=(
        Rezultat("zbroj_mjerenih", "Zbroj mjerenih kutova", _dms_adrese(11, "C"), Vrsta.KUT, _KUT_TOL,
                 formula="α + β + γ"),
        Rezultat("f", "Odstupanje fβ (″)", ("E12",), tolerancija=0.01, decimale=0,
                 formula="fβ = 180° − (α + β + γ)"),
        Rezultat("v", "Popravak vβ (″)", ("E13",), tolerancija=0.5, decimale=2, formula="vβ = fβ / 3"),
        Rezultat("alfa_izj", "Izjednačeni kut α′", _dms_adrese(8, "F"), Vrsta.KUT, _KUT_TOL_IZJ,
                 formula="α′ = α + v₁ (v₁ u cijelim sekundama)", cijele_sekunde=True),
        Rezultat("beta_izj", "Izjednačeni kut β′", _dms_adrese(9, "F"), Vrsta.KUT, _KUT_TOL_IZJ,
                 formula="β′ = β + v₂ (v₂ u cijelim sekundama)", cijele_sekunde=True),
        Rezultat("gama_izj", "Izjednačeni kut γ′", _dms_adrese(10, "F"), Vrsta.KUT, _KUT_TOL_IZJ,
                 formula="γ′ = γ + v₃ (v₃ u cijelim sekundama)", cijele_sekunde=True),
        Rezultat("zbroj_izj", "Zbroj izjednačenih kutova", _dms_adrese(11, "F"), Vrsta.KUT, 0.05,
                 formula="α′ + β′ + γ′ = 180° 00′ 00″ (v₁ + v₂ + v₃ = fβ)"),
        Rezultat("sin_alfa", "sin α′", ("I8",), tolerancija=2e-5, decimale=5, formula="sin α′"),
        Rezultat("sin_beta", "sin β′", ("I9",), tolerancija=2e-5, decimale=5, formula="sin β′"),
        Rezultat("sin_gama", "sin γ′", ("I10",), tolerancija=2e-5, decimale=5, formula="sin γ′"),
        Rezultat("m", "m = a / sin α′", ("I12",), tolerancija=0.02, decimale=2, formula="m = a / sin α′"),
        Rezultat("b", "Stranica b", ("K9",), tolerancija=0.02, formula="b = m · sin β′"),
        Rezultat("c", "Stranica c", ("K10",), tolerancija=0.02, formula="c = m · sin γ′"),
        Rezultat("b_cos_gama", "b · cos γ′", ("J12",), tolerancija=0.02, formula="b · cos γ′"),
        Rezultat("c_cos_beta", "c · cos β′", ("J13",), tolerancija=0.02, formula="c · cos β′"),
        Rezultat("a_kontrola", "Kontrola a = b·cos γ′ + c·cos β′", ("K13",), tolerancija=0.02,
                 formula="a = b · cos γ′ + c · cos β′"),
    ),
    izracun=_izracun_sinus,
    generator=_generator_sinus,
)


# --- Kosinusov poučak (obrazac 14 – cos) --------------------------------------
#
# Stupci: B oznaka | C–E kut | F oznaka | G duljina | I oznaka | J vrijednost


def _izracun_kosinus(u: dict[str, float]) -> dict[str, float]:
    alfa, b, c = _kut(u, "alfa"), u["b"], u["c"]
    cos_a = math.cos(math.radians(alfa))
    a2 = b * b + c * c - 2 * b * c * cos_a
    a = math.sqrt(a2)
    cos_b = (a2 + c * c - b * b) / (2 * a * c)
    cos_g = (a2 + b * b - c * c) / (2 * a * b)
    beta, gama = math.degrees(math.acos(cos_b)), math.degrees(math.acos(cos_g))
    sin_a = math.sin(math.radians(alfa))
    return {
        "b2": b * b, "c2": c * c, "cos_alfa": cos_a, "dva_bc_cos": 2 * b * c * cos_a, "a2": a2, "a": a,
        "cos_beta": cos_b, "cos_gama": cos_g, "beta": beta, "gama": gama, "zbroj": alfa + beta + gama,
        "a_kontrola_b": b / math.sin(math.radians(beta)) * sin_a,
        "a_kontrola_c": c / math.sin(math.radians(gama)) * sin_a,
    }


def _generator_dvije_stranice(rng: random.Random, varijanta: int, korak: int) -> dict[str, float]:
    u: dict[str, float] = {}
    _postavi_kut(u, "alfa", korak * rng.randint(40 * 3600 // korak, 100 * 3600 // korak) / 3600)
    while True:
        b, c = _duljina(rng, 100, 250), _duljina(rng, 100, 250)
        if abs(b - c) >= 1:
            break
    # Varijante naizmjence daju b > c i b < c (predznak (β − γ)/2 u tangensovu poučku).
    if (b > c) != (varijanta % 2 == 0):
        b, c = c, b
    u["b"], u["c"] = b, c
    return u


_KUT_TOL_COS = 2.0
_KOSINUS = Zadatak(
    id="kosinus",
    naziv="Kosinusov poučak",
    list="Kosinusov poučak",
    obrazac="Trigonometrijski obrazac br. 14 – cos – Računanje trokuta iz dviju mjerenih duljina "
    "stranica i kuta između njih",
    ulazi=(
        *_dms_ulazi("alfa", "Mjereni kut α", 8, "C"),
        Ulaz("b", "G8", "Mjerena duljina b", 2),
        Ulaz("c", "G9", "Mjerena duljina c", 2),
    ),
    kutovi_ulaza=("alfa",),
    rezultati=(
        Rezultat("b2", "b²", ("J8",), tolerancija=0.001, decimale=4, formula="b²"),
        Rezultat("c2", "c²", ("J9",), tolerancija=0.001, decimale=4, formula="c²"),
        Rezultat("cos_alfa", "cos α", ("J10",), tolerancija=1e-7, decimale=9, formula="cos α"),
        Rezultat("dva_bc_cos", "2bc · cos α", ("J11",), tolerancija=0.01, decimale=5, formula="2 · b · c · cos α"),
        Rezultat("a2", "a²", ("J12",), tolerancija=0.01, decimale=5, formula="a² = b² + c² − 2bc · cos α"),
        Rezultat("a", "Stranica a", ("J13",), tolerancija=0.006, decimale=2, formula="a = √a²"),
        Rezultat("cos_beta", "cos β", ("J14",), tolerancija=2e-5, decimale=9, formula="cos β = (a² + c² − b²) / 2ac"),
        Rezultat("cos_gama", "cos γ", ("J15",), tolerancija=2e-5, decimale=9, formula="cos γ = (a² + b² − c²) / 2ab"),
        Rezultat("beta", "Kut β", _dms_adrese(9, "C"), Vrsta.KUT, _KUT_TOL_COS, formula="β = arccos(cos β)"),
        Rezultat("gama", "Kut γ", _dms_adrese(10, "C"), Vrsta.KUT, _KUT_TOL_COS, formula="γ = arccos(cos γ)"),
        Rezultat("zbroj", "Kontrola α + β + γ", _dms_adrese(11, "C"), Vrsta.KUT, _KUT_TOL_COS,
                 formula="α + β + γ = 180°"),
        Rezultat("a_kontrola_b", "Kontrola a = (b / sin β) · sin α", ("G13",), tolerancija=0.02,
                 formula="a = (b / sin β) · sin α"),
        Rezultat("a_kontrola_c", "Kontrola a = (c / sin γ) · sin α", ("G14",), tolerancija=0.02,
                 formula="a = (c / sin γ) · sin α"),
    ),
    izracun=_izracun_kosinus,
    generator=_generator_dvije_stranice,
)


# --- Tangensov poučak (obrazac 14 – tan) --------------------------------------
#
# Stupci: B oznaka | C predznak | D–F kut | G oznaka | H duljina | J oznaka | K vrijednost


def _izracun_tangens(u: dict[str, float]) -> dict[str, float]:
    alfa, b, c = _kut(u, "alfa"), u["b"], u["c"]
    pola = alfa / 2
    kot = 1 / math.tan(math.radians(pola))
    omjer = (b - c) / (b + c)
    razlika_pola = math.degrees(math.atan(omjer * kot))
    zbroj_pola = 90 - pola
    beta, gama = zbroj_pola + razlika_pola, zbroj_pola - razlika_pola
    a = math.sqrt(b * b + c * c - 2 * b * c * math.cos(math.radians(alfa)))
    return {
        "alfa_pola": pola, "cot_pola": kot, "b_minus_c": b - c, "b_plus_c": b + c, "omjer": omjer,
        "arctan": razlika_pola, "zbroj_pola": zbroj_pola, "razlika_pola": razlika_pola,
        "beta": beta, "gama": gama, "zbroj": alfa + beta + gama, "a": a,
        "a_kontrola": b / math.sin(math.radians(beta)) * math.sin(math.radians(alfa)),
    }


_TANGENS = Zadatak(
    id="tangens",
    naziv="Tangensov poučak",
    list="Tangensov poučak",
    obrazac="Trigonometrijski obrazac br. 14 – tan – Računanje trokuta iz dviju mjerenih duljina "
    "stranica i kuta između njih",
    ulazi=(
        *_dms_ulazi("alfa", "Mjereni kut α", 8, "D"),
        Ulaz("b", "H8", "Mjerena duljina b", 2),
        Ulaz("c", "H9", "Mjerena duljina c", 2),
    ),
    kutovi_ulaza=("alfa",),
    rezultati=(
        Rezultat("alfa_pola", "α / 2 (°, decimalno)", ("K8",), tolerancija=1e-6, decimale=8, formula="α / 2"),
        Rezultat("cot_pola", "B = cot(α / 2)", ("K9",), tolerancija=1e-6, decimale=9, formula="B = cot(α / 2)"),
        Rezultat("b_minus_c", "b − c", ("K10",), tolerancija=0.001, decimale=2, formula="b − c"),
        Rezultat("b_plus_c", "b + c", ("K11",), tolerancija=0.001, decimale=2, formula="b + c"),
        Rezultat("omjer", "A = (b − c) / (b + c)", ("K12",), tolerancija=1e-8, decimale=9,
                 formula="A = (b − c) / (b + c)"),
        Rezultat("arctan", "arctan(A · B) (°, decimalno)", ("K13",), tolerancija=3e-4, decimale=7,
                 formula="(β − γ)/2 = arctan(A · B), u stupnjevima"),
        Rezultat("zbroj_pola", "(β + γ) / 2", _dms_adrese(12, "D"), Vrsta.KUT, 1.0,
                 formula="(β + γ)/2 = 90° − α/2"),
        Rezultat("razlika_pola", "(β − γ) / 2", _dms_adrese(13, "D"), Vrsta.KUT, 1.0, predznak="C13",
                 formula="(β − γ)/2; predznak + ako je b > c, − ako je b < c"),
        Rezultat("beta", "Kut β", _dms_adrese(9, "D"), Vrsta.KUT, _KUT_TOL_COS,
                 formula="β = (β + γ)/2 + (β − γ)/2"),
        Rezultat("gama", "Kut γ", _dms_adrese(10, "D"), Vrsta.KUT, _KUT_TOL_COS,
                 formula="γ = (β + γ)/2 − (β − γ)/2"),
        Rezultat("zbroj", "Kontrola α + β + γ", _dms_adrese(11, "D"), Vrsta.KUT, _KUT_TOL_COS,
                 formula="α + β + γ = 180°"),
        Rezultat("a", "Stranica a", ("H10",), tolerancija=0.006, decimale=3, formula="a² = b² + c² − 2bc · cos α"),
        Rezultat("a_kontrola", "Kontrola a = (b / sin β) · sin α", ("H13",), tolerancija=0.02, decimale=3,
                 formula="a = (b / sin β) · sin α"),
    ),
    izracun=_izracun_tangens,
    generator=_generator_dvije_stranice,
)

ZADACI: dict[str, Zadatak] = {z.id: z for z in (_SINUS, _KOSINUS, _TANGENS)}


def osobni_podaci(zadatak: Zadatak, sjeme: int, jmbag: str, korak: int = 1) -> dict[str, float]:
    """Ulazni podaci studenta: isti za isto sjeme, zadatak i JMBAG (ne ovise o redoslijedu popisa).

    ``korak`` je točnost mjerenja kutova u sekundama (npr. 10: sekunde 0, 10, 20…)."""
    rng = random.Random(f"{sjeme}:{zadatak.id}:{jmbag}:{korak}")
    return zadatak.generator(rng, rng.randrange(4), korak)


def kontrolni_podaci(zadatak: Zadatak, korak: int = 1, broj: int = 4) -> list[dict[str, float]]:
    """Drugi skupovi ulaza na kojima se izvode formule studenta (uvijek isti, radi ponovljivosti)."""
    rng = random.Random(f"kontrola:{zadatak.id}:{korak}")
    return [zadatak.generator(rng, i, korak) for i in range(broj)]

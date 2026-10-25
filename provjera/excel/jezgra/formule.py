"""Parser i izračun Excel formula za trigonometrijske obrasce (AD-1: čisto, bez Excela).

Podržan je podskup Excela koji obrasci trebaju: aritmetika, usporedbe, ``&``,
reference i rasponi (i na drugi list), te funkcije iz ``FUNKCIJE``. Nepodržana
funkcija ili sintaksa baca ``Nepodrzano``; provjera tada ne može suditi o formuli,
ali i dalje uspoređuje vrijednost koju je Excel spremio.
"""

import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal

from provjera.excel.jezgra.xlsx import Celija, adresa, rastavi_adresu


class Nepodrzano(Exception):
    """Formula koristi nešto što ovaj izračun ne zna (funkciju, ime, sintaksu)."""


class ExcelGreska(Exception):
    """Greška kakvu bi i Excel prikazao u ćeliji (``#DIV/0!``, ``#VALUE!``, ``#NUM!``…)."""

    def __init__(self, kod: str):
        super().__init__(kod)
        self.kod = kod


# --- Leksička analiza ---------------------------------------------------------

_TOKENI = re.compile(
    r"""
    (?P<razmak>\s+)
  | (?P<tekst>"(?:[^"]|"")*")
  | (?P<greska>\#(?:DIV/0!|VALUE!|REF!|NAME\?|NUM!|N/A|NULL!))
  | (?P<ref>(?:(?:'(?:[^']|'')+'|[A-Za-z_][\w.]*)!)?\$?[A-Za-z]{1,3}\$?\d+(?![\w(]))
  | (?P<broj>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<funkcija>[A-Za-z_][\w.]*(?=\())
  | (?P<ime>[A-Za-z_][\w.]*)
  | (?P<op><>|<=|>=|[-+*/^&=<>%:(),;])
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Token:
    vrsta: str
    tekst: str


def tokeni(formula: str) -> list[Token]:
    rezultat, pozicija = [], 0
    while pozicija < len(formula):
        p = _TOKENI.match(formula, pozicija)
        if not p:
            raise Nepodrzano(f"neočekivan znak u formuli: {formula[pozicija:pozicija + 10]!r}")
        pozicija = p.end()
        vrsta = p.lastgroup or ""
        if vrsta != "razmak":
            rezultat.append(Token(vrsta, p.group()))
    return rezultat


# --- Sintaksno stablo ---------------------------------------------------------


@dataclass(frozen=True)
class Broj:
    vrijednost: float
    tekst: str


@dataclass(frozen=True)
class Tekst:
    vrijednost: str


@dataclass(frozen=True)
class Logicka:
    vrijednost: bool


@dataclass(frozen=True)
class Ref:
    list: str | None
    adresa: str  # bez $, velikim slovima


@dataclass(frozen=True)
class Raspon:
    od: Ref
    do: Ref


@dataclass(frozen=True)
class Unarno:
    op: str
    izraz: "Cvor"


@dataclass(frozen=True)
class Binarno:
    op: str
    lijevo: "Cvor"
    desno: "Cvor"


@dataclass(frozen=True)
class Postotak:
    izraz: "Cvor"


@dataclass(frozen=True)
class Poziv:
    ime: str
    argumenti: tuple["Cvor", ...]


@dataclass(frozen=True)
class GreskaLiteral:
    kod: str


Cvor = Broj | Tekst | Logicka | Ref | Raspon | Unarno | Binarno | Postotak | Poziv | GreskaLiteral

_PRIORITET = {
    "=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1,
    "&": 2,
    "+": 3, "-": 3,
    "*": 4, "/": 4,
    "^": 5,
}


def _ref(tekst: str) -> Ref:
    if "!" in tekst:
        list_, adr = tekst.rsplit("!", 1)
        if list_.startswith("'"):
            list_ = list_[1:-1].replace("''", "'")
    else:
        list_, adr = None, tekst
    return Ref(list_, adr.replace("$", "").upper())


class _Parser:
    def __init__(self, formula: str):
        self.tokeni = tokeni(formula)
        self.i = 0

    def _vidi(self) -> Token | None:
        return self.tokeni[self.i] if self.i < len(self.tokeni) else None

    def _uzmi(self) -> Token:
        t = self._vidi()
        if t is None:
            raise Nepodrzano("formula je prekratka")
        self.i += 1
        return t

    def _ocekuj(self, tekst: str) -> None:
        t = self._uzmi()
        if t.tekst != tekst:
            raise Nepodrzano(f"očekivano {tekst!r}, pronađeno {t.tekst!r}")

    def cijela(self) -> Cvor:
        cvor = self.izraz(0)
        if self._vidi() is not None:
            raise Nepodrzano(f"višak u formuli: {self._vidi().tekst!r}")
        return cvor

    def izraz(self, najmanji: int) -> Cvor:
        lijevo = self.unarni()
        while True:
            t = self._vidi()
            if t is None or t.vrsta != "op" or t.tekst not in _PRIORITET:
                return lijevo
            prioritet = _PRIORITET[t.tekst]
            if prioritet < najmanji:
                return lijevo
            self._uzmi()
            # ^ je u Excelu lijevo asocijativan, kao i ostali operatori.
            desno = self.izraz(prioritet + 1)
            lijevo = Binarno(t.tekst, lijevo, desno)

    def unarni(self) -> Cvor:
        t = self._vidi()
        if t is not None and t.vrsta == "op" and t.tekst in "+-":
            self._uzmi()
            # Unarni minus veže jače od ^: -2^2 = 4, kao u Excelu.
            izraz = self.unarni()
            return Unarno(t.tekst, izraz)
        return self.postfiks()

    def postfiks(self) -> Cvor:
        cvor = self.osnovni()
        while (t := self._vidi()) is not None and t.tekst == "%":
            self._uzmi()
            cvor = Postotak(cvor)
        return cvor

    def osnovni(self) -> Cvor:
        t = self._uzmi()
        if t.vrsta == "broj":
            return Broj(float(t.tekst), t.tekst)
        if t.vrsta == "tekst":
            return Tekst(t.tekst[1:-1].replace('""', '"'))
        if t.vrsta == "greska":
            return GreskaLiteral(t.tekst)
        if t.vrsta == "ref":
            od = _ref(t.tekst)
            if (s := self._vidi()) is not None and s.tekst == ":":
                self._uzmi()
                kraj = self._uzmi()
                if kraj.vrsta != "ref":
                    raise Nepodrzano("raspon mora završiti adresom ćelije")
                do = _ref(kraj.tekst)
                return Raspon(od, Ref(od.list, do.adresa))
            return od
        if t.vrsta == "ime":
            if t.tekst.upper() in ("TRUE", "FALSE"):
                return Logicka(t.tekst.upper() == "TRUE")
            raise Nepodrzano(f"imenovani raspon ili nepoznato ime: {t.tekst}")
        if t.vrsta == "funkcija":
            ime = t.tekst.upper()
            for prefiks in ("_XLFN._XLWS.", "_XLFN.", "_XLWS."):
                if ime.startswith(prefiks):
                    ime = ime[len(prefiks):]
            self._ocekuj("(")
            argumenti: list[Cvor] = []
            if (s := self._vidi()) is not None and s.tekst == ")":
                self._uzmi()
                return Poziv(ime, ())
            while True:
                argumenti.append(self.izraz(0))
                s = self._uzmi()
                if s.tekst == ")":
                    return Poziv(ime, tuple(argumenti))
                if s.tekst not in (",", ";"):
                    raise Nepodrzano(f"očekivan ',' ili ')', pronađeno {s.tekst!r}")
        if t.tekst == "(":
            cvor = self.izraz(0)
            self._ocekuj(")")
            return cvor
        raise Nepodrzano(f"neočekivan dio formule: {t.tekst!r}")


def parsiraj(formula: str) -> Cvor:
    """``formula`` je bez početnog ``=``."""
    return _Parser(formula.lstrip("=")).cijela()


def _cvorovi(cvor: Cvor) -> Iterator[Cvor]:
    yield cvor
    if isinstance(cvor, Unarno | Postotak):
        yield from _cvorovi(cvor.izraz)
    elif isinstance(cvor, Binarno):
        yield from _cvorovi(cvor.lijevo)
        yield from _cvorovi(cvor.desno)
    elif isinstance(cvor, Poziv):
        for a in cvor.argumenti:
            yield from _cvorovi(a)


def brojevi(cvor: Cvor) -> list[float]:
    """Brojčani literali upisani u formulu (za prepoznavanje prepisanih vrijednosti)."""
    return [c.vrijednost for c in _cvorovi(cvor) if isinstance(c, Broj)]


def funkcije(cvor: Cvor) -> set[str]:
    return {c.ime for c in _cvorovi(cvor) if isinstance(c, Poziv)}


def reference(cvor: Cvor) -> list[Ref | Raspon]:
    return [c for c in _cvorovi(cvor) if isinstance(c, Ref | Raspon)]


# --- Izračun ------------------------------------------------------------------

Vrijednost = float | str | bool | None


def _broj(v: Vrijednost) -> float:
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, float | int):
        return float(v)
    try:
        return float(v.replace(",", ".")) if v.strip() else 0.0
    except ValueError:
        raise ExcelGreska("#VALUE!") from None


def _konacan(x: float) -> float:
    if math.isnan(x) or math.isinf(x):
        raise ExcelGreska("#NUM!")
    return x


def _zaokruzi(x: float, mjesta: float, nacin: str) -> float:
    kvant = Decimal(1).scaleb(-int(mjesta))
    d = Decimal(repr(x))
    if nacin == ROUND_HALF_UP:
        return float(d.quantize(kvant, rounding=ROUND_HALF_UP))
    return float(d.quantize(kvant, rounding=nacin))


def _mod(x: float, y: float) -> float:
    if y == 0:
        raise ExcelGreska("#DIV/0!")
    return x - y * math.floor(x / y)


def _acot(x: float) -> float:
    return math.pi / 2 - math.atan(x)


def _cot(x: float) -> float:
    t = math.tan(x)
    if t == 0:
        raise ExcelGreska("#DIV/0!")
    return 1 / t


def _djeli(x: float, y: float) -> float:
    if y == 0:
        raise ExcelGreska("#DIV/0!")
    return x / y


def _sqrt(x: float) -> float:
    if x < 0:
        raise ExcelGreska("#NUM!")
    return math.sqrt(x)


def _domena(f: Callable[[float], float]) -> Callable[[float], float]:
    def omotac(x: float) -> float:
        try:
            return f(x)
        except ValueError:
            raise ExcelGreska("#NUM!") from None

    return omotac


def _ln(x: float) -> float:
    if x <= 0:
        raise ExcelGreska("#NUM!")
    return math.log(x)


# Funkcije jednog brojčanog argumenta.
_JEDNOARGUMENTNE: dict[str, Callable[[float], float]] = {
    "SIN": math.sin,
    "COS": math.cos,
    "TAN": math.tan,
    "COT": _cot,
    "ASIN": _domena(math.asin),
    "ACOS": _domena(math.acos),
    "ATAN": math.atan,
    "ACOT": _acot,
    "RADIANS": math.radians,
    "DEGREES": math.degrees,
    "SQRT": _sqrt,
    "ABS": abs,
    "INT": lambda x: float(math.floor(x)),
    "SIGN": lambda x: float((x > 0) - (x < 0)),
    "EXP": math.exp,
    "LN": _ln,
    "LOG10": lambda x: _ln(x) / math.log(10),
    "EVEN": lambda x: float(math.copysign(math.ceil(abs(x) / 2) * 2, x)),
}

FUNKCIJE = frozenset(
    set(_JEDNOARGUMENTNE)
    | {"PI", "POWER", "MOD", "QUOTIENT", "ROUND", "ROUNDUP", "ROUNDDOWN", "TRUNC",
       "ATAN2", "SUM", "SUMSQ", "PRODUCT", "MIN", "MAX", "AVERAGE", "IF", "AND", "OR",
       "NOT", "LOG", "VALUE", "UNICHAR", "CHAR", "CONCATENATE", "CONCAT", "UPPER", "LOWER", "LEN"}
)


class Racunalo:
    """Izračunava ćelije radne knjige iz njihovih formula.

    ``zamjene`` postavlja vrijednosti ulaznih ćelija (``(list, adresa)`` → broj); tako
    se formule studenta izvode i na drugim ulaznim podacima. Ćelija bez formule vraća
    spremljenu vrijednost.
    """

    def __init__(
        self,
        listovi: dict[str, dict[str, Celija]],
        glavni_list: str,
        zamjene: dict[tuple[str, str], float] | None = None,
    ):
        self.listovi = listovi
        self.glavni = glavni_list
        self.zamjene = zamjene or {}
        self._gotovo: dict[tuple[str, str], Vrijednost | ExcelGreska] = {}
        self._u_tijeku: set[tuple[str, str]] = set()
        self._stabla: dict[str, Cvor] = {}

    def stablo(self, formula: str) -> Cvor:
        if formula not in self._stabla:
            self._stabla[formula] = parsiraj(formula)
        return self._stabla[formula]

    def celija(self, adr: str, list_: str | None = None) -> Vrijednost:
        kljuc = (list_ or self.glavni, adr.upper())
        if kljuc in self.zamjene:
            return self.zamjene[kljuc]
        if kljuc in self._gotovo:
            rezultat = self._gotovo[kljuc]
            if isinstance(rezultat, ExcelGreska):
                raise rezultat
            return rezultat
        if kljuc[0] not in self.listovi:
            raise ExcelGreska("#REF!")
        celija = self.listovi[kljuc[0]].get(kljuc[1])
        if celija is None:
            return None
        if celija.formula is None:
            return celija.vrijednost
        if kljuc in self._u_tijeku:
            raise ExcelGreska("#CIRC!")
        self._u_tijeku.add(kljuc)
        try:
            rezultat = self._izracunaj(self.stablo(celija.formula), kljuc[0])
            if isinstance(rezultat, list):
                rezultat = rezultat[0] if rezultat else None
            self._gotovo[kljuc] = rezultat
            return rezultat
        except ExcelGreska as e:
            self._gotovo[kljuc] = e
            raise
        finally:
            self._u_tijeku.discard(kljuc)

    def _raspon(self, raspon: Raspon, list_: str) -> list[Vrijednost]:
        (r0, s0), (r1, s1) = rastavi_adresu(raspon.od.adresa), rastavi_adresu(raspon.do.adresa)
        cilj = raspon.od.list or list_
        return [
            self.celija(adresa(r, s), cilj)
            for r in range(min(r0, r1), max(r0, r1) + 1)
            for s in range(min(s0, s1), max(s0, s1) + 1)
        ]

    def _izracunaj(self, cvor: Cvor, list_: str) -> Vrijednost | list[Vrijednost]:
        if isinstance(cvor, Broj | Tekst | Logicka):
            return cvor.vrijednost
        if isinstance(cvor, GreskaLiteral):
            raise ExcelGreska(cvor.kod)
        if isinstance(cvor, Ref):
            return self.celija(cvor.adresa, cvor.list or list_)
        if isinstance(cvor, Raspon):
            return self._raspon(cvor, list_)
        if isinstance(cvor, Unarno):
            x = _broj(self._skalar(cvor.izraz, list_))
            return -x if cvor.op == "-" else x
        if isinstance(cvor, Postotak):
            return _broj(self._skalar(cvor.izraz, list_)) / 100
        if isinstance(cvor, Binarno):
            return self._binarno(cvor, list_)
        if isinstance(cvor, Poziv):
            return self._poziv(cvor, list_)
        raise Nepodrzano(f"nepoznat čvor: {cvor!r}")

    def _skalar(self, cvor: Cvor, list_: str) -> Vrijednost:
        v = self._izracunaj(cvor, list_)
        if isinstance(v, list):
            raise ExcelGreska("#VALUE!")
        return v

    def _binarno(self, cvor: Binarno, list_: str) -> Vrijednost:
        a = self._skalar(cvor.lijevo, list_)
        b = self._skalar(cvor.desno, list_)
        op = cvor.op
        if op == "&":
            return f"{_u_tekst(a)}{_u_tekst(b)}"
        if op in ("=", "<>", "<", ">", "<=", ">="):
            x, y = _usporedivo(a), _usporedivo(b)
            if type(x) is not type(y):
                # Excel: broj < tekst < logička; za obrasce dovoljno je da nisu jednaki.
                return op == "<>"
            return {
                "=": x == y, "<>": x != y, "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y,
            }[op]
        x, y = _broj(a), _broj(b)
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            return _djeli(x, y)
        if op == "^":
            try:
                return _konacan(math.pow(x, y))
            except (ValueError, OverflowError):
                raise ExcelGreska("#NUM!") from None
        raise Nepodrzano(f"operator {op}")

    def _ravno(self, argumenti: tuple[Cvor, ...], list_: str) -> list[float]:
        """Brojevi svih argumenata; tekst i prazne ćelije iz raspona se preskaču, kao u Excelu."""
        brojevi_: list[float] = []
        for a in argumenti:
            v = self._izracunaj(a, list_)
            if isinstance(v, list):
                brojevi_ += [float(x) for x in v if isinstance(x, float | int) and not isinstance(x, bool)]
            else:
                brojevi_.append(_broj(v))
        return brojevi_

    def _poziv(self, cvor: Poziv, list_: str) -> Vrijednost:
        ime, arg = cvor.ime, cvor.argumenti
        if ime not in FUNKCIJE:
            raise Nepodrzano(f"funkcija {ime}")

        def br(i: int) -> float:
            return _broj(self._skalar(arg[i], list_))

        def broj_argumenata(*dopusteno: int) -> None:
            if len(arg) not in dopusteno:
                raise ExcelGreska("#VALUE!")

        if ime in _JEDNOARGUMENTNE:
            broj_argumenata(1)
            try:
                return _konacan(_JEDNOARGUMENTNE[ime](br(0)))
            except OverflowError:
                raise ExcelGreska("#NUM!") from None
        if ime == "PI":
            broj_argumenata(0)
            return math.pi
        if ime == "POWER":
            broj_argumenata(2)
            try:
                return _konacan(math.pow(br(0), br(1)))
            except (ValueError, OverflowError):
                raise ExcelGreska("#NUM!") from None
        if ime == "MOD":
            broj_argumenata(2)
            return _mod(br(0), br(1))
        if ime == "QUOTIENT":
            broj_argumenata(2)
            return float(math.trunc(_djeli(br(0), br(1))))
        if ime in ("ROUND", "ROUNDUP", "ROUNDDOWN"):
            broj_argumenata(2)
            nacin = {"ROUND": ROUND_HALF_UP, "ROUNDUP": ROUND_UP, "ROUNDDOWN": ROUND_DOWN}[ime]
            return _zaokruzi(br(0), br(1), nacin)
        if ime == "TRUNC":
            broj_argumenata(1, 2)
            return _zaokruzi(br(0), br(1) if len(arg) == 2 else 0, ROUND_DOWN)
        if ime == "ATAN2":
            broj_argumenata(2)
            x, y = br(0), br(1)
            if x == 0 and y == 0:
                raise ExcelGreska("#DIV/0!")
            return math.atan2(y, x)  # Excel: ATAN2(x; y)
        if ime == "LOG":
            broj_argumenata(1, 2)
            baza = br(1) if len(arg) == 2 else 10.0
            return _ln(br(0)) / _ln(baza) if baza != 1 else _djeli(1, 0)
        if ime == "VALUE":
            broj_argumenata(1)
            return _broj(self._skalar(arg[0], list_))
        if ime in ("UNICHAR", "CHAR"):
            broj_argumenata(1)
            kod = int(br(0))
            if not 1 <= kod <= (0x10FFFF if ime == "UNICHAR" else 255):
                raise ExcelGreska("#VALUE!")
            return chr(kod) if ime == "UNICHAR" else bytes([kod]).decode("cp1252", errors="replace")
        if ime in ("CONCATENATE", "CONCAT"):
            return "".join(_u_tekst(self._skalar(a, list_)) for a in arg)
        if ime in ("UPPER", "LOWER", "LEN"):
            broj_argumenata(1)
            tekst = _u_tekst(self._skalar(arg[0], list_))
            return {"UPPER": tekst.upper(), "LOWER": tekst.lower(), "LEN": float(len(tekst))}[ime]
        if ime in ("SUM", "SUMSQ", "PRODUCT", "MIN", "MAX", "AVERAGE"):
            brojevi_ = self._ravno(arg, list_)
            if ime == "SUM":
                return math.fsum(brojevi_)
            if ime == "SUMSQ":
                return math.fsum(x * x for x in brojevi_)
            if ime == "PRODUCT":
                return math.prod(brojevi_) if brojevi_ else 0.0
            if ime == "AVERAGE":
                return _djeli(math.fsum(brojevi_), len(brojevi_))
            if not brojevi_:
                return 0.0
            return min(brojevi_) if ime == "MIN" else max(brojevi_)
        if ime == "IF":
            broj_argumenata(2, 3)
            if _broj(self._skalar(arg[0], list_)) != 0:
                return self._skalar(arg[1], list_)
            return self._skalar(arg[2], list_) if len(arg) == 3 else False
        if ime in ("AND", "OR"):
            istine = [x != 0 for x in self._ravno(arg, list_)]
            return all(istine) if ime == "AND" else any(istine)
        if ime == "NOT":
            broj_argumenata(1)
            return br(0) == 0
        raise Nepodrzano(f"funkcija {ime}")


def _u_tekst(v: Vrijednost) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _usporedivo(v: Vrijednost) -> float | str | bool:
    if v is None:
        return 0.0
    if isinstance(v, str):
        return v.casefold()
    return v

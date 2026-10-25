"""Jedinice (AD-6): jedino mjesto pretvorbi; duljine su cijeli twipsi, fontovi polutočke."""

import re
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum


class Jedinica(Enum):
    TWIPS = "twips"
    POLUTOCKE = "polutocke"
    TEKST = "tekst"
    BOOL = "bool"
    TOCKE = "tocke"  # twipsi prikazani u pt (razmaci odlomka)
    RETCI = "retci"  # prored u 240-inama retka (pravilo „auto“)
    PORAVNANJE = "poravnanje"  # vrijednost iz Poravnanje (npr. „obostrano“)


TWIPS_PO_CM = Decimal(1440) / Decimal("2.54")
TWIPS_PO_PT = 20
RETCI_PO_RETKU = 240

_BROJ = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*$")

_MJERA = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(cm|mm|pt)\s*$")


def _parsiraj(tekst: str) -> tuple[Decimal, str]:
    pogodak = _MJERA.match(tekst) if isinstance(tekst, str) else None
    if not pogodak:
        raise ValueError(
            f"neispravna mjera {tekst!r}; očekuje se npr. '3 cm', '25 mm' ili '12 pt'"
        )
    return Decimal(pogodak[1].replace(",", ".")), pogodak[2]


def _cijeli(iznos: Decimal) -> int:
    return int(iznos.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def parsiraj_duljinu(tekst: str) -> int:
    """„3 cm“, „25 mm“ ili „12 pt“ → twipsi (zaokruženo na najbliži cijeli broj)."""
    iznos, jedinica = _parsiraj(tekst)
    if jedinica == "cm":
        return _cijeli(iznos * TWIPS_PO_CM)
    if jedinica == "mm":
        return _cijeli(iznos / 10 * TWIPS_PO_CM)
    return _cijeli(iznos * 20)


def parsiraj_mm(tekst: str) -> int:
    """„3 cm“ ili „25 mm“ → cijeli milimetri; necijeli mm je greška."""
    iznos, jedinica = _parsiraj(tekst)
    if jedinica == "pt":
        raise ValueError(f"mjera {tekst!r} mora biti u cm ili mm")
    mm = iznos * 10 if jedinica == "cm" else iznos
    if mm != mm.to_integral_value():
        raise ValueError(f"mjera {tekst!r} mora biti cijeli broj milimetara")
    return int(mm)


def parsiraj_velicinu_fonta(tekst: str) -> int:
    """„12 pt“ → polutočke; dopuštene su samo cijele polutočke („10,5 pt“)."""
    iznos, jedinica = _parsiraj(tekst)
    if jedinica != "pt":
        raise ValueError(f"veličina fonta {tekst!r} mora biti u pt")
    polutocke = iznos * 2
    if polutocke != polutocke.to_integral_value():
        raise ValueError(f"veličina fonta {tekst!r} mora biti višekratnik 0,5 pt")
    return int(polutocke)


def parsiraj_retke(tekst: str) -> int:
    """Višestruki prored „1,15“ → 240-ine retka (276); jednostruki „1“ → 240."""
    pogodak = _BROJ.match(tekst) if isinstance(tekst, str) else None
    if not pogodak:
        raise ValueError(f"neispravan prored {tekst!r}; očekuje se broj redaka, npr. '1' ili '1,15'")
    iznos = _cijeli(Decimal(pogodak[1].replace(",", ".")) * RETCI_PO_RETKU)
    if iznos <= 0:
        raise ValueError(f"prored {tekst!r} mora biti veći od nule")
    return iznos


def mm_u_twips(mm: int) -> int:
    return _cijeli(Decimal(mm) / 10 * TWIPS_PO_CM)


def twips_u_cm(twips: int) -> Decimal:
    return Decimal(twips) / TWIPS_PO_CM


def twips_u_pt(twips: int) -> Decimal:
    return Decimal(twips) / TWIPS_PO_PT


def retci_u_broj(retci: int) -> Decimal:
    return Decimal(retci) / RETCI_PO_RETKU


def unutar_tolerancije(a: int, b: int, tol: int) -> bool:
    return abs(a - b) <= tol

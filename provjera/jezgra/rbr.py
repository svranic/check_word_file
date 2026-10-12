"""Parsiranje rednog broja (FR-9): jedini tumač studentskog unosa Rbr."""

import re
from dataclasses import dataclass

_RBR = re.compile(r"^0*([1-9][0-9]{0,8})\.?$")  # najviše 9 znamenki


@dataclass(frozen=True)
class GreskaUnosa:
    poruka_kljuc: str


PRAZNO = GreskaUnosa("rbr.prazno")
NEISPRAVNO = GreskaUnosa("rbr.neispravno")


def parsiraj(unos: str) -> int | GreskaUnosa:
    """„54“, „54.“ i „ 054“ → 54; prazno, 0, negativno, decimalno i tekst → ``GreskaUnosa``."""
    tekst = unos.strip()
    if not tekst:
        return PRAZNO
    pogodak = _RBR.match(tekst)
    if not pogodak:
        return NEISPRAVNO
    return int(pogodak[1])

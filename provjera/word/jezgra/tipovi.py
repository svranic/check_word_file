"""Pydantic tipovi mjera iz profila: tekst s jedinicom („3 cm“) → cijeli broj (AD-6)."""

from collections.abc import Callable
from typing import Annotated

from pydantic import BeforeValidator

from provjera.word.jezgra import jedinice


def _mjera(pretvorba: Callable[[str], int]) -> Callable[[object], int]:
    def validiraj(vrijednost: object) -> int:
        if not isinstance(vrijednost, str):
            raise ValueError("mjera mora biti tekst s jedinicom, npr. '3 cm'")
        return pretvorba(vrijednost)

    return validiraj


Duljina = Annotated[int, BeforeValidator(_mjera(jedinice.parsiraj_duljinu))]
"""Duljina u twipsima."""

DuljinaMm = Annotated[int, BeforeValidator(_mjera(jedinice.parsiraj_mm))]
"""Duljina u cijelim milimetrima (formula margina)."""

VelicinaFonta = Annotated[int, BeforeValidator(_mjera(jedinice.parsiraj_velicinu_fonta))]
"""Veličina fonta u polutočkama („12 pt“ → 24)."""

Retci = Annotated[int, BeforeValidator(_mjera(jedinice.parsiraj_retke))]
"""Višestruki prored u 240-inama retka („1“ → 240, „1,15“ → 276)."""

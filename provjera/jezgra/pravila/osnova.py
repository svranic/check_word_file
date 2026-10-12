"""Ugovor i registar pravila (AD-4).

Pravilo je funkcija ``(DocModel, KontekstProvjere, Postavke, Profil) -> list[Nalaz]``.
Četvrti parametar (profil, samo za čitanje) daje pristup zajedničkim odjeljcima
``[naziv_datoteke]``, ``[formula]`` i ``[tolerancije]``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from provjera.jezgra.nalaz import Nalaz


class PostavkeBaza(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ukljuceno: bool = True


FunkcijaPravila = Callable[[Any, Any, Any, Any], list[Nalaz]]


@dataclass(frozen=True)
class Pravilo:
    id: str
    funkcija: FunkcijaPravila
    postavke: type[PostavkeBaza]
    poruke: tuple[str, ...]


# Redoslijed registracije je redoslijed izvođenja i prikaza.
REGISTAR: dict[str, Pravilo] = {}


def registriraj(
    id: str, postavke: type[PostavkeBaza], poruke: tuple[str, ...]
) -> Callable[[FunkcijaPravila], FunkcijaPravila]:
    def dekorator(funkcija: FunkcijaPravila) -> FunkcijaPravila:
        if id in REGISTAR:
            raise ValueError(f"pravilo {id} je već registrirano")
        REGISTAR[id] = Pravilo(id, funkcija, postavke, poruke)
        return funkcija

    return dekorator

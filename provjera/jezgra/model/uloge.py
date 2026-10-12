"""Uloge (AD-13): jedino mjesto koje klasificira sekcije; pravila samo filtriraju po ulozi."""

from enum import Enum


class Uloga(Enum):
    NASLOVNICA = "NASLOVNICA"
    TIJELO = "TIJELO"


def uloge_sekcija(broj: int) -> tuple[Uloga, ...]:
    """Uz barem dvije sekcije prva je naslovnica; jedina sekcija je tijelo."""
    if broj >= 2:
        return (Uloga.NASLOVNICA,) + (Uloga.TIJELO,) * (broj - 1)
    return (Uloga.TIJELO,) * broj

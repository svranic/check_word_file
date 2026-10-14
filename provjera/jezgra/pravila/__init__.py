"""Pravila provjere i registar (AD-4). Uvoz modula pravila registrira ih redom."""

# isort: off — redoslijed uvoza je redoslijed izvođenja i prikaza pravila.
from provjera.jezgra.pravila import r_naziv  # noqa: F401
from provjera.jezgra.pravila import r_sekcije  # noqa: F401
from provjera.jezgra.pravila import r_margine  # noqa: F401
from provjera.jezgra.pravila import r_tekst  # noqa: F401
from provjera.jezgra.pravila import r_naslovi  # noqa: F401
from provjera.jezgra.pravila import r_sazetak  # noqa: F401
from provjera.jezgra.pravila import r_literatura  # noqa: F401
from provjera.jezgra.pravila import r_stilovi  # noqa: F401
# isort: on
from provjera.jezgra.pravila.osnova import REGISTAR, PostavkeBaza, Pravilo

__all__ = ["REGISTAR", "PostavkeBaza", "Pravilo"]

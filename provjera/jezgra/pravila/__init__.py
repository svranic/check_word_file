"""Pravila provjere i registar (AD-4). Uvoz modula pravila registrira ih redom."""

from provjera.jezgra.pravila import r_naziv  # noqa: F401
from provjera.jezgra.pravila.osnova import REGISTAR, PostavkeBaza, Pravilo

__all__ = ["REGISTAR", "PostavkeBaza", "Pravilo"]

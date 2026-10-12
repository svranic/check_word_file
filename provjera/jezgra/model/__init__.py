"""Parsiranje .docx u DocModel i dodjela uloga (AD-3, AD-13)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DocModel:
    """Nepromjenjivi model dokumenta; priča 1.5 dodaje sekcije."""


def procitaj(docx: bytes) -> DocModel:
    """Parsira dokument točno jednom; ``docx`` je već prošao ``ulaz.provjeri_ulaz``."""
    return DocModel()

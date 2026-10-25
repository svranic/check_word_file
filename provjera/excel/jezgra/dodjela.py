"""Koje zadatke (listove) rješava koji student, prema ``zadaci.raspodjela`` profila."""

import hashlib

from provjera.excel.jezgra.profil import ProfilExcel


def dodijeljeni(profil: ProfilExcel, jmbag: str | None, redni_broj: int | None = None) -> tuple[str, ...] | None:
    """Zadaci studenta; ``None`` ako se iz danih podataka ne mogu odrediti.

    ``redni_broj`` je položaj studenta u popisu (od 0) i potreban je samo za raspodjelu "redom".
    """
    vrste = profil.zadaci.vrste
    match profil.zadaci.raspodjela:
        case "svi":
            return vrste
        case "nasumicno" if jmbag:
            sazetak = hashlib.sha256(f"{profil.zadaci.sjeme}:{jmbag}".encode()).digest()
            return (vrste[int.from_bytes(sazetak[:8]) % len(vrste)],)
        case "redom" if redni_broj is not None:
            return (vrste[redni_broj % len(vrste)],)
    return None

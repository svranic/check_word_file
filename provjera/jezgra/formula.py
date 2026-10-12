"""Formula margina (FR-4, AD-7): jedini izvor individualnih margina za web, PDF i batch.

Svaka margina je osnovica + (znamenka − raspon/korak) · korak, gdje su znamenke
indeksa kombinacije ``k`` zapisanog u bazi ``v`` (broj vrijednosti po margini).
Permutacija ``k_i = (a·i + b) mod N`` izvedena iz sjemena jamči jedinstvenost;
Rbr. n dobiva n-tu dopuštenu kombinaciju.
"""

import hashlib
from dataclasses import dataclass, fields
from functools import lru_cache
from math import gcd

from provjera.jezgra import jedinice
from provjera.jezgra.profil import ParametriFormule, kanonski_json

# Svaka promjena algoritma podiže verziju i zahtijeva novi snapshot.
FORMULA_VERZIJA = 1


@dataclass(frozen=True)
class Margine:
    """Margine u cijelim milimetrima, redom kao u Wordovu dijalogu."""

    gore: int
    dolje: int
    lijevo: int
    desno: int

    def u_twips(self) -> dict[str, int]:
        return {
            polje.name: jedinice.mm_u_twips(getattr(self, polje.name))
            for polje in fields(self)
        }


def _osnovice(parametri: ParametriFormule) -> tuple[int, int, int, int]:
    return (
        parametri.osnovica_gore,
        parametri.osnovica_dolje,
        parametri.osnovica_lijevo,
        parametri.osnovica_desno,
    )


def _dopustena(margine: Margine, parametri: ParametriFormule) -> bool:
    vrijednosti = (margine.gore, margine.dolje, margine.lijevo, margine.desno)
    pomaknutih = sum(m != o for m, o in zip(vrijednosti, _osnovice(parametri)))
    jednaka_naslovnici = all(m == parametri.naslovnica for m in vrijednosti)
    return pomaknutih >= 2 and not jednaka_naslovnici


@lru_cache(maxsize=8)
def _dopustene(parametri: ParametriFormule) -> tuple[Margine, ...]:
    koraka = parametri.raspon // parametri.korak
    v = 2 * koraka + 1
    n = v**4
    sazetak = hashlib.sha256(str(parametri.sjeme).encode("utf-8")).hexdigest()
    a = int(sazetak[:8], 16) % n
    while a == 0 or gcd(a, n) != 1:
        a = (a + 1) % n
    b = int(sazetak[8:16], 16) % n

    rezultat = []
    for i in range(n):
        k = (a * i + b) % n
        pomaci = []
        for _ in range(4):
            k, znamenka = divmod(k, v)
            pomaci.append((znamenka - koraka) * parametri.korak)
        margine = Margine(*(o + p for o, p in zip(_osnovice(parametri), pomaci)))
        if _dopustena(margine, parametri):
            rezultat.append(margine)
    return tuple(rezultat)


def najveci_rbr(parametri: ParametriFormule) -> int:
    return len(_dopustene(parametri))


def margine(rbr: int, parametri: ParametriFormule) -> Margine:
    dopustene = _dopustene(parametri)
    if not 1 <= rbr <= len(dopustene):
        raise ValueError(f"Rbr. mora biti između 1 i {len(dopustene)}")
    return dopustene[rbr - 1]


def otisak(parametri: ParametriFormule) -> str:
    """Otisak parametara formule i ``FORMULA_VERZIJA`` (12 heksadecimalnih znakova)."""
    podaci = {
        "formula_verzija": FORMULA_VERZIJA,
        "parametri": parametri.model_dump(mode="json"),
    }
    return hashlib.sha256(kanonski_json(podaci)).hexdigest()[:12]

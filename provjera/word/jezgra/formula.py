"""Formula margina (FR-4, AD-7): jedini izvor margina tijela za web, PDF i batch.

Svaka margina je osnovica + (znamenka − raspon/korak) · korak, gdje su znamenke
indeksa kombinacije ``k`` zapisanog u bazi ``v`` (broj vrijednosti po margini).
Permutacija ``k_i = (a·i + b) mod N`` izvedena iz sjemena jamči jedinstvenost;
Rbr. n dobiva n-tu dopuštenu kombinaciju.

Uz ``fiksne_margine = true`` svi studenti dobivaju osnovice, a ``raspon``, ``korak`` i
``sjeme`` smiju izostati.
"""

import hashlib
import json
from dataclasses import dataclass, fields
from functools import lru_cache
from math import gcd

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictInt,
    model_serializer,
    model_validator,
)

from provjera.word.jezgra import jedinice
from provjera.word.jezgra.tipovi import DuljinaMm

# Gornja granica prostora formule margina (21⁴); štiti od preduge izgradnje tablice.
NAJVISE_KOMBINACIJA = 21**4


class ParametriFormule(BaseModel):
    """Odjeljak ``[formula]`` profila; sve duljine u cijelim milimetrima."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    osnovica_gore: DuljinaMm
    osnovica_dolje: DuljinaMm
    osnovica_lijevo: DuljinaMm
    osnovica_desno: DuljinaMm
    raspon: DuljinaMm | None = None
    korak: DuljinaMm | None = None
    naslovnica: DuljinaMm
    sjeme: StrictInt | None = Field(default=None, ge=0)
    # Iste margine tijela (osnovice) za sve studente; zadano su individualne.
    fiksne_margine: StrictBool = False

    @model_validator(mode="after")
    def _provjeri_odnose(self) -> "ParametriFormule":
        greske = []
        if self.fiksne_margine:
            najmanje = 0
        else:
            for polje in ("raspon", "korak", "sjeme"):
                if getattr(self, polje) is None:
                    greske.append(f"{polje} je obavezan kad margine nisu fiksne")
            if greske:
                raise ValueError("; ".join(greske))
            najmanje = self.raspon
            if self.korak <= 0:
                greske.append("korak mora biti veći od 0")
            elif self.raspon <= 0 or self.raspon % self.korak:
                greske.append("raspon mora biti pozitivan višekratnik koraka")
            elif (2 * (self.raspon // self.korak) + 1) ** 4 > NAJVISE_KOMBINACIJA:
                greske.append(f"raspon/korak daje više od {NAJVISE_KOMBINACIJA} kombinacija")
        for strana in ("gore", "dolje", "lijevo", "desno"):
            if getattr(self, f"osnovica_{strana}") - najmanje <= 0:
                greske.append(
                    f"osnovica_{strana} mora biti veća od raspona"
                    if not self.fiksne_margine
                    else f"osnovica_{strana} mora biti veća od 0"
                )
        if self.naslovnica <= 0:
            greske.append("naslovnica mora biti veća od 0")
        if greske:
            raise ValueError("; ".join(greske))
        return self

    @model_serializer(mode="wrap")
    def _bez_zadanih(self, handler: SerializerFunctionWrapHandler) -> dict:
        """Izostavlja ``fiksne_margine = false``, a ``raspon``/``korak``/``sjeme`` kad su
        prazni ili kad su margine fiksne (tada se ne koriste). Profil bez zastavice tako ima
        isti ``otisak`` i ``profil.verzija`` kao prije njezina uvođenja (AD-9)."""
        podaci = handler(self)
        if not self.fiksne_margine:
            podaci.pop("fiksne_margine", None)
        for polje in ("raspon", "korak", "sjeme"):
            if self.fiksne_margine or podaci.get(polje) is None:
                podaci.pop(polje, None)
        return podaci


def kanonski_json(podaci: object) -> bytes:
    return json.dumps(
        podaci, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


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


def najveci_rbr(parametri: ParametriFormule) -> int | None:
    """Najveći Rbr. s individualnim marginama; ``None`` uz fiksne margine (bez granice)."""
    if parametri.fiksne_margine:
        return None
    return len(_dopustene(parametri))


def margine(rbr: int | None, parametri: ParametriFormule) -> Margine:
    """Margine tijela za Rbr.; uz fiksne margine osnovice za svaki Rbr. i za ``None``."""
    if parametri.fiksne_margine:
        return Margine(*_osnovice(parametri))
    if rbr is None:
        raise ValueError("Rbr. je obavezan kad margine nisu fiksne")
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

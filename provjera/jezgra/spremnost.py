"""Pregled spremnosti vježbe (priča 3.3): profil i zamrznuti popis prije objave.

Čista funkcija bez I/O-a: aplikacija predaje Rbr. sa zamrznutog popisa, broj aktivnih
studenata te rezultat samoprovjere (priča 3.4), a problemi su ključevi poruka s parametrima (prijevod radi ``poruke``).
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from provjera.jezgra import formula
from provjera.jezgra import profil as profil_modul
from provjera.jezgra.profil import Profil
from provjera.jezgra.poruke import poruka
from provjera.jezgra.samoprovjera import (
    NemaSkupa,
    RezultatPrimjera,
    broj_odstupanja,
    ukupno,
)


@dataclass(frozen=True)
class Problem:
    """Razlog zašto vježba nije spremna: ključ poruke ``spremnost.*`` i parametri."""

    kljuc: str
    parametri: Mapping[str, str | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parametri", MappingProxyType(dict(self.parametri)))

    def __eq__(self, drugi: object) -> bool:
        if not isinstance(drugi, Problem):
            return NotImplemented
        return (self.kljuc, dict(self.parametri)) == (drugi.kljuc, dict(drugi.parametri))

    def __hash__(self) -> int:
        return hash((self.kljuc, tuple(sorted(self.parametri.items()))))


@dataclass(frozen=True)
class PregledSpremnosti:
    naziv: str
    verzija: str
    broj_aktivnih: int
    broj_ukljucenih_pravila: int
    margine_jedinstvene: bool | None  # None: nema zamrznutog popisa ili su margine fiksne
    problemi: tuple[Problem, ...]

    @property
    def spremno(self) -> bool:
        return not self.problemi


def _popis_rbrova(rbrovi: Sequence[int]) -> str:
    return ", ".join(str(r) for r in rbrovi)


def _individualne_margine(
    profil: Profil, rbrovi: Sequence[int], dupli: bool, problemi: list[Problem]
) -> bool | None:
    """Raspon formule i jedinstvenost individualnih margina; problemi idu u ``problemi``."""
    najveci = formula.najveci_rbr(profil.formula)
    jedinstveni = sorted(set(rbrovi))
    izvan = [r for r in jedinstveni if not 1 <= r <= najveci]
    if izvan:
        problemi.append(
            Problem(
                "spremnost.rbr_izvan_raspona",
                {"rbrovi": _popis_rbrova(izvan), "najveci": najveci},
            )
        )
    vidjene: dict[formula.Margine, int] = {}
    jedinstvene = True
    for rbr in jedinstveni:
        if not 1 <= rbr <= najveci:
            continue
        margine = formula.margine(rbr, profil.formula)
        if margine in vidjene:
            jedinstvene = False
            problemi.append(
                Problem("spremnost.iste_margine", {"prvi": vidjene[margine], "drugi": rbr})
            )
        else:
            vidjene[margine] = rbr
    if dupli:
        return False  # isti Rbr. dvaput znači iste margine
    if not vidjene:
        return None  # nijedan Rbr. nije provjeren
    return jedinstvene


def pregled(
    profil: Profil,
    rbrovi: Sequence[int] | None,
    broj_aktivnih: int,
    samoprovjera: Sequence[RezultatPrimjera] | NemaSkupa | None,
) -> PregledSpremnosti:
    """Računa spremnost; ``rbrovi`` je ``None`` kad zamrznutog popisa nema, a
    ``samoprovjera`` je ``None`` dok samoprovjera nije pokrenuta, a ``NemaSkupa`` kad
    referentni skup nedostaje ili je neispravan.

    Jedinstvenost margina provjerava se za sve Rbr. na popisu (i neaktivne);
    Rbr. izvan raspona formule preskaču se jer su već prijavljeni kao problem.
    Uz fiksne margine raspon i jedinstvenost se ne provjeravaju (``margine_jedinstvene``
    ostaje ``None``); dupli Rbr. i dalje je problem.
    """
    problemi: list[Problem] = []
    margine_jedinstvene: bool | None = None
    if rbrovi is None:
        problemi.append(Problem("spremnost.nema_popisa"))
    else:
        if broj_aktivnih <= 0:
            problemi.append(Problem("spremnost.nema_aktivnih"))
        dupli = sorted(r for r, broj in Counter(rbrovi).items() if broj > 1)
        if dupli:
            problemi.append(Problem("spremnost.dupli_rbr", {"rbrovi": _popis_rbrova(dupli)}))
        if not profil.formula.fiksne_margine:
            margine_jedinstvene = _individualne_margine(profil, rbrovi, bool(dupli), problemi)
    ukljucenih = sum(p.ukljuceno for p in profil.pravila.values())
    if not ukljucenih:
        problemi.append(Problem("spremnost.nema_pravila"))
    if samoprovjera is None:
        problemi.append(Problem("spremnost.samoprovjera_nije_pokrenuta"))
    elif isinstance(samoprovjera, NemaSkupa):
        razlog = poruka(samoprovjera.poruka_kljuc, **samoprovjera.parametri)
        problemi.append(Problem("spremnost.samoprovjera_nema_skupa", {"poruka": razlog}))
    elif not ukupno(samoprovjera):
        problemi.append(
            Problem("spremnost.samoprovjera_ne_prolazi", {"broj": broj_odstupanja(samoprovjera)})
        )
    return PregledSpremnosti(
        naziv=profil.vjezba.naziv,
        verzija=profil_modul.verzija(profil),
        broj_aktivnih=broj_aktivnih,
        broj_ukljucenih_pravila=ukljucenih,
        margine_jedinstvene=margine_jedinstvene,
        problemi=tuple(problemi),
    )

"""R-BROJ-STRANICE: polje broja stranice u podnožju svake sekcije tijela, naslovnica bez broja.

Primjenjuju se vrste podnožja koje Word stvarno prikazuje: u tijelu zadano, uz prvu
stranicu (``titlePg``) i parne stranice (``evenAndOddHeaders``); na naslovnici prva ako je
``titlePg``, inače zadano. Poravnanje i format broja se ne provjeravaju.
"""

import re
from typing import TYPE_CHECKING

from pydantic import ConfigDict, model_validator

from provjera.jezgra.model import DocModel, Podnozje, Sekcija, VrstaPodnozja
from provjera.jezgra.model.uloge import Uloga
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.jezgra.pravila.runovi import nalazi_runova_na
from provjera.jezgra.tipovi import VelicinaFonta

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-BROJ-STRANICE"

# Ključ nalaza kad podnožje vrste nema polje broja stranice (ni ručni broj).
_BEZ_BROJA = {
    VrstaPodnozja.ZADANO: "bez_broja",
    VrstaPodnozja.PRVA: "bez_broja_prva",
    VrstaPodnozja.PARNA: "bez_broja_parna",
}


class Postavke(PostavkeBaza):
    """Ciljne vrijednosti dolaze isključivo iz ``[pravila.R-BROJ-STRANICE]`` u profilu."""

    model_config = ConfigDict(validate_default=True)

    font: str | None = None
    velicina: VelicinaFonta | None = None

    @model_validator(mode="after")
    def _ciljevi_kad_je_ukljuceno(self) -> "Postavke":
        if self.ukljuceno:
            nedostaju = [ime for ime in _CILJEVI if getattr(self, ime) is None]
            if nedostaju:
                raise ValueError(f"nedostaju ciljne vrijednosti: {', '.join(nedostaju)}")
        return self


_CILJEVI = ("font", "velicina")


# Samostalni ručni broj: odlomak je samo broj (do 3 znamenke), uz crtice ili kratku riječ
# („2“, „- 2 -“, „Stranica 2“). Godina („Varaždin, 2025.“) i JMBAG nisu broj stranice.
_RUCNI_BROJ = re.compile(
    r"[\s\-–—]*(?:(?:stranica|str\.?|strana|page|p\.)\s*)?\d{1,3}\.?[\s\-–—]*",
    re.IGNORECASE,
)


def _ima_rucni_broj(podnozje: Podnozje) -> bool:
    # Broj je često odvojen tabulatorom od drugog teksta („Ana Horvat\t\t2“).
    return any(
        _RUCNI_BROJ.fullmatch(dio)
        for odlomak in podnozje.odlomci_izvan_polja
        for dio in (odlomak, *re.split(r"\t+", odlomak))
    )


def _vrste_tijela(sekcija: Sekcija, model: DocModel) -> list[VrstaPodnozja]:
    vrste = [VrstaPodnozja.ZADANO]
    if sekcija.prva_stranica:
        vrste.append(VrstaPodnozja.PRVA)
    if model.parna_neparna:
        vrste.append(VrstaPodnozja.PARNA)
    return vrste


def _lokacija(sekcija: Sekcija) -> Lokacija:
    return Lokacija(Dio.PODNOZJE, sekcija=sekcija.indeks)


def _tijelo(sekcija: Sekcija, model: DocModel, postavke: Postavke, provjereni: set[str]) -> list[Nalaz]:
    """``provjereni`` su dijelovi podnožja već prijavljeni u ranijoj sekciji (Poveži s prethodnim)."""
    nalazi, kljucevi, runovi = [], [], []
    for vrsta in _vrste_tijela(sekcija, model):
        podnozje: Podnozje = sekcija.podnozja.po_vrsti(vrsta)
        if podnozje.dio is not None:
            if podnozje.dio in provjereni:
                continue
            provjereni.add(podnozje.dio)
        if podnozje.polja_stranice:
            runovi += [run for polje in podnozje.polja_stranice for run in polje.runovi]
            continue
        kljuc = "rucni_broj" if _ima_rucni_broj(podnozje) else _BEZ_BROJA[vrsta]
        if kljuc not in kljucevi:
            kljucevi.append(kljuc)
    lokacija = _lokacija(sekcija)
    nalazi += [Nalaz(ID, Status.NE_PROLAZI, lokacija, f"{ID}.{k}") for k in kljucevi]
    nalazi += nalazi_runova_na(runovi, lokacija, ID, postavke.font, postavke.velicina, {})
    return nalazi


def _naslovnica(sekcija: Sekcija) -> list[Nalaz]:
    vrsta = VrstaPodnozja.PRVA if sekcija.prva_stranica else VrstaPodnozja.ZADANO
    podnozje = sekcija.podnozja.po_vrsti(vrsta)
    if podnozje.polja_stranice or _ima_rucni_broj(podnozje):
        return [Nalaz(ID, Status.NE_PROLAZI, _lokacija(sekcija), f"{ID}.naslovnica_ima_broj")]
    return []


@registriraj(
    ID,
    Postavke,
    poruke=(
        f"{ID}.prolazi",
        f"{ID}.bez_sekcija",
        f"{ID}.bez_broja",
        f"{ID}.bez_broja_prva",
        f"{ID}.bez_broja_parna",
        f"{ID}.rucni_broj",
        f"{ID}.naslovnica_ima_broj",
        f"{ID}.font",
        f"{ID}.font_tema",
        f"{ID}.font_nepoznat",
        f"{ID}.velicina",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    if not model.sekcije:
        return [Nalaz(ID, Status.NEPROVJERLJIVO, Lokacija(Dio.DOKUMENT), f"{ID}.bez_sekcija")]
    nalazi, provjereni = [], set()
    for sekcija in model.sekcije:
        if sekcija.uloga is Uloga.NASLOVNICA:
            nalazi += _naslovnica(sekcija)
        else:
            nalazi += _tijelo(sekcija, model, postavke, provjereni)
    return nalazi or [Nalaz(ID, Status.PROSLO, Lokacija(Dio.PODNOZJE), f"{ID}.prolazi")]

"""R-MARGINE (FR-18): margine naslovnice i tijela, A4 uspravno, bez guttera i zrcalnih margina."""

from typing import TYPE_CHECKING

from pydantic import ConfigDict

from provjera.jezgra import formula
from provjera.jezgra.jedinice import Jedinica, mm_u_twips, unutar_tolerancije
from provjera.jezgra.model import DocModel, Sekcija
from provjera.jezgra.model.uloge import Uloga
from provjera.jezgra.nalaz import Dio, KontekstProvjere, Lokacija, Nalaz, Status, Vrijednost
from provjera.jezgra.pravila.osnova import PostavkeBaza, registriraj
from provjera.jezgra.tipovi import Duljina

if TYPE_CHECKING:
    from provjera.jezgra.profil import Profil

ID = "R-MARGINE"
STRANE = ("gore", "dolje", "lijevo", "desno")


class Postavke(PostavkeBaza):
    model_config = ConfigDict(validate_default=True)

    sirina_stranice: Duljina = "21 cm"
    visina_stranice: Duljina = "29,7 cm"


def _twips(iznos: int) -> Vrijednost:
    return Vrijednost(iznos, Jedinica.TWIPS)


def _ocekivane(sekcija: Sekcija, kontekst: KontekstProvjere, profil: "Profil") -> dict[str, int]:
    if sekcija.uloga is Uloga.NASLOVNICA:
        return dict.fromkeys(STRANE, mm_u_twips(profil.formula.naslovnica))
    return formula.margine(kontekst.rbr, profil.formula).u_twips()


def _margine(sekcija: Sekcija, kontekst: KontekstProvjere, profil: "Profil") -> Nalaz:
    lokacija = Lokacija(Dio.DOKUMENT, sekcija=sekcija.indeks)
    pronadene = {s: getattr(sekcija, s) for s in STRANE}
    if None in pronadene.values():
        return Nalaz(ID, Status.NEPROVJERLJIVO, lokacija, "R-MARGINE.nedostaje",
                     parametri={"sekcija": sekcija.indeks})
    ocekivane = _ocekivane(sekcija, kontekst, profil)
    tolerancija = profil.tolerancije.margine
    ispravno = all(unutar_tolerancije(pronadene[s], ocekivane[s], tolerancija) for s in STRANE)
    if ispravno:
        return Nalaz(ID, Status.PROSLO, lokacija, "R-MARGINE.prolazi", parametri={"sekcija": sekcija.indeks})
    parametri = {"sekcija": sekcija.indeks, "tolerancija": _twips(tolerancija)}
    for s in STRANE:
        parametri[f"{s}_pronadeno"] = _twips(pronadene[s])
        parametri[f"{s}_ocekivano"] = _twips(ocekivane[s])
    return Nalaz(ID, Status.NE_PROLAZI, lokacija, "R-MARGINE.sekcija_odstupa", parametri=parametri)


def _stranica(sekcija: Sekcija, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    lokacija = Lokacija(Dio.DOKUMENT, sekcija=sekcija.indeks)
    parametri = {"sekcija": sekcija.indeks}
    nalazi = []
    if sekcija.sirina is None or sekcija.visina is None:
        nalazi.append(Nalaz(ID, Status.NEPROVJERLJIVO, lokacija, "R-MARGINE.nedostaje_stranica",
                            parametri=parametri))
    else:
        # Pejzažna A4 ima zamijenjene dimenzije; prijavljuje se kao pejzaž, ne kao kriva veličina.
        pronadene = sorted((sekcija.sirina, sekcija.visina))
        ocekivane = sorted((postavke.sirina_stranice, postavke.visina_stranice))
        tol = profil.tolerancije.stranica
        if not all(unutar_tolerancije(p, o, tol) for p, o in zip(pronadene, ocekivane)):
            nalazi.append(Nalaz(
                ID, Status.NE_PROLAZI, lokacija, "R-MARGINE.nije_a4",
                parametri={**parametri, "sirina": _twips(sekcija.sirina), "visina": _twips(sekcija.visina)},
            ))
    if sekcija.pejzazno:
        nalazi.append(Nalaz(ID, Status.NE_PROLAZI, lokacija, "R-MARGINE.pejzazno", parametri=parametri))
    if sekcija.gutter:
        nalazi.append(Nalaz(ID, Status.NE_PROLAZI, lokacija, "R-MARGINE.gutter",
                            pronadeno=_twips(sekcija.gutter), parametri=parametri))
    return nalazi


@registriraj(
    ID,
    Postavke,
    poruke=(
        "R-MARGINE.prolazi",
        "R-MARGINE.sekcija_odstupa",
        "R-MARGINE.nedostaje",
        "R-MARGINE.nedostaje_stranica",
        "R-MARGINE.bez_sekcija",
        "R-MARGINE.nije_a4",
        "R-MARGINE.pejzazno",
        "R-MARGINE.gutter",
        "R-MARGINE.zrcalne",
    ),
)
def provjeri(model: DocModel, kontekst: KontekstProvjere, postavke: Postavke, profil: "Profil") -> list[Nalaz]:
    if not model.sekcije:
        return [Nalaz(ID, Status.NEPROVJERLJIVO, Lokacija(Dio.DOKUMENT), "R-MARGINE.bez_sekcija")]
    nalazi = []
    for sekcija in model.sekcije:
        nalazi.append(_margine(sekcija, kontekst, profil))
        nalazi += _stranica(sekcija, postavke, profil)
    if model.zrcalne_margine:
        nalazi.append(Nalaz(ID, Status.NE_PROLAZI, Lokacija(Dio.DOKUMENT), "R-MARGINE.zrcalne"))
    return nalazi

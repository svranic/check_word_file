"""Lokalna nastavnička aplikacija: priprema vježbe i batch provjera (Epici 3 i 4)."""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from provjera.word.adapteri import batch, excel_izlaz
from provjera.word.adapteri.pdf_svojstva import izradi_pdf, spremi_pdf
from provjera.word.adapteri.popis import (
    ZONA,
    GreskaIzdanog,
    GreskaRetka,
    GreskaZamrznutog,
    PopisVecZamrznut,
    Razlike,
    Student,
    UcitaniPopis,
    primijeni,
    procitaj_izdano,
    procitaj_zamrznuti,
    putanja_izdanog,
    putanja_pdf,
    putanja_popisa,
    sljedeci_rbr,
    spremi,
    ucitaj_isvu,
    usporedi,
    zamrzni,
    zapisi_atomski,
    zapisi_izdano,
)
from provjera.word.adapteri.samoprovjera import GreskaReferentnog, otisak_skupa
from provjera.word.adapteri.samoprovjera import pokreni as pokreni_samoprovjeru
from provjera.word.jezgra import formula, profil, spremnost, zbirna
from provjera.word.jezgra.predaje import (
    RezultatBatcha,
    opis_kandidata,
    opis_nacina,
    opis_razloga,
    opis_statusa,
    opis_studenta,
)
from provjera.word.jezgra.poruke import poruka
from provjera.word.jezgra.samoprovjera import (
    NemaSkupa,
    RezultatPrimjera,
    StatusPrimjera,
    broj_odstupanja,
    ukupno,
)

log = logging.getLogger(__name__)

KORIJEN = Path(__file__).resolve().parents[1]
MAPA_PROFILA = KORIJEN / "profili" / "word"
MAPA_REFERENTNOG = KORIJEN / "tests" / "word" / "referentni"
ZADANA_MAPA = Path.home() / "ProvjeraWord"


def _normalizirano(putanja: Path) -> Path:
    """Apsolutna putanja usporediva na Windowsu (velika i mala slova, kose crte)."""
    return Path(os.path.normcase(str(putanja.expanduser().resolve())))


def unutar_repozitorija(mapa: Path) -> bool:
    return _normalizirano(mapa).is_relative_to(_normalizirano(KORIJEN))


def podatkovna_mapa() -> Path:
    """Prikazuje odabir podatkovne mape; zaustavlja stranicu ako mapa nije prihvatljiva."""
    unos = st.text_input(
        poruka("nastavnik.mapa"),
        value=str(ZADANA_MAPA),
        key="podatkovna_mapa",
        help=poruka("nastavnik.mapa_pomoc"),
    ).strip()
    if not unos:
        st.error(poruka("nastavnik.mapa_prazna"))
        st.stop()
    try:
        mapa = Path(unos).expanduser()
        if "\0" in unos or not mapa.is_absolute() or mapa.is_file():
            raise ValueError("podatkovna mapa mora biti apsolutna putanja mape")
        mapa = mapa.resolve()
        u_repozitoriju = unutar_repozitorija(mapa)
    except (OSError, RuntimeError, ValueError):
        st.error(poruka("nastavnik.mapa_neispravna"))
        st.stop()
    if u_repozitoriju:
        st.warning(poruka("nastavnik.mapa_u_repozitoriju"), icon="⚠️")
        st.stop()
    st.caption(poruka("nastavnik.mapa_odabrana", mapa=bez_markdowna(str(mapa))))
    return mapa


def _procitaj_profile() -> list[tuple[str, profil.Profil | profil.GreskaProfila]]:
    imenovani, necitljivi = [], []
    for datoteka in sorted(MAPA_PROFILA.glob("*.toml")):
        try:
            imenovani.append((datoteka.name, datoteka.read_bytes()))
        except OSError as greska:
            razlog = greska.strerror or type(greska).__name__
            necitljivi.append(
                (
                    datoteka.name,
                    profil.GreskaProfila((poruka("profil.necitljiv", razlog=razlog),)),
                )
            )
    return profil.ucitaj_sve(imenovani) + necitljivi


def odabir_vjezbe() -> profil.Profil:
    """Nudi sve profile; neispravan se prikazuje sa svim greškama i zaustavlja stranicu."""
    ucitani = _procitaj_profile()
    if not ucitani:
        st.error(poruka("nastavnik.nema_profila"))
        st.stop()
    # Ispravni prvi, da zadani odabir bude upotrebljiv.
    ucitani.sort(key=lambda par: isinstance(par[1], profil.GreskaProfila))
    po_datoteci = dict(ucitani)

    def naziv(ime: str) -> str:
        p = po_datoteci[ime]
        if isinstance(p, profil.GreskaProfila):
            return poruka("nastavnik.profil_neispravan", datoteka=ime)
        if p.vjezba.objavljeno:
            return p.vjezba.naziv
        return poruka("nastavnik.vjezba_neobjavljena", naziv=p.vjezba.naziv)

    ime = st.selectbox(
        poruka("nastavnik.vjezba"), list(po_datoteci), format_func=naziv, key="vjezba"
    )
    odabrani = po_datoteci[ime]
    if isinstance(odabrani, profil.GreskaProfila):
        st.error(
            poruka(
                "nastavnik.profil_greske",
                datoteka=bez_markdowna(ime),
                broj=len(odabrani.greske),
            ),
            icon="❌",
        )
        st.markdown("\n".join(f"- {bez_markdowna(g)}" for g in odabrani.greske))
        st.stop()
    return odabrani


def opis_greske(greska: GreskaRetka) -> str:
    tekst = poruka(greska.poruka_kljuc, **greska.parametri)
    if greska.redak is None:
        return tekst
    return poruka("popis.redak", redak=greska.redak, poruka=tekst)


def prikazi_popis(popis: UcitaniPopis) -> None:
    lijevo, desno = st.columns(2)
    lijevo.write(poruka("popis.broj_studenata", broj=len(popis.studenti)))
    desno.write(poruka("popis.broj_neaktivnih", broj=popis.broj_neaktivnih))
    if popis.moze_zamrznuti:
        st.success(poruka("nastavnik.popis_ispravan"), icon="✅")
    else:
        st.error(poruka("nastavnik.popis_neispravan", broj=len(popis.greske)), icon="❌")
        st.markdown("\n".join(f"- {opis_greske(g)}" for g in popis.greske))
    if popis.studenti:
        st.dataframe(
            [
                {
                    poruka("nastavnik.stupac_rbr"): s.rbr,
                    poruka("nastavnik.stupac_jmbag"): s.jmbag,
                    poruka("nastavnik.stupac_ime"): s.ime,
                    poruka("nastavnik.stupac_prezime"): s.prezime,
                    poruka("nastavnik.stupac_aktivan"): poruka(
                        "vrijednost.da" if s.aktivan else "vrijednost.ne"
                    ),
                }
                for s in popis.studenti
            ],
            hide_index=True,
        )


KLJUC_OBAVIJESTI = "popis_obavijest"


def _obavijesti(vrsta: str, tekst: str) -> None:
    """Poruka nakon akcije preživljava ponovno pokretanje skripte."""
    st.session_state[KLJUC_OBAVIJESTI] = (vrsta, tekst)


def prikazi_obavijest() -> None:
    obavijest = st.session_state.pop(KLJUC_OBAVIJESTI, None)
    if obavijest is None:
        return
    vrsta, tekst = obavijest
    if vrsta == "uspjeh":
        st.success(tekst, icon="✅")
    else:
        st.error(tekst, icon="❌")


def opis_greske_zamrznutog(greska: GreskaZamrznutog, putanja: Path) -> str:
    # Putanja se prikazuje kroz Markdown; ``\`` i ``_`` u Windows putanji ne smiju se izgubiti.
    putanja_tekst = bez_markdowna(str(putanja))
    if greska.poruka_kljuc == "popis.zamrznuti_zakljucan":
        return poruka("nastavnik.zamrznuti_zakljucan", putanja=putanja_tekst)
    tekst = poruka(greska.poruka_kljuc, **greska.parametri)
    if greska.redak is not None:
        tekst = poruka("popis.redak", redak=greska.redak, poruka=tekst)
    return poruka("nastavnik.zamrznuti_ostecen", putanja=putanja_tekst, poruka=tekst)


def bez_markdowna(tekst: str) -> str:
    """Imena studenata ne smiju se protumačiti kao Markdown (``*``, ``_``, ``[`` …)."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~$:<])", r"\\\1", tekst)


def _zamrzni(studenti: tuple[Student, ...], mapa_vjezbe: Path) -> None:
    try:
        zamrzni(studenti, mapa_vjezbe)
    except PopisVecZamrznut:
        _obavijesti("greska", poruka("nastavnik.vec_zamrznut"))
    except OSError:
        _obavijesti("greska", poruka("nastavnik.zapis_neuspio"))
    except ValueError:
        _obavijesti("greska", poruka("nastavnik.popis_neispravan_za_zapis"))
    else:
        _obavijesti("uspjeh", poruka("nastavnik.zamrznuto", broj=len(studenti)))


def _primijeni(
    izvoz: tuple[Student, ...], prikazani: tuple[Student, ...], putanja: Path
) -> None:
    """Primjenjuje samo razlike koje je nastavnik vidio (``prikazani`` je otisak popisa)."""
    try:
        zamrznuti = procitaj_zamrznuti(putanja)
        if zamrznuti != prikazani:
            _obavijesti("greska", poruka("nastavnik.popis_promijenjen"))
            return
        razlike = usporedi(zamrznuti, izvoz)
        if not razlike.ima_promjena:
            return  # nema što zapisati; ne tvrdi se da je išta primijenjeno
        spremi(primijeni(zamrznuti, razlike), putanja)
    except GreskaZamrznutog as greska:
        _obavijesti("greska", opis_greske_zamrznutog(greska, putanja))
    except OSError:
        _obavijesti("greska", poruka("nastavnik.zapis_neuspio"))
    except ValueError:
        _obavijesti("greska", poruka("nastavnik.popis_neispravan_za_zapis"))
    else:
        _obavijesti(
            "uspjeh",
            poruka(
                "nastavnik.primijenjeno",
                novi=len(razlike.novi),
                ispisani=len(razlike.ispisani),
                ponovno=len(razlike.ponovno_upisani),
            ),
        )


def zamrznuti_popis(putanja: Path) -> tuple[Student, ...] | None:
    """Prikazuje stanje zamrznutog popisa; oštećen popis zaustavlja stranicu."""
    st.subheader(poruka("nastavnik.zamrznuti_naslov"))
    prikazi_obavijest()
    if not putanja.exists():
        st.info(poruka("nastavnik.zamrznuti_nema"), icon="ℹ️")
        return None
    try:
        studenti = procitaj_zamrznuti(putanja)
    except GreskaZamrznutog as greska:
        st.error(opis_greske_zamrznutog(greska, putanja), icon="❌")
        st.stop()
    aktivnih = sum(s.aktivan for s in studenti)
    st.write(
        poruka(
            "nastavnik.zamrznuti_stanje",
            broj=len(studenti),
            aktivnih=aktivnih,
            neaktivnih=len(studenti) - aktivnih,
        )
    )
    st.caption(poruka("nastavnik.zamrznuti_ne_uredivati"))
    return studenti


def _popis_studenata(studenti: tuple[Student, ...]) -> str:
    return "\n".join(
        "- "
        + poruka(
            "nastavnik.razlike_student",
            rbr=s.rbr,
            ime=bez_markdowna(s.ime),
            prezime=bez_markdowna(s.prezime),
            jmbag=s.jmbag,
        )
        for s in studenti
    )


def prikazi_razlike(zamrznuti: tuple[Student, ...], razlike: Razlike) -> None:
    st.markdown(f"**{poruka('nastavnik.razlike_naslov')}**")
    if not razlike.ima_promjena and not razlike.promijenjeno_ime:
        st.success(poruka("nastavnik.razlike_nema"), icon="✅")
    elif not razlike.ima_promjena:
        st.info(poruka("nastavnik.razlike_nema_za_primjenu"), icon="ℹ️")
    if razlike.novi:
        prvi = sljedeci_rbr(zamrznuti)
        st.markdown(poruka("nastavnik.razlike_novi"))
        st.markdown(
            "\n".join(
                "- "
                + poruka(
                    "nastavnik.razlike_novi_student",
                    ime=bez_markdowna(s.ime),
                    prezime=bez_markdowna(s.prezime),
                    jmbag=s.jmbag,
                    rbr=prvi + i,
                )
                for i, s in enumerate(razlike.novi)
            )
        )
    if razlike.ispisani:
        st.markdown(poruka("nastavnik.razlike_ispisani"))
        st.markdown(_popis_studenata(razlike.ispisani))
    if razlike.ponovno_upisani:
        st.markdown(poruka("nastavnik.razlike_ponovno"))
        st.markdown(_popis_studenata(razlike.ponovno_upisani))
    if razlike.promijenjeno_ime:
        st.warning(poruka("nastavnik.razlike_imena"), icon="⚠️")
        st.markdown(
            "\n".join(
                "- "
                + poruka(
                    "nastavnik.razlike_ime",
                    rbr=p.zamrznuti.rbr,
                    staro=bez_markdowna(f"{p.zamrznuti.ime} {p.zamrznuti.prezime}"),
                    novo=bez_markdowna(f"{p.izvoz.ime} {p.izvoz.prezime}"),
                    jmbag=p.zamrznuti.jmbag,
                )
                for p in razlike.promijenjeno_ime
            )
        )


def akcije_popisa(
    popis: UcitaniPopis, zamrznuti: tuple[Student, ...] | None, mapa_vjezbe: Path
) -> None:
    """„Zamrzni popis“ dok popis ne postoji; inače razlike i „Primijeni promjene“."""
    if zamrznuti is None:
        if not popis.moze_zamrznuti:
            st.caption(poruka("nastavnik.zamrzni_onemoguceno"))
        st.button(
            poruka("nastavnik.zamrzni"),
            key="zamrzni",
            type="primary",
            disabled=not popis.moze_zamrznuti,
            help=poruka("nastavnik.zamrzni_pomoc"),
            on_click=_zamrzni,
            args=(popis.studenti, mapa_vjezbe),
        )
        return
    if not popis.moze_zamrznuti:
        st.warning(poruka("nastavnik.primijeni_onemoguceno"), icon="⚠️")
        return
    razlike = usporedi(zamrznuti, popis.studenti)
    prikazi_razlike(zamrznuti, razlike)
    st.button(
        poruka("nastavnik.primijeni"),
        key="primijeni",
        type="primary",
        disabled=not razlike.ima_promjena,
        on_click=_primijeni,
        args=(popis.studenti, zamrznuti, putanja_popisa(mapa_vjezbe)),
    )


# --- Samoprovjera (priča 3.4) -------------------------------------------------

KLJUC_SAMOPROVJERE = "samoprovjera_rezultati"

RezultatSamoprovjere = tuple[RezultatPrimjera, ...] | GreskaReferentnog


def kljuc_samoprovjere(odabrani: profil.Profil) -> tuple[str, str]:
    """Rezultat vrijedi samo za ovu verziju profila i ovaj sadržaj referentnog skupa."""
    return (profil.verzija(odabrani), otisak_skupa(odabrani.vjezba.id, MAPA_REFERENTNOG))


def _pokreni_samoprovjeru(odabrani: profil.Profil) -> None:
    # Otisak prije pokretanja: promjena skupa tijekom izvođenja poništava rezultat.
    kljuc = kljuc_samoprovjere(odabrani)
    with st.spinner(poruka("samoprovjera.u_tijeku")):
        try:
            rezultat: RezultatSamoprovjere = pokreni_samoprovjeru(odabrani, MAPA_REFERENTNOG)
        except GreskaReferentnog as greska:
            rezultat = greska
    # Po vježbi se čuva samo zadnji rezultat.
    spremljeni = st.session_state.setdefault(KLJUC_SAMOPROVJERE, {})
    spremljeni[odabrani.vjezba.id] = (kljuc, rezultat)


def rezultat_samoprovjere(odabrani: profil.Profil) -> RezultatSamoprovjere | None:
    """Zadnji rezultat ako se od tada nisu promijenili ni profil ni referentni skup."""
    spremljeno = st.session_state.get(KLJUC_SAMOPROVJERE, {}).get(odabrani.vjezba.id)
    if spremljeno is None or spremljeno[0] != kljuc_samoprovjere(odabrani):
        return None
    return spremljeno[1]


def _skup(pravila: frozenset[str] | None) -> str:
    if pravila is None:
        return poruka("samoprovjera.nista")
    return ", ".join(sorted(pravila)) or poruka("samoprovjera.nijedno")


_STATUS_PRIMJERA = {
    StatusPrimjera.PROLAZI: "samoprovjera.status_prolazi",
    StatusPrimjera.NE_PROLAZI: "samoprovjera.status_ne_prolazi",
    StatusPrimjera.PRESKOCENO: "samoprovjera.status_preskoceno",
}


def _status(rezultat: RezultatPrimjera) -> str:
    status = poruka(_STATUS_PRIMJERA[rezultat.status])
    if rezultat.razlog is None:
        return status
    return poruka(
        "samoprovjera.status_razlog",
        status=status,
        razlog=poruka(rezultat.razlog, **rezultat.parametri),
    )


def prikazi_samoprovjeru(
    odabrani: profil.Profil, rezultat: RezultatSamoprovjere | None
) -> None:
    st.subheader(poruka("samoprovjera.naslov"))
    st.caption(poruka("samoprovjera.opis"))
    st.button(
        poruka("samoprovjera.pokreni"),
        key="samoprovjera",
        on_click=_pokreni_samoprovjeru,
        args=(odabrani,),
    )
    if rezultat is None:
        return
    if isinstance(rezultat, GreskaReferentnog):
        st.error(poruka(rezultat.poruka_kljuc, **rezultat.parametri), icon="❌")
        return
    if ukupno(rezultat):
        st.success(poruka("samoprovjera.prolazi"), icon="✅")
    else:
        st.error(poruka("samoprovjera.ne_prolazi", broj=broj_odstupanja(rezultat)), icon="❌")
    st.dataframe(
        [
            {
                poruka("samoprovjera.stupac_primjer"): r.ime,
                poruka("samoprovjera.stupac_ocekivano"): _skup(r.ocekivano),
                poruka("samoprovjera.stupac_pronadeno"): _skup(r.pronadeno),
                poruka("samoprovjera.stupac_status"): _status(r),
            }
            for r in rezultat
        ],
        hide_index=True,
    )


def prikazi_spremnost(
    odabrani: profil.Profil,
    zamrznuti: tuple[Student, ...] | None,
    samoprovjera: RezultatSamoprovjere | None,
) -> spremnost.PregledSpremnosti:
    st.subheader(poruka("spremnost.naslov"))
    rbrovi = None if zamrznuti is None else [s.rbr for s in zamrznuti]
    aktivnih = 0 if zamrznuti is None else sum(s.aktivan for s in zamrznuti)
    rezultati = (
        NemaSkupa(samoprovjera.poruka_kljuc, samoprovjera.parametri)
        if isinstance(samoprovjera, GreskaReferentnog)
        else samoprovjera
    )
    rezultat = spremnost.pregled(odabrani, rbrovi, aktivnih, rezultati)
    if odabrani.formula.fiksne_margine:
        margine = poruka("spremnost.margine_fiksne")
    elif rezultat.margine_jedinstvene is None:
        margine = poruka("spremnost.margine_neprovjerene")
    elif rezultat.margine_jedinstvene:
        margine = "✅ " + poruka("spremnost.margine_jedinstvene")
    else:
        margine = "❌ " + poruka("spremnost.margine_nejedinstvene")
    st.markdown(
        "\n".join(
            f"- {redak}"
            for redak in (
                poruka(
                    "spremnost.profil",
                    naziv=bez_markdowna(rezultat.naziv),
                    verzija=rezultat.verzija,
                ),
                poruka("spremnost.aktivnih", broj=rezultat.broj_aktivnih),
                poruka(
                    "spremnost.pravila",
                    broj=rezultat.broj_ukljucenih_pravila,
                    ukupno=len(odabrani.pravila),
                ),
                margine,
            )
        )
    )
    if rezultat.spremno:
        st.success(poruka("spremnost.spremno"), icon="✅")
    else:
        st.warning(poruka("spremnost.nije_spremno", broj=len(rezultat.problemi)), icon="❌")
        st.markdown(
            "\n".join(f"- {poruka(p.kljuc, **p.parametri)}" for p in rezultat.problemi)
        )
    return rezultat


# --- PDF sa svojstvima (priča 3.5) ---------------------------------------------

KLJUC_PDF = "pdf_svojstva"
FORMAT_VREMENA = "%d.%m.%Y. %H:%M"


def _procitaj_ako_postoji(putanja: Path) -> bytes | None:
    return putanja.read_bytes() if putanja.exists() else None


def _vrati(putanja: Path, prije: bytes | None) -> bool:
    """Vraća datoteku na stanje prije generiranja; ``False`` ako ni to nije uspjelo."""
    try:
        if prije is None:
            putanja.unlink(missing_ok=True)
        else:
            zapisi_atomski(putanja, prije)
    except OSError:
        return False
    return True


def _neuspjelo(mapa_vjezbe: Path, kljuc: str = "nastavnik.pdf_zapis_neuspio") -> None:
    st.session_state.get(KLJUC_PDF, {}).pop(str(mapa_vjezbe), None)
    st.error(poruka(kljuc), icon="❌")


def _generiraj_pdf(
    odabrani: profil.Profil, zamrznuti: tuple[Student, ...], mapa_vjezbe: Path
) -> None:
    """Sprema PDF pa ``izdano.json``, oboje ili ništa; zapamćeni PDF vrijedi za ovaj profil,
    popis i podatkovnu mapu.

    PDF ide prvi: ako ni vraćanje ne uspije, stari ``izdano.json`` uz novi PDF daje samo
    upozorenje o razlici, a ne lažnu tvrdnju da je novi profil izdan.
    """
    putanja = putanja_pdf(mapa_vjezbe, odabrani.vjezba.id)
    izdano = putanja_izdanog(mapa_vjezbe)
    try:
        sadrzaj = izradi_pdf(odabrani, zamrznuti)
    except Exception:  # noqa: BLE001 — fpdf ili Rbr. izvan formule: poruka, ne traceback
        _neuspjelo(mapa_vjezbe, "nastavnik.pdf_izrada_neuspjela")
        return
    try:
        pdf_prije = _procitaj_ako_postoji(putanja)
        spremi_pdf(sadrzaj, putanja)
    except OSError:
        _neuspjelo(mapa_vjezbe)
        return
    try:
        zapisi_izdano(mapa_vjezbe, odabrani, datetime.now(ZONA))
    except OSError:
        if not _vrati(putanja, pdf_prije):
            st.error(poruka("nastavnik.pdf_vracanje_neuspjelo", putanja=bez_markdowna(str(putanja))), icon="❌")
        _neuspjelo(mapa_vjezbe)
        return
    spremljeni = st.session_state.setdefault(KLJUC_PDF, {})
    spremljeni[str(mapa_vjezbe)] = (profil.verzija(odabrani), zamrznuti, sadrzaj)
    st.success(
        poruka(
            "nastavnik.pdf_generirano",
            putanja=str(putanja),
            broj=sum(s.aktivan for s in zamrznuti),
        ),
        icon="✅",
    )


def prikazi_izdano(odabrani: profil.Profil, mapa_vjezbe: Path) -> None:
    """Kada je zadnji PDF izdan i odgovara li još trenutnom profilu."""
    try:
        izdano = procitaj_izdano(mapa_vjezbe)
    except GreskaIzdanog as greska:
        st.error(poruka(greska.poruka_kljuc), icon="❌")
        return
    if izdano is None:
        st.caption(poruka("nastavnik.pdf_nije_izdano"))
        return
    st.caption(
        poruka(
            "nastavnik.pdf_izdano",
            vrijeme=izdano.vrijeme.strftime(FORMAT_VREMENA),
            verzija=izdano.profil_verzija,
        )
    )
    if (izdano.formula_otisak, izdano.profil_verzija) != (
        formula.otisak(odabrani.formula),
        profil.verzija(odabrani),
    ):
        st.warning(poruka("nastavnik.pdf_izdano_razlika"), icon="⚠️")


def prikazi_pdf(
    odabrani: profil.Profil,
    zamrznuti: tuple[Student, ...] | None,
    pregled: spremnost.PregledSpremnosti,
    mapa_vjezbe: Path,
) -> None:
    st.subheader(poruka("nastavnik.pdf_naslov"))
    st.caption(poruka("nastavnik.pdf_opis"))
    st.caption(poruka("nastavnik.pdf_poveznica"))
    st.code(odabrani.vjezba.poveznica, language=None)
    spremno = pregled.spremno and zamrznuti is not None
    if not spremno:
        st.caption(poruka("nastavnik.pdf_onemoguceno"))
    if st.button(
        poruka("nastavnik.pdf_generiraj"),
        key="generiraj_pdf",
        type="primary",
        disabled=not spremno,
        help=None if spremno else poruka("nastavnik.pdf_onemoguceno"),
    ) and spremno:
        _generiraj_pdf(odabrani, zamrznuti, mapa_vjezbe)
    prikazi_izdano(odabrani, mapa_vjezbe)
    if not spremno:
        return
    spremljeno = st.session_state.get(KLJUC_PDF, {}).get(str(mapa_vjezbe))
    if spremljeno is None or spremljeno[:2] != (profil.verzija(odabrani), zamrznuti):
        return
    st.download_button(
        poruka("nastavnik.pdf_preuzmi"),
        data=spremljeno[2],
        file_name=putanja_pdf(mapa_vjezbe, odabrani.vjezba.id).name,
        mime="application/pdf",
        key="preuzmi_pdf",
        on_click="ignore",
    )


# --- Batch provjera (priča 4.1) -------------------------------------------------

KLJUC_BATCH = "batch_rezultat"


def mapa_predaja(podaci: Path) -> Path | None:
    """Unos mape predaja; ``None`` (uz poruku) dok mapa nije upotrebljiva."""
    unos = st.text_input(
        poruka("batch.mapa"), key="mapa_predaja", help=poruka("batch.mapa_pomoc")
    ).strip()
    if not unos:
        st.caption(poruka("batch.mapa_prazna"))
        return None
    try:
        mapa = Path(unos).expanduser()
        if "\0" in unos or not mapa.is_absolute() or not mapa.is_dir():
            raise ValueError("mapa predaja mora biti apsolutna putanja postojeće mape")
        mapa = mapa.resolve()
    except (OSError, RuntimeError, ValueError):
        st.error(poruka("batch.mapa_neispravna"), icon="❌")
        return None
    if batch.unutar(mapa, podaci):
        st.error(poruka("batch.mapa_u_podacima"), icon="❌")
        return None
    return mapa


def _kljuc_batcha(
    odabrani: profil.Profil, zamrznuti: tuple[Student, ...] | None, mapa: Path | None
) -> tuple:
    """Rezultat vrijedi samo za ovu vježbu, verziju profila, zamrznuti popis i mapu predaja."""
    return (odabrani.vjezba.id, profil.verzija(odabrani), zamrznuti, mapa)


def _spremi_tablicu(
    odabrani: profil.Profil, rezultat: RezultatBatcha, mapa_vjezbe: Path, vrijeme: datetime
) -> tuple[str, str]:
    """(vrsta, poruka): zbirna tablica se sprema odmah nakon provjere, bez prepisivanja.

    Nijedna greška ne smije izgubiti rezultat provjere niti prikazati traceback.
    """
    try:
        tablica = zbirna.izradi(rezultat, odabrani, vrijeme.strftime(FORMAT_VREMENA))
        putanja = excel_izlaz.spremi(
            excel_izlaz.izradi(tablica), mapa_vjezbe, odabrani.vjezba.id, vrijeme
        )
    except Exception as greska:  # noqa: BLE001 — prikazuje se kao poruka, ne traceback
        log.warning("zbirna tablica nije spremljena (%s)", type(greska).__name__)
        razlog = getattr(greska, "strerror", None) or type(greska).__name__
        return "greska", poruka("batch.tablica_nije_spremljena", razlog=razlog)
    return "uspjeh", poruka("batch.tablica_spremljena", putanja=str(putanja))


def _pokreni_batch(
    odabrani: profil.Profil,
    zamrznuti: tuple[Student, ...],
    mapa: Path,
    podaci: Path,
    mapa_vjezbe: Path,
) -> None:
    vrijeme = datetime.now(ZONA)  # vrijeme provjere, ne spremanja
    traka = st.progress(0.0)

    def napredak(obradeno: int, ukupno: int) -> None:
        traka.progress(
            obradeno / ukupno,
            text=poruka("batch.u_tijeku", obradeno=obradeno, ukupno=ukupno),
        )

    try:
        rezultat = batch.pokreni(mapa, odabrani, zamrznuti, napredak, izuzeto=podaci)
    except OSError as greska:
        st.session_state.pop(KLJUC_BATCH, None)  # stari rezultat više ne vrijedi
        st.error(
            poruka("batch.mapa_necitljiva", razlog=greska.strerror or type(greska).__name__),
            icon="❌",
        )
        return
    finally:
        traka.empty()
    spremanje = _spremi_tablicu(odabrani, rezultat, mapa_vjezbe, vrijeme)
    kljuc = _kljuc_batcha(odabrani, zamrznuti, mapa)
    st.session_state[KLJUC_BATCH] = (kljuc, rezultat, spremanje)


def zadnji_batch(
    odabrani: profil.Profil, zamrznuti: tuple[Student, ...] | None, mapa: Path | None
) -> tuple[RezultatBatcha, tuple[str, str]] | None:
    """Zadnji rezultat i ishod spremanja zbirne tablice, ako vrijede za ovaj odabir."""
    spremljeno = st.session_state.get(KLJUC_BATCH)
    if spremljeno is None or spremljeno[0] != _kljuc_batcha(odabrani, zamrznuti, mapa):
        return None
    return spremljeno[1], spremljeno[2]


def prikazi_rezultat_batcha(rezultat: RezultatBatcha, spremanje: tuple[str, str]) -> None:
    vrsta, tekst = spremanje
    if vrsta == "uspjeh":
        st.success(tekst, icon="✅")
    else:
        st.error(tekst, icon="❌")
    if not rezultat.datoteke:
        st.info(poruka("batch.nema_datoteka"), icon="ℹ️")
        return
    st.success(poruka("batch.gotovo", broj=len(rezultat.datoteke)), icon="✅")
    st.dataframe(
        [
            {
                poruka("batch.stupac_datoteka"): d.relativno,
                poruka("batch.stupac_student"): "" if d.student is None else opis_studenta(d.student),
                poruka("batch.stupac_nacin"): opis_nacina(d),
                poruka("batch.stupac_status"): "" if d.status is None else opis_statusa(d.status),
                poruka("batch.stupac_razlog"): opis_razloga(d) or "",
                poruka("batch.stupac_kandidati"): opis_kandidata(d),
            }
            for d in rezultat.datoteke
        ],
        hide_index=True,
    )


def prikazi_batch(
    odabrani: profil.Profil,
    zamrznuti: tuple[Student, ...] | None,
    podaci: Path,
    mapa_vjezbe: Path,
) -> None:
    st.subheader(poruka("batch.naslov"))
    st.caption(poruka("batch.opis"))
    problemi = batch.problemi_konfiguracije(odabrani, zamrznuti)
    if problemi:
        st.caption(poruka("batch.nije_moguce", broj=len(problemi)))
        st.markdown("\n".join(f"- {poruka(p.kljuc, **p.parametri)}" for p in problemi))
        return
    mapa = mapa_predaja(podaci)
    otisak = batch.stanje_otiska(odabrani, mapa_vjezbe)
    potvrdeno = True
    # Upozorenje tek uz odabranu mapu, kad je nastavnik spreman pokrenuti provjeru.
    if mapa is not None and otisak is not batch.StanjeOtiska.ISTI:
        st.warning(poruka(f"batch.otisak_{otisak.value}"), icon="⚠️")
        # Potvrda vrijedi samo za ovo upozorenje, profil i mapu; promjena traži novu.
        potvrdeno = st.checkbox(
            poruka("batch.potvrda_otiska"),
            key=f"potvrda_otiska_{otisak.value}_{profil.verzija(odabrani)}_{mapa}",
        )
    moze = mapa is not None and potvrdeno
    if st.button(
        poruka("batch.pokreni"), key="pokreni_batch", type="primary", disabled=not moze
    ) and moze:
        _pokreni_batch(odabrani, zamrznuti, mapa, podaci, mapa_vjezbe)
    zadnji = zadnji_batch(odabrani, zamrznuti, mapa)
    if zadnji is not None:
        prikazi_rezultat_batcha(*zadnji)


st.set_page_config(page_title=poruka("nastavnik.naslov"), page_icon="📋")

st.title(poruka("nastavnik.naslov"))

mapa = podatkovna_mapa()
vjezba = odabir_vjezbe()
mapa_vjezbe = mapa / vjezba.vjezba.id
zamrznuti = zamrznuti_popis(putanja_popisa(mapa_vjezbe))
samoprovjera = rezultat_samoprovjere(vjezba)
pregled_spremnosti = prikazi_spremnost(vjezba, zamrznuti, samoprovjera)
prikazi_samoprovjeru(vjezba, samoprovjera)
prikazi_pdf(vjezba, zamrznuti, pregled_spremnosti, mapa_vjezbe)
prikazi_batch(vjezba, zamrznuti, mapa, mapa_vjezbe)

st.subheader(poruka("nastavnik.popis_naslov"))
datoteka = st.file_uploader(poruka("nastavnik.ucitaj_popis"), type=["xlsx"], key="isvu")
if datoteka is not None:
    popis = ucitaj_isvu(datoteka.getvalue())
    prikazi_popis(popis)
    akcije_popisa(popis, zamrznuti, mapa_vjezbe)

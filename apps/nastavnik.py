"""Lokalna nastavnička aplikacija: priprema vježbe i batch provjera (Epici 3 i 4)."""

import os
import re
from pathlib import Path

import streamlit as st

from provjera.adapteri.popis import (
    GreskaRetka,
    GreskaZamrznutog,
    PopisVecZamrznut,
    Razlike,
    Student,
    UcitaniPopis,
    primijeni,
    procitaj_zamrznuti,
    putanja_popisa,
    sljedeci_rbr,
    spremi,
    ucitaj_isvu,
    usporedi,
    zamrzni,
)
from provjera.jezgra import profil
from provjera.jezgra.poruke import poruka

KORIJEN = Path(__file__).resolve().parents[1]
MAPA_PROFILA = KORIJEN / "profili"
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
    st.caption(poruka("nastavnik.mapa_odabrana", mapa=str(mapa)))
    return mapa


def odabir_vjezbe() -> profil.Profil:
    profili, neispravnih = profil.svi(
        datoteka.read_bytes() for datoteka in sorted(MAPA_PROFILA.glob("*.toml"))
    )
    if neispravnih:
        st.warning(poruka("nastavnik.neispravni_profili", broj=neispravnih), icon="⚠️")
    if not profili:
        st.error(poruka("nastavnik.nema_profila"))
        st.stop()
    po_id = {p.vjezba.id: p for p in profili}

    def naziv(id_vjezbe: str) -> str:
        p = po_id[id_vjezbe]
        if p.vjezba.objavljeno:
            return p.vjezba.naziv
        return poruka("nastavnik.vjezba_neobjavljena", naziv=p.vjezba.naziv)

    id_vjezbe = st.selectbox(
        poruka("nastavnik.vjezba"), list(po_id), format_func=naziv, key="vjezba"
    )
    return po_id[id_vjezbe]


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
    tekst = poruka(greska.poruka_kljuc, **greska.parametri)
    if greska.redak is not None:
        tekst = poruka("popis.redak", redak=greska.redak, poruka=tekst)
    return poruka("nastavnik.zamrznuti_ostecen", putanja=str(putanja), poruka=tekst)


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


st.set_page_config(page_title=poruka("nastavnik.naslov"), page_icon="📋")

st.title(poruka("nastavnik.naslov"))

mapa = podatkovna_mapa()
vjezba = odabir_vjezbe()
mapa_vjezbe = mapa / vjezba.vjezba.id
zamrznuti = zamrznuti_popis(putanja_popisa(mapa_vjezbe))

st.subheader(poruka("nastavnik.popis_naslov"))
datoteka = st.file_uploader(poruka("nastavnik.ucitaj_popis"), type=["xlsx"], key="isvu")
if datoteka is not None:
    popis = ucitaj_isvu(datoteka.getvalue())
    prikazi_popis(popis)
    akcije_popisa(popis, zamrznuti, mapa_vjezbe)

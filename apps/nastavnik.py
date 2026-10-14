"""Lokalna nastavnička aplikacija: priprema vježbe i batch provjera (Epici 3 i 4)."""

import os
from pathlib import Path

import streamlit as st

from provjera.adapteri.popis import GreskaRetka, UcitaniPopis, ucitaj_isvu
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


st.set_page_config(page_title=poruka("nastavnik.naslov"), page_icon="📋")

st.title(poruka("nastavnik.naslov"))

podatkovna_mapa()
odabir_vjezbe()

st.subheader(poruka("nastavnik.popis_naslov"))
datoteka = st.file_uploader(poruka("nastavnik.ucitaj_popis"), type=["xlsx"], key="isvu")
if datoteka is not None:
    prikazi_popis(ucitaj_isvu(datoteka.getvalue()))

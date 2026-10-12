"""Studentska web provjera (Streamlit Community Cloud). Smije uvoziti samo jezgru (AD-2)."""

from pathlib import Path

import streamlit as st

from provjera.jezgra import formula, profil, rbr
from provjera.jezgra.jedinice import Jedinica, mm_u_twips
from provjera.jezgra.poruke import formatiraj, poruka

MAPA_PROFILA = Path(__file__).resolve().parents[1] / "profili"
# Stanje vezano uz jednu provjeru; briše se pri promjeni Rbr. ili vježbe (FR-9).
KLJUCEVI_PROVJERE = ("izvjestaj", "datoteka")


def ocisti_provjeru() -> None:
    for kljuc in KLJUCEVI_PROVJERE:
        st.session_state.pop(kljuc, None)


def potvrdi_rbr() -> None:
    rezultat = rbr.parsiraj(st.session_state.get("rbr_unos", ""))
    novi = rezultat if isinstance(rezultat, int) else None
    if novi != st.session_state.get("rbr"):
        ocisti_provjeru()
    st.session_state["rbr"] = novi
    st.session_state["rbr_greska"] = (
        rezultat.poruka_kljuc if isinstance(rezultat, rbr.GreskaUnosa) else None
    )


def prikazi_margine(odabrani: profil.Profil, broj: int) -> None:
    margine = formula.margine(broj, odabrani.formula).u_twips()
    st.subheader(poruka("margine.naslov"))
    for stupac, strana in zip(st.columns(4), ("gore", "dolje", "lijevo", "desno")):
        stupac.metric(poruka(f"margine.{strana}"), formatiraj(margine[strana], Jedinica.TWIPS))
    st.write(poruka("margine.uputa"))
    naslovnica = mm_u_twips(odabrani.formula.naslovnica)
    st.caption(
        poruka("margine.naslovnica", naslovnica=formatiraj(naslovnica, Jedinica.TWIPS))
    )
    st.caption(poruka("margine.usporedi"))
    st.write(poruka("naziv.obrazac", obrazac=odabrani.naziv_datoteke.obrazac))


st.set_page_config(page_title=poruka("app.naslov"), page_icon="📄")

st.title(poruka("app.naslov"))
st.write(poruka("app.podnaslov"))
st.info(poruka("privatnost.obrada"), icon="🔒")

profili, neispravnih = profil.objavljeni(
    datoteka.read_bytes() for datoteka in sorted(MAPA_PROFILA.glob("*.toml"))
)
if not profili:
    st.warning(poruka("profil.nedostupno"))
    st.stop()
if neispravnih:
    st.warning(poruka("profil.djelomicno_nedostupno"))

po_id = {p.vjezba.id: p for p in profili}
id_vjezbe = st.selectbox(
    poruka("vjezba.odabir"),
    list(po_id),
    format_func=lambda i: po_id[i].vjezba.naziv,
    key="vjezba",
    on_change=ocisti_provjeru,
)
odabrani = po_id[id_vjezbe]

with st.form("rbr_obrazac"):
    st.text_input(poruka("rbr.oznaka"), key="rbr_unos", placeholder=poruka("rbr.primjer"))
    st.form_submit_button(poruka("rbr.potvrdi"), on_click=potvrdi_rbr)

broj = st.session_state.get("rbr")
if st.session_state.get("rbr_greska"):
    st.error(poruka(st.session_state["rbr_greska"]))
elif broj is not None:
    najveci = formula.najveci_rbr(odabrani.formula)
    if broj > najveci:
        st.error(poruka("rbr.prevelik", rbr=broj, najveci=najveci))
    else:
        prikazi_margine(odabrani, broj)

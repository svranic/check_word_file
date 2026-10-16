"""Studentska web provjera (Streamlit Community Cloud). Smije uvoziti samo jezgru (AD-2)."""

from pathlib import Path

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from provjera.jezgra import formula, profil, rbr, ulaz
from provjera.jezgra.jedinice import Jedinica, mm_u_twips
from provjera.jezgra.nalaz import Izvjestaj, KontekstProvjere, Nalaz, Status
from provjera.jezgra.poruke import (
    formatiraj,
    opis_izvora,
    opis_lokacije,
    poruka,
    tekst_nalaza,
)
from provjera.jezgra.provjera import NAJVISE_PRIMJERA, provjeri, spremnost
from provjera.jezgra.sazetak import html_sazetka

MAPA_PROFILA = Path(__file__).resolve().parents[1] / "profili"
# Stanje vezano uz jednu provjeru; briše se pri promjeni Rbr. ili vježbe (FR-9).
KLJUCEVI_PROVJERE = ("izvjestaj", "greska_provjere", "vrijeme_provjere")
VREMENSKA_ZONA = ZoneInfo("Europe/Zagreb")
# FR-11: redoslijed grupa nalaza u izvještaju.
REDOSLIJED_GRUPA = (Status.NE_PROLAZI, Status.NEPROVJERLJIVO, Status.PROSLO)
VELICINA_PO_RAZLOGU = {
    ulaz.RazlogOdbijanja.PREVELIKA: ulaz.NAJVECA_VELICINA_MB,
    ulaz.RazlogOdbijanja.ZIP_BOMBA: ulaz.NAJVECA_RASPAKIRANA_MB,
}


def novo_polje_za_ucitavanje() -> None:
    """Novi ključ polja: Streamlit odbacuje prethodno učitanu datoteku (AD-10)."""
    st.session_state["polje_ucitavanja"] = st.session_state.get("polje_ucitavanja", 0) + 1


def ocisti_provjeru() -> None:
    for kljuc in KLJUCEVI_PROVJERE:
        st.session_state.pop(kljuc, None)
    novo_polje_za_ucitavanje()


def potvrdi_rbr() -> None:
    rezultat = rbr.parsiraj(st.session_state.get("rbr_unos", ""))
    novi = rezultat if isinstance(rezultat, int) else None
    if novi != st.session_state.get("rbr"):
        ocisti_provjeru()
    st.session_state["rbr"] = novi
    st.session_state["rbr_greska"] = (
        rezultat.poruka_kljuc if isinstance(rezultat, rbr.GreskaUnosa) else None
    )


def prikazi_margine(odabrani: profil.Profil, broj: int | None) -> None:
    """Margine tijela za Rbr.; uz fiksne margine (``broj`` je ``None``) iste za sve."""
    fiksne = odabrani.formula.fiksne_margine
    margine = formula.margine(broj, odabrani.formula).u_twips()
    st.subheader(poruka("margine.naslov_fiksne" if fiksne else "margine.naslov"))
    for stupac, strana in zip(st.columns(4), ("gore", "dolje", "lijevo", "desno")):
        stupac.metric(poruka(f"margine.{strana}"), formatiraj(margine[strana], Jedinica.TWIPS))
    st.write(poruka("margine.uputa"))
    naslovnica = mm_u_twips(odabrani.formula.naslovnica)
    st.caption(
        poruka("margine.naslovnica", naslovnica=formatiraj(naslovnica, Jedinica.TWIPS))
    )
    if not fiksne:
        st.caption(poruka("margine.usporedi"))
    st.write(poruka("naziv.obrazac", obrazac=odabrani.naziv_datoteke.obrazac))


def bez_markdowna(tekst: str) -> str:
    """Nazivi datoteka sadrže ``_`` i slične znakove koje Markdown ne smije protumačiti."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~$:])", r"\\\1", tekst)


def ucitaj_dokument(odabrani: profil.Profil, broj: int | None) -> None:
    datoteka = st.file_uploader(
        poruka("ulaz.oznaka"),
        key=f"datoteka_{st.session_state.get('polje_ucitavanja', 0)}",
        # Malo iznad granice jezgre, da veću datoteku odbije jezgra s našom porukom.
        max_upload_size=ulaz.NAJVECA_VELICINA_MB + 1,
    )
    if datoteka is not None:
        for kljuc in KLJUCEVI_PROVJERE:
            st.session_state.pop(kljuc, None)
        kontekst = KontekstProvjere(datoteka.name, broj, None, None)
        try:
            st.session_state["izvjestaj"] = provjeri(datoteka.getvalue(), odabrani, kontekst)
            # Vrijeme dodaje stranica (adapter); jezgra ne čita sat.
            st.session_state["vrijeme_provjere"] = datetime.now(VREMENSKA_ZONA).strftime(
                "%d.%m.%Y. %H:%M"
            )
        except MemoryError:
            st.session_state["greska_provjere"] = "izvjestaj.preopterecenje"
        except Exception:  # noqa: BLE001 — student nikad ne vidi traceback
            st.session_state["greska_provjere"] = "izvjestaj.greska"
        novo_polje_za_ucitavanje()
        st.rerun()

    if st.session_state.get("greska_provjere"):
        st.error(poruka(st.session_state["greska_provjere"]), icon="❌")
    elif st.session_state.get("izvjestaj") is not None:
        try:
            prikazi_izvjestaj(st.session_state["izvjestaj"])
        except Exception:  # noqa: BLE001 — student nikad ne vidi traceback
            st.error(poruka("izvjestaj.greska"), icon="❌")
        else:
            try:
                ponudi_sazetak(st.session_state["izvjestaj"], odabrani)
            except Exception as greska:  # noqa: BLE001 — bez sažetka izvještaj i dalje vrijedi
                # Samo tip greške: nikad naziv datoteke ni sadržaj (AD-10).
                logging.getLogger(__name__).warning("sažetak nije izrađen (%s)", type(greska).__name__)


def prikazi_nalaz(nalaz: Nalaz) -> None:
    with st.container(border=True):
        st.markdown(
            f"**{poruka(f'status.{nalaz.status.value}')}** · "
            f"{poruka(f'pravilo.{nalaz.pravilo_id}')} · {bez_markdowna(opis_lokacije(nalaz.lokacija))}"
        )
        st.markdown(bez_markdowna(tekst_nalaza(nalaz)))
        if nalaz.status is not Status.PROSLO:
            for kljuc, vrijednost in (("izvjestaj.ocekivano", nalaz.ocekivano), ("izvjestaj.pronadeno", nalaz.pronadeno)):
                if vrijednost is not None:
                    st.caption(bez_markdowna(poruka(kljuc, vrijednost=formatiraj(vrijednost.iznos, vrijednost.jedinica))))
        if nalaz.pojave > 1:
            st.caption(poruka("izvjestaj.pojave", pojave=nalaz.pojave))
            # Jedna lokacija već je u zaglavlju nalaza; „…“ znači da pojava ima više od primjera.
            lokacije = list(dict.fromkeys(nalaz.primjeri))
            if len(lokacije) >= 2:
                primjeri = "; ".join(opis_lokacije(lokacija) for lokacija in lokacije)
                # Skrivenih lokacija može biti samo kad je popis primjera pun.
                if len(lokacije) >= NAJVISE_PRIMJERA and nalaz.pojave > len(lokacije):
                    primjeri += "; …"
                st.caption(bez_markdowna(poruka("izvjestaj.primjeri", primjeri=primjeri)))
        if nalaz.izvor is not None:
            with st.expander(poruka("izvjestaj.tehnicki_detalji")):
                st.write(bez_markdowna(poruka("izvjestaj.izvor", izvor=opis_izvora(nalaz.izvor))))


def ponudi_sazetak(izvjestaj: Izvjestaj, odabrani: profil.Profil) -> None:
    if izvjestaj.odbijeno is not None:
        return
    vrijeme = st.session_state.get("vrijeme_provjere", "–")
    st.download_button(
        poruka("sazetak.preuzmi"),
        data=html_sazetka(izvjestaj, odabrani.vjezba.naziv, vrijeme).encode("utf-8"),
        file_name=(
            poruka("sazetak.datoteka_bez_rbr")
            if izvjestaj.rbr is None
            else poruka("sazetak.datoteka", rbr=izvjestaj.rbr)
        ),
        mime="text/html",
    )


def prikazi_izvjestaj(izvjestaj: Izvjestaj) -> None:
    if izvjestaj.odbijeno is not None:
        razlog = izvjestaj.odbijeno
        st.error(poruka(f"ulaz.{razlog}", mb=VELICINA_PO_RAZLOGU.get(razlog, 0)), icon="❌")
        return
    if spremnost(izvjestaj):
        st.success(poruka("izvjestaj.spremno"), icon="✅")
    else:
        st.error(poruka("izvjestaj.nije_spremno"), icon="❌")
    for status in REDOSLIJED_GRUPA:
        grupa = [n for n in izvjestaj.nalazi if n.status is status]
        if grupa:
            st.subheader(poruka(f"izvjestaj.grupa.{status.value}"))
            for nalaz in grupa:
                prikazi_nalaz(nalaz)
    st.caption(poruka("izvjestaj.verzija_profila", verzija=izvjestaj.profil_verzija))


st.set_page_config(page_title=poruka("app.naslov"), page_icon="📄")

st.title(poruka("app.naslov"))
st.write(poruka("app.podnaslov"))
st.info(poruka("privatnost.obrada"), icon="🔒")

def _procitaj_profil(datoteka: Path) -> bytes:
    """Nečitljiva datoteka profila broji se kao neispravan profil, ne ruši stranicu."""
    try:
        return datoteka.read_bytes()
    except OSError:
        return b""


profili, neispravnih = profil.objavljeni(
    _procitaj_profil(datoteka) for datoteka in sorted(MAPA_PROFILA.glob("*.toml"))
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

if odabrani.formula.fiksne_margine:
    # Iste margine za sve studente: Rbr. nije potreban, odmah se nudi učitavanje.
    prikazi_margine(odabrani, None)
    ucitaj_dokument(odabrani, None)
    st.stop()

with st.form("rbr_obrazac"):
    st.text_input(poruka("rbr.oznaka"), key="rbr_unos", placeholder=poruka("rbr.primjer"))
    st.form_submit_button(poruka("rbr.potvrdi"), on_click=potvrdi_rbr)

broj = st.session_state.get("rbr")
if st.session_state.get("rbr_greska"):
    st.error(poruka(st.session_state["rbr_greska"]), icon="❌")
elif broj is not None:
    najveci = formula.najveci_rbr(odabrani.formula)
    if broj > najveci:
        st.error(poruka("rbr.prevelik", rbr=broj, najveci=najveci), icon="❌")
    else:
        prikazi_margine(odabrani, broj)
        ucitaj_dokument(odabrani, broj)

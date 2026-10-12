"""Lokalna nastavnička aplikacija: priprema vježbe i batch provjera (Epici 3 i 4)."""

import streamlit as st

from provjera.jezgra.poruke import poruka

st.set_page_config(page_title=poruka("nastavnik.naslov"), page_icon="📋")

st.title(poruka("nastavnik.naslov"))

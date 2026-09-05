"""
Debito Pubblico Intelligence · Dashboard Streamlit
Lo stock, gli spread, le scadenze e la storia del debito italiano.
"""

import streamlit as st
from lab_connectors.branding import apply_branding

st.set_page_config(
    page_title="Debito Pubblico · Dashboard",
    page_icon="🇮🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_branding(
    repo_name="debito-pubblico-intelligence",
    repo_url="https://github.com/dataciviclab/debito-pubblico-intelligence",
)

pages = {
    "": [
        st.Page("pages/01_Panoramica.py", title="Panoramica", icon="📊", default=True),
    ],
    "Analisi": [
        st.Page("pages/02_Spread.py", title="Spread BTP-Bund", icon="📈"),
        st.Page("pages/03_Composizione.py", title="Composizione", icon="🧩"),
        st.Page("pages/04_Scadenze.py", title="Scadenze", icon="⏰"),
        st.Page("pages/05_Trend_Storico.py", title="Trend Storico", icon="📜"),
        st.Page("pages/06_FPI.py", title="Flussi Banca d'Italia", icon="🏦"),
    ],
    "Strumenti": [
        st.Page("pages/07_SQL.py", title="Query SQL", icon="🧪"),
    ],
}

pg = st.navigation(pages, position="sidebar")

st.sidebar.caption("Fonti: MEF OCPI · Eurostat · Banca d'Italia · MEF Tesoro")

pg.run()

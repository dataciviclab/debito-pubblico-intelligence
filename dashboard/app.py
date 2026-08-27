#!/usr/bin/env python3
"""
Debito Pubblico Intelligence · Dashboard Streamlit
Lo stock, gli spread, le scadenze e la storia del debito italiano.
"""

import streamlit as st

st.set_page_config(
    page_title="Debito Pubblico · Dashboard",
    page_icon="🇮🇹",
    layout="wide",
    initial_sidebar_state="expanded",
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

st.sidebar.markdown("---")
st.sidebar.caption("Fonti: MEF OCPI · Eurostat · Banca d'Italia · MEF Tesoro")
st.sidebar.caption("Codice: [dataciviclab/debito-pubblico-intelligence](https://github.com/dataciviclab/debito-pubblico-intelligence)")
st.sidebar.caption("[DataCivicLab](https://dataciviclab.org/) · CC BY 4.0")

pg.run()

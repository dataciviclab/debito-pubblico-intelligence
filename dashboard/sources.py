"""Data sources for the Debito Pubblico Intelligence dashboard."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from lab_connectors.duckdb.queries import query_clean
from lab_connectors.registry import load_registry

PREFIX = "debito_pubblico_intelligence/"
_registry = load_registry(Path(__file__).parent.parent / "registry" / "registry.json")


def _q(slug: str, sql: str, year: int = 2026):
    return query_clean(slug, sql, [year], prefix=PREFIX)


@st.cache_data(ttl=3600, show_spinner=False)
def query_ocpi(sql: str, year: int = 2026):
    return _q("ocpi_serie_storiche", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_debito_pil(sql: str, year: int = 2026):
    return _q("eurostat_debito_pil", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_rendimento(sql: str, year: int = 2026):
    return _q("eurostat_rendimento_10y", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_composizione(sql: str, year: int = 2026):
    return _q("mef_composizione", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_scadenze(year: int = 2026):
    return _q("mef_scadenze_isin", "SELECT * FROM clean_input", year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_scadenze(sql: str, year: int = 2026):
    return _q("mef_scadenze_isin", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_fpi(sql: str, year: int = 2026):
    return _q("fpi_debito_pa", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_vita_media(sql: str, year: int = 2026):
    return _q("mef_vita_media", sql, year)

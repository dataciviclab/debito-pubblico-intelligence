"""Data sources for the Debito Pubblico Intelligence dashboard.

Due livelli, deliberatamente distinti:
- `load_mart()` legge i **mart** (contratto pubblico, risolto da lab-connectors):
  è quello che usano le pagine che mostrano numeri già calcolati — KPI,
  rollover, composizione. Così la dashboard non ricalcola la logica dei mart.
- `query_*()` legge il **clean**: serve solo alle pagine esplorative (serie
  lunghe, filtri liberi, SQL), dove la granularità grezza è la fonte giusta.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from lab_connectors.duckdb.queries import load_mart_table, query_clean
from lab_connectors.registry import load_registry

PREFIX = "debito_pubblico_intelligence/"
_registry = load_registry(Path(__file__).parent.parent / "registry" / "registry.json")


def _q(slug: str, sql: str, year: int = 2026):
    return query_clean(slug, sql, [year], prefix=PREFIX)


@st.cache_data(ttl=300, show_spinner=False)
def load_mart(slug: str, table: str, year: int = 2026):
    """Legge un mart pubblicato. Il path contract vive in lab-connectors.

    Se il mart non è ancora pubblicato (primo merge, compose non ancora girato)
    restituisce un DataFrame vuoto invece di propagare il 404: ogni pagina ha
    già la sua guardia sull'empty e mostra un messaggio, non uno stack trace.
    TTL corto (5 min) così la pagina si accende da sola appena il mart compare.
    """
    try:
        return load_mart_table(slug, table, year, prefix=PREFIX, registry=_registry)
    except Exception as exc:
        print(f"[sources] mart non disponibile: {slug}/{table} — {str(exc)[:120]}")
        return pd.DataFrame()


# ── Mart (contratto) ─────────────────────────────────────────────


@st.cache_data(ttl=3600, show_spinner=False)
def load_scadenze(year: int = 2026):
    return load_mart("mef_scadenze_isin", "mart_scadenze_isin", year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_rollover(year: int = 2026):
    return load_mart("mef_scadenze_isin", "mart_rollover_12m", year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_composizione(year: int = 2026):
    return load_mart("mef_composizione", "mart_composizione", year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_serie_storiche(year: int = 2026):
    return load_mart("ocpi_serie_storiche", "mart_serie_storiche", year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_detentori(year: int = 2026):
    return load_mart("fpi_debito_pa", "mart_detentori", year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_debt_service(table: str, year: int = 2026):
    """Mart del compose debt_service: mart_interessi_annui | mart_debt_service_12m."""
    return load_mart("debt_service", table, year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_rendimento_10y(year: int = 2026):
    return load_mart("eurostat_rendimento_10y", "mart_rendimento_10y", year)


# ── Clean (esplorazione) ─────────────────────────────────────────


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
def query_scadenze(sql: str, year: int = 2026):
    return _q("mef_scadenze_isin", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_fpi(sql: str, year: int = 2026):
    return _q("fpi_debito_pa", sql, year)


@st.cache_data(ttl=3600, show_spinner=False)
def query_vita_media(sql: str, year: int = 2026):
    return _q("mef_vita_media", sql, year)

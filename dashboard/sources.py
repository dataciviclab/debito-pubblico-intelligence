"""Data sources for the Debito Pubblico Intelligence dashboard."""

from __future__ import annotations

import streamlit as st
from pathlib import Path

from lab_connectors.duckdb.queries import load_clean, query_clean
from lab_connectors.registry import load_registry

PREFIX = "debito_pubblico_intelligence/"

_registry = load_registry(Path(__file__).parent.parent / "registry" / "registry.json")


def _flat_url(slug: str, year: int = 2026) -> str:
    """Build URL for flat clean files: {prefix}{slug}/{slug}_{year}_clean.parquet"""
    return (
        f"https://storage.googleapis.com/dataciviclab-clean/"
        f"{PREFIX}{slug}/{slug}_{year}_clean.parquet"
    )


def _flat_urls(slug: str, years: list[int] | None = None) -> list[str]:
    """Build URLs for flat clean files, one per year."""
    if years is None:
        years = [2026]
    return [_flat_url(slug, y) for y in years]


# ── ocpi_serie_storiche (il dataset principale, multi-series) ──────

def query_ocpi(sql: str, years: list[int] | None = None):
    """Query sulle serie storiche OCPI (1861-2025)."""
    urls = _flat_urls("ocpi_serie_storiche", years or [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


def load_ocpi_series(serie: str):
    """Carica una singola serie OCPI come DataFrame pivot anno→valore."""
    return query_ocpi(f"""
        SELECT anno, valore
        FROM clean_input
        WHERE serie = '{serie}'
        ORDER BY anno
    """)


# ── eurostat_debito_pil ────────────────────────────────────────────

def query_debito_pil(sql: str):
    urls = _flat_urls("eurostat_debito_pil", [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


# ── eurostat_rendimento_10y (spread) ───────────────────────────────

def query_rendimento(sql: str):
    urls = _flat_urls("eurostat_rendimento_10y", [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


# ── mef_composizione ──────────────────────────────────────────────

def query_composizione(sql: str):
    urls = _flat_urls("mef_composizione", [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


# ── mef_scadenze_isin ─────────────────────────────────────────────

def load_scadenze():
    urls = _flat_urls("mef_scadenze_isin", [2026])
    paths = "', '".join(urls)
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"SELECT * FROM read_parquet(['{paths}'], union_by_name=true)")


def query_scadenze(sql: str):
    urls = _flat_urls("mef_scadenze_isin", [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


# ── mef_titoli_12m ────────────────────────────────────────────────

def load_titoli_12m():
    urls = _flat_urls("mef_titoli_12m", [2026])
    paths = "', '".join(urls)
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"SELECT * FROM read_parquet(['{paths}'], union_by_name=true)")


# ── mef_vita_media ────────────────────────────────────────────────

def load_vita_media():
    urls = _flat_urls("mef_vita_media", [2026])
    paths = "', '".join(urls)
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"SELECT * FROM read_parquet(['{paths}'], union_by_name=true)")


def query_vita_media(sql: str):
    urls = _flat_urls("mef_vita_media", [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


# ── fpi_debito_pa ─────────────────────────────────────────────────

def query_fpi(sql: str):
    urls = _flat_urls("fpi_debito_pa", [2026])
    paths = "', '".join(urls)
    cte = f"WITH clean_input AS (SELECT * FROM read_parquet(['{paths}'], union_by_name=true))"
    from lab_connectors.duckdb.core import _query_df
    return _query_df(f"{cte} {sql}")


def get_registry():
    return _registry


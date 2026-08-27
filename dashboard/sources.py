"""Data sources for the Debito Pubblico Intelligence dashboard."""

from __future__ import annotations

import streamlit as st
from pathlib import Path

from lab_connectors.duckdb.queries import load_clean, query_clean
from lab_connectors.registry import load_registry

PREFIX = "debito_pubblico_intelligence/"

_registry = load_registry(Path(__file__).parent.parent / "registry" / "registry.json")


# ── ocpi_serie_storiche (il dataset principale, multi-series) ──────

def query_ocpi(sql: str):
    """Query sulle serie storiche OCPI (1861-2025)."""
    return query_clean("ocpi_serie_storiche", sql, [2026], prefix=PREFIX)


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
    return query_clean("eurostat_debito_pil", sql, [2026], prefix=PREFIX)


# ── eurostat_rendimento_10y (spread) ───────────────────────────────

def query_rendimento(sql: str):
    return query_clean("eurostat_rendimento_10y", sql, [2026], prefix=PREFIX)


# ── mef_composizione ──────────────────────────────────────────────

def load_composizione():
    return load_clean("mef_composizione", [2026], prefix=PREFIX)


def query_composizione(sql: str):
    return query_clean("mef_composizione", sql, [2026], prefix=PREFIX)


# ── mef_scadenze_isin ─────────────────────────────────────────────

def load_scadenze():
    return load_clean("mef_scadenze_isin", [2026], prefix=PREFIX)


def query_scadenze(sql: str):
    return query_clean("mef_scadenze_isin", sql, [2026], prefix=PREFIX)


# ── mef_titoli_12m ────────────────────────────────────────────────

def load_titoli_12m():
    return load_clean("mef_titoli_12m", [2026], prefix=PREFIX)


# ── mef_vita_media ────────────────────────────────────────────────

def load_vita_media():
    return load_clean("mef_vita_media", [2026], prefix=PREFIX)


def query_vita_media(sql: str):
    return query_clean("mef_vita_media", sql, [2026], prefix=PREFIX)


# ── fpi_debito_pa ─────────────────────────────────────────────────

def query_fpi(sql: str):
    return query_clean("fpi_debito_pa", sql, [2026], prefix=PREFIX)


def get_registry():
    return _registry

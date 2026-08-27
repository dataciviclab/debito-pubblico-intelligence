"""Data sources for the Debito Pubblico Intelligence dashboard."""

from __future__ import annotations

from pathlib import Path

from lab_connectors.duckdb.queries import query_clean_flat
from lab_connectors.registry import load_registry

PREFIX = "debito_pubblico_intelligence/"
_registry = load_registry(Path(__file__).parent.parent / "registry" / "registry.json")


def query_ocpi(sql: str, years: list[int] | None = None):
    return query_clean_flat("ocpi_serie_storiche", sql, year=years[-1] if years else 2026, prefix=PREFIX)


def query_debito_pil(sql: str):
    return query_clean_flat("eurostat_debito_pil", sql, prefix=PREFIX)


def query_rendimento(sql: str):
    return query_clean_flat("eurostat_rendimento_10y", sql, prefix=PREFIX)


def query_composizione(sql: str):
    return query_clean_flat("mef_composizione", sql, prefix=PREFIX)


def load_scadenze():
    return query_clean_flat("mef_scadenze_isin", "SELECT * FROM clean_input", prefix=PREFIX)


def query_scadenze(sql: str):
    return query_clean_flat("mef_scadenze_isin", sql, prefix=PREFIX)


def load_titoli_12m():
    return query_clean_flat("mef_titoli_12m", "SELECT * FROM clean_input", prefix=PREFIX)


def load_vita_media():
    return query_clean_flat("mef_vita_media", "SELECT * FROM clean_input", prefix=PREFIX)


def query_vita_media(sql: str):
    return query_clean_flat("mef_vita_media", sql, prefix=PREFIX)


def query_fpi(sql: str):
    return query_clean_flat("fpi_debito_pa", sql, prefix=PREFIX)


def get_registry():
    return _registry

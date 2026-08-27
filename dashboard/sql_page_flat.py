"""Versione flat di render_sql_query per dataset con path {slug}/{slug}_{year}_clean.parquet."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd


def render_sql_query_flat(
    *,
    registry: Any,
    prefix: str = "",
    default_slug: str | None = None,
    title: str = "🧪 Query SQL",
    description: str = (
        "Scrivi query SQL sui dataset pubblici. "
        "Usa ``clean_input`` come nome della tabella virtuale."
    ),
    max_rows: int = 1000,
) -> None:
    """Render SQL page for flat clean files (no year directory)."""
    import duckdb
    import streamlit as st

    from lab_connectors.duckdb.sql_page import _get_datasets_with_columns, _build_query

    st.title(title)
    st.markdown(description)

    datasets = _get_datasets_with_columns(registry)
    slug_list = [ds["slug"] for ds in datasets]
    slug_to_ds = {ds["slug"]: ds for ds in datasets}

    if not slug_list:
        st.error("Nessun dataset trovato nel registry.")
        return

    idx = 0
    if default_slug and default_slug in slug_list:
        idx = slug_list.index(default_slug)

    selected_slug = st.selectbox(
        "📋 Dataset",
        slug_list,
        index=idx,
        format_func=lambda s: f"{s} ({len(slug_to_ds[s]['columns'])} colonne)",
    )

    ds_info = slug_to_ds[selected_slug]

    if ds_info["columns"]:
        with st.expander(f"Schema: {selected_slug}", expanded=False):
            st.dataframe(
                pd.DataFrame(ds_info["columns"]),
                use_container_width=True,
                hide_index=True,
            )

    # Get year from dataset period
    period = ds_info.get("period", {})
    year = period.get("end", 2026) if isinstance(period, dict) else 2026

    # Build flat URL
    bucket = "dataciviclab-clean"
    flat_url = (
        f"https://storage.googleapis.com/{bucket}/"
        f"{prefix}{selected_slug}/{selected_slug}_{year}_clean.parquet"
    )

    cte_expr = f"SELECT * FROM read_parquet('{flat_url}')"

    # Default SQL
    default_sql = f"SELECT * FROM clean_input LIMIT 20"
    sql = st.text_area(
        "📝 SQL Query",
        value=default_sql,
        height=120,
        key="sql_input",
    )

    if st.button("▶️ Esegui", type="primary"):
        wrapped = _build_query(sql, cte_expr, max_rows)
        t0 = time.time()
        try:
            with duckdb.connect():
                df = duckdb.sql(wrapped).df()
            elapsed = time.time() - t0
            st.success(f"{len(df)} righe in {elapsed:.2f}s")
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, f"{selected_slug}.csv", "text/csv")
        except Exception as e:
            st.error(f"Errore: {e}")

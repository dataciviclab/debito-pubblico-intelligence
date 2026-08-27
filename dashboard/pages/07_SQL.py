"""Query SQL — versione custom per flat files."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
import streamlit as st
from sources import _q
from lab_connectors.registry import load_registry
from lab_connectors.duckdb.sql_page import _get_datasets_with_columns, _build_query

st.title("🧪 Query SQL")
st.markdown("Interroga direttamente i dati del Debito Pubblico. Scrivi SQL su ``clean_input``.")

registry = load_registry(Path(__file__).parent.parent.parent / "registry" / "registry.json")
datasets = _get_datasets_with_columns(registry)
slug_list = [ds["slug"] for ds in datasets]
slug_to_ds = {ds["slug"]: ds for ds in datasets}

selected_slug = st.selectbox(
    "📋 Dataset",
    slug_list,
    index=slug_list.index("ocpi_serie_storiche"),
    format_func=lambda s: f"{s} ({len(slug_to_ds[s]['columns'])} colonne)",
)

ds_info = slug_to_ds[selected_slug]
if ds_info["columns"]:
    with st.expander(f"Schema: {selected_slug}", expanded=False):
        import pandas as pd
        st.dataframe(pd.DataFrame(ds_info["columns"]), use_container_width=True, hide_index=True)

# CTE flat: un solo file, anno 2026
clean_url = f"https://storage.googleapis.com/dataciviclab-clean/debito_pubblico_intelligence/{selected_slug}/2026/{selected_slug}_2026_clean.parquet"
cte = f"SELECT * FROM read_parquet('{clean_url}')"

sql = st.text_area("SQL", value="SELECT * FROM clean_input LIMIT 20", height=150)

if st.button("▶️ Esegui", type="primary"):
    wrapped = _build_query(sql, cte, 1000)
    t0 = time.time()
    try:
        with duckdb.connect() as con:
            df = con.sql(wrapped).df()
        st.success(f"{len(df)} righe in {time.time()-t0:.2f}s")
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV", csv, f"{selected_slug}.csv", "text/csv")
    except Exception as e:
        st.error(f"Errore: {e}")

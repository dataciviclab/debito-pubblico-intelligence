"""Flussi Banca d'Italia — FPI debito PA."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sources import query_fpi

st.title("🏦 Flussi Banca d'Italia (FPI)")

# ── Filtro ────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    year_start = st.selectbox("Da anno", list(range(2010, 2027)), index=0)
with col2:
    year_end = st.selectbox("A anno", list(range(2010, 2027)), index=16)

# ── Emissioni nette titoli ───────────────────────────────────────
st.subheader("Emissioni Nette Titoli a Medio/Lungo Termine")

df_emissioni = query_fpi(f"""
    SELECT
        SUBSTR(CAST(data AS VARCHAR), 1, 7) AS mese,
        SUM(valore_mln_eur) AS emissioni_mln
    FROM clean_input
    WHERE tavola_nome = 'fabbisogno_ap_strumenti'
        AND codice IN ('S13.F32', 'S13.F31')
        AND CAST(SUBSTR(CAST(data AS VARCHAR), 1, 4) AS INTEGER) BETWEEN {year_start} AND {year_end}
    GROUP BY mese
    ORDER BY mese
""")

if not df_emissioni.empty:
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in df_emissioni["emissioni_mln"]]
        fig.add_trace(go.Bar(
            x=df_emissioni["mese"],
            y=df_emissioni["emissioni_mln"] / 1e3,
            marker_color=colors,
            name="Emissioni nette (mld €)",
        ))
        fig.add_hline(y=0, line_color="gray")
        fig.update_layout(
            xaxis_title="Mese",
            yaxis_title="Emissioni nette (mld €)",
            height=400,
            margin={"t": 30},
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart(df_emissioni.set_index("mese")["emissioni_mln"] / 1e3)

# ── Stock debito PA ──────────────────────────────────────────────
st.subheader("Stock Debito PA")

df_stock = query_fpi(f"""
    SELECT
        SUBSTR(CAST(data AS VARCHAR), 1, 7) AS mese,
        SUM(valore_mln_eur) AS stock_mln
    FROM clean_input
    WHERE tavola_nome = 'debito_ap_sottosettori'
        AND codice = 'S1311.MGD'
        AND CAST(SUBSTR(CAST(data AS VARCHAR), 1, 4) AS INTEGER) BETWEEN {year_start} AND {year_end}
    GROUP BY mese
    ORDER BY mese
""")

if not df_stock.empty:
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_stock["mese"],
            y=df_stock["stock_mln"] / 1e3,
            name="Stock Debito PA (mld €)",
            line={"color": "#1f77b4", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(31,119,180,0.1)",
        ))
        fig.update_layout(
            xaxis_title="Mese",
            yaxis_title="Stock (mld €)",
            height=400,
            margin={"t": 30},
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.line_chart(df_stock.set_index("mese")["stock_mln"] / 1e3)

# ── Fabbisogno netto ─────────────────────────────────────────────
st.subheader("Fabbisogno Netto")

df_fabb = query_fpi(f"""
    SELECT
        SUBSTR(CAST(data AS VARCHAR), 1, 7) AS mese,
        SUM(valore_mln_eur) AS fabbisogno_mln
    FROM clean_input
    WHERE tavola_nome = 'fabbisogno_ap_strumenti'
        AND codice = 'S13.FAB'
        AND CAST(SUBSTR(CAST(data AS VARCHAR), 1, 4) AS INTEGER) BETWEEN {year_start} AND {year_end}
    GROUP BY mese
    ORDER BY mese
""")

if not df_fabb.empty:
    try:
        import plotly.graph_objects as go

        colors = ["#d62728" if v > 0 else "#2ca02c" for v in df_fabb["fabbisogno_mln"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_fabb["mese"],
            y=df_fabb["fabbisogno_mln"] / 1e3,
            marker_color=colors,
            name="Fabbisogno netto (mld €)",
        ))
        fig.add_hline(y=0, line_color="gray")
        fig.update_layout(
            xaxis_title="Mese",
            yaxis_title="Fabbisogno (mld €)",
            height=400,
            margin={"t": 30},
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart(df_fabb.set_index("mese")["fabbisogno_mln"] / 1e3)

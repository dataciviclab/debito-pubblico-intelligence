"""Spread BTP-Bund — Confronto rendimenti 10Y europei."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sources import query_rendimento

st.title("📈 Spread BTP-Bund")

# ── Filtro anni ───────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    year_start = st.selectbox("Da", list(range(1980, 2027)), index=30)
with col2:
    year_end = st.selectbox("A", list(range(1980, 2027)), index=46)

# ── Rendimenti 10Y multi-paese ────────────────────────────────────
st.subheader("Rendimento Titoli di Stato 10Y")

df = query_rendimento(f"""
    SELECT mese, paese, rendimento_pct
    FROM clean_input
    WHERE CAST(SUBSTR(mese, 1, 4) AS INTEGER) BETWEEN {year_start} AND {year_end}
    ORDER BY mese, paese
""")

if df.empty:
    st.warning("Nessun dato disponibile.")
    st.stop()

# Mappa codici paesi
PAESI = {"IT": "🇮🇹 Italia", "DE": "🇩🇪 Germania", "FR": "🇫🇷 Francia", "ES": "🇪🇸 Spagna", "US": "🇺🇸 USA", "JP": "🇯🇵 Giappone"}

selected = st.multiselect(
    "Paesi",
    list(PAESI.keys()),
    default=["IT", "DE"],
    format_func=lambda x: PAESI.get(x, x),
)

if selected:
    df_filtered = df[df["paese"].isin(selected)]
    pivot = df_filtered.pivot(index="mese", columns="paese", values="renimento_pct") if "renimento_pct" in df_filtered.columns else df_filtered.pivot_table(index="mese", columns="paese", values="rendimento_pct")

    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        colors = {"IT": "#1f77b4", "DE": "#2ca02c", "FR": "#ff7f0e", "ES": "#d62728", "US": "#9467bd", "JP": "#8c564b"}
        for paese in selected:
            if paese in pivot.columns:
                fig.add_trace(go.Scatter(
                    x=pivot.index,
                    y=pivot[paese],
                    name=PAESI.get(paese, paese),
                    line=dict(color=colors.get(paese, "#333"), width=2),
                ))
        fig.update_layout(yaxis_title="Rendimento 10Y (%)", height=500, margin=dict(t=30))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.line_chart(pivot)

# ── Spread BTP-Bund ───────────────────────────────────────────────
st.subheader("📊 Spread BTP-Bund (IT − DE)")

df_spread = query_rendimento(f"""
    SELECT
        it.mese,
        it.rendimento_pct - de.rendimento_pct AS spread
    FROM clean_input it
    JOIN clean_input de ON it.mese = de.mese
    WHERE it.paese = 'IT' AND de.paese = 'DE'
        AND CAST(SUBSTR(it.mese, 1, 4) AS INTEGER) BETWEEN {year_start} AND {year_end}
    ORDER BY it.mese
""")

if not df_spread.empty:
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_spread["mese"],
            y=df_spread["spread"],
            name="Spread BTP-Bund",
            line=dict(color="#e74c3c", width=2),
            fill="tozeroy",
            fillcolor="rgba(231, 76, 60, 0.1)",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            yaxis_title="Spread (punti base)",
            xaxis_title="Mese",
            height=400,
            margin=dict(t=30),
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.line_chart(df_spread.set_index("mese")["spread"])

    # KPI spread
    latest_spread = df_spread["spread"].iloc[-1]
    avg_spread = df_spread["spread"].mean()
    col1, col2 = st.columns(2)
    col1.metric("Spread attuale", f"{latest_spread:.0f} pb")
    col2.metric("Spread medio", f"{avg_spread:.0f} pb")

"""Scadenze — Maturity wall e rollover del debito."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sources import query_scadenze, load_scadenze

st.title("⏰ Scadenze Debito")

# ── Dati ──────────────────────────────────────────────────────────
df = load_scadenze()

if df.empty:
    st.warning("Nessun dato disponibile.")
    st.stop()

# Estrai anno-mese scadenza
df["scadenza_mese"] = df["scadenza"].astype(str).str[:7]
df["scadenza_anno"] = df["scadenza"].astype(str).str[:4].astype(int)

# ── Filtri ────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    year_filter = st.selectbox(
        "Anno scadenza",
        sorted(df["scadenza_anno"].unique()),
        index=0,
    )
with col2:
    tipo_filter = st.multiselect(
        "Tipo titolo",
        sorted(df["tipo"].unique()),
        default=sorted(df["tipo"].unique()),
    )

df_filtered = df[(df["scadenza_anno"] == year_filter) & (df["tipo"].isin(tipo_filter))]

# ── KPI ───────────────────────────────────────────────────────────
totale = df_filtered["circolante_riv_eur"].sum()
nr_titoli = len(df_filtered)
cedola_media = df_filtered["cedola_pct"].dropna().mean()

col1, col2, col3 = st.columns(3)
col1.metric("💰 Totale in Scadenza", f"€ {totale/1e9:,.1f} mld")
col2.metric("📋 Nr Titoli", f"{nr_titoli}")
col3.metric("📈 Cedola Media", f"{cedola_media:.2f}%" if cedola_media == cedola_media else "—")

# ── Maturity Wall per mese ───────────────────────────────────────
st.subheader(f"Maturity Wall — {year_filter}")

df_mese = df_filtered.groupby("scadenza_mese").agg(
    totale=("circolante_riv_eur", "sum"),
    nr_titoli=("isin", "count"),
).reset_index().sort_values("scadenza_mese")

try:
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_mese["scadenza_mese"],
        y=df_mese["totale"] / 1e9,
        name="Circolante (mld €)",
        marker_color="#1f77b4",
    ))
    fig.update_layout(
        xaxis_title="Mese Scadenza",
        yaxis_title="Importo (mld €)",
        height=400,
        margin=dict(t=30),
    )
    st.plotly_chart(fig, use_container_width=True)
except ImportError:
    st.bar_chart(df_mese.set_index("scadenza_mese")["totale"] / 1e9)

# ── Distribuzione per tipo ───────────────────────────────────────
st.subheader("Distribuzione per Tipo Titolo")

df_tipo = df_filtered.groupby("tipo").agg(
    totale=("circolante_riv_eur", "sum"),
    nr_titoli=("isin", "count"),
    cedola_media=("cedola_pct", "mean"),
).reset_index().sort_values("totale", ascending=False)

try:
    import plotly.express as px

    fig = px.pie(
        df_tipo,
        names="tipo",
        values="totale",
        title=f"Scadenze {year_filter} per Tipo",
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
except ImportError:
    st.bar_chart(df_tipo.set_index("tipo")["totale"] / 1e9)

# ── Tabella dettaglio ────────────────────────────────────────────
st.subheader("Dettaglio Titoli")

df_display = df_filtered[["isin", "tipo", "emissione", "scadenza", "cedola_pct", "circolante_riv_eur"]].copy()
df_display["circolante_mld"] = (df_display["circolante_riv_eur"] / 1e9).round(2)
df_display = df_display.drop(columns=["circolante_riv_eur"])

st.dataframe(df_display, use_container_width=True, hide_index=True)

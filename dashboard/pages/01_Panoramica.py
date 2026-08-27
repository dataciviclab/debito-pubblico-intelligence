"""Panoramica — Visione d'insieme del debito pubblico italiano."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sources import query_ocpi, query_debito_pil, query_composizione

st.title("🇮🇹 Debito Pubblico Italiano")

# ── KPI da OCPI ───────────────────────────────────────────────────
df_debito = query_ocpi("SELECT anno, valore FROM clean_input WHERE serie = 'C' ORDER BY anno")
df_dpil = query_ocpi("SELECT anno, valore FROM clean_input WHERE serie = 'D' ORDER BY anno")
df_interessi = query_ocpi("SELECT anno, valore FROM clean_input WHERE serie = 'I' ORDER BY anno")
df_saldo = query_ocpi("SELECT anno, valore FROM clean_input WHERE serie = 'G' ORDER BY anno")
df_pil = query_ocpi("SELECT anno, valore FROM clean_input WHERE serie = 'B' ORDER BY anno")

if df_debito.empty:
    st.warning("Nessun dato disponibile.")
    st.stop()

# Ultimo anno con dati
latest = int(df_debito["anno"].max())
row_debito = df_debito[df_debito["anno"] == latest].iloc[0]
row_dpil = df_dpil[df_dpil["anno"] == latest].iloc[0] if not df_dpil.empty else None
row_interessi = df_interessi[df_interessi["anno"] == latest].iloc[0] if not df_interessi.empty else None
row_saldo = df_saldo[df_saldo["anno"] == latest].iloc[0] if not df_saldo.empty else None
row_pil = df_pil[df_pil["anno"] == latest].iloc[0] if not df_pil.empty else None

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "💰 Stock Debito",
    f"€ {row_debito['valore']/1e3:,.0f} mld",
    help=f"Dati al {latest}, fonte OCPI",
)
if row_dpil is not None:
    delta = None
    if len(df_dpil) > 1:
        prev = df_dpil[df_dpil["anno"] == latest - 1]
        if not prev.empty:
            delta = f"{row_dpil['valore'] - prev.iloc[0]['valore']:+.1f}%"
    col2.metric(
        "📊 Debito/PIL",
        f"{row_dpil['valore']:.1f}%",
        delta=delta,
        help="Soglia Maastricht: 60%",
    )
if row_interessi is not None:
    col3.metric(
        "💸 Interessi/PIL",
        f"{row_interessi['valore']:.2f}%",
    )
if row_saldo is not None:
    col4.metric(
        "⚖️ Saldo Primario/PIL",
        f"{row_saldo['valore']:+.2f}%",
    )

# ── Debito/PIL con soglia Maastricht ──────────────────────────────
st.subheader(f"Debito/PIL — Storico (1861–{latest})")

if not df_dpil.empty:
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_dpil["anno"],
        y=df_dpil["valore"],
        name="Debito/PIL",
        line=dict(color="#1f77b4", width=2),
        fill="tozeroy",
        fillcolor="rgba(31,119,180,0.1)",
    ))
    fig.add_hline(
        y=60, line_dash="dash", line_color="red",
        annotation_text="Maastricht 60%",
        annotation_position="top left",
    )
    fig.update_layout(
        yaxis_title="Debito/PIL %",
        xaxis_title="Anno",
        height=400,
        margin=dict(t=30),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── PIL e Debito (doppio asse) ───────────────────────────────────
st.subheader(f"PIL e Debito — {latest}")

if not df_pil.empty and not df_debito.empty:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=df_pil["anno"],
        y=df_pil["valore"] / 1e3,
        name="PIL nominale (mld €)",
        marker_color="rgba(46, 204, 113, 0.5)",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df_debito["anno"],
        y=df_debito["valore"] / 1e3,
        name="Debito (mld €)",
        line=dict(color="#e74c3c", width=2),
    ), secondary_y=True)
    fig.update_yaxes(title_text="PIL (mld €)", secondary_y=False)
    fig.update_yaxes(title_text="Debito (mld €)", secondary_y=True)
    fig.update_layout(height=400, margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)

# ── Composizione debito (snapshot) ────────────────────────────────
st.subheader(f"🧩 Composizione Debito — Snapshot {latest}")

df_comp = query_composizione("""
    SELECT tipologia, valore_mln_eur
    FROM clean_input
    WHERE colonna = 'mln. Euro' AND tipologia != 'Totale'
    ORDER BY valore_mln_eur DESC
""")

if not df_comp.empty:
    try:
        import plotly.express as px

        fig = px.treemap(
            df_comp,
            path=["tipologia"],
            values="valore_mln_eur",
            title="Composizione per Tipo Titolo",
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart(df_comp.set_index("tipologia")["valore_mln_eur"] / 1e3)

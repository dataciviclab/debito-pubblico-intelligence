"""Composizione Debito — Come è fatto il debito italiano."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sources import query_composizione

st.title("🧩 Composizione Debito")

# ── Dati ──────────────────────────────────────────────────────────
df = query_composizione("""
    SELECT tipologia, valore_mln_eur
    FROM clean_input
    WHERE colonna = 'mln. Euro'
    ORDER BY valore_mln_eur DESC
""")

if df.empty:
    st.warning("Nessun dato disponibile.")
    st.stop()

totale = df["valore_mln_eur"].sum()

# ── KPI ───────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("💰 Totale Debito", f"€ {totale/1e3:,.0f} mld")
col2.metric("📋 Tipologie", f"{len(df)}")
# BTP dominante
btp = df[df["tipologia"].str.startswith("BTP")]["valore_mln_eur"].sum()
col3.metric("📊 BTP (tutte)", f"{btp/totale*100:.1f}%")

# ── Treemap ───────────────────────────────────────────────────────
st.subheader("Composizione per Tipo Titolo")

df_treemap = df[df["tipologia"] != "Totale"]

try:
    import plotly.express as px

    fig = px.treemap(
        df_treemap,
        path=["tipologia"],
        values="valore_mln_eur",
        title="Debito per Tipologia Titolo (€ mln)",
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
except ImportError:
    st.bar_chart(df.set_index("tipologia")["valore_mln_eur"] / 1e3)

# ── Tabella dettaglio ────────────────────────────────────────────
st.subheader("Dettaglio")

df_display = df[df["tipologia"] != "Totale"].copy()
df_display["pct"] = (df_display["valore_mln_eur"] / totale * 100).round(1)
df_display["valore_mld"] = (df_display["valore_mln_eur"] / 1e3).round(1)

st.dataframe(
    df_display[["tipologia", "valore_mld", "pct"]].rename(columns={
        "tipologia": "Tipologia",
        "valore_mld": "Valore (mld €)",
        "pct": "%",
    }),
    use_container_width=True,
    hide_index=True,
)

# ── Note ──────────────────────────────────────────────────────────
st.caption("""
- **BTP**: Buoni del Tesoro Poliennali (scadenza 3-50 anni)
- **BOT**: Buoni Ordinari del Tesoro (scadenza 3-12 mesi)
- **CCTeu**: Certificati di Credito del Tesoro europei (tasso variabile)
- **BTP €i**: BTP indicizzati all'inflazione
- **BTP Green**: BTP per spesa verde
- **PostA**: Buoni Fruttiferi Postali
""")

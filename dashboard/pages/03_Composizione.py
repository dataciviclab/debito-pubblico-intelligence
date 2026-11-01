"""Composizione Debito — Come è fatto il debito italiano."""

import pandas as pd
import streamlit as st
from sources import load_composizione

st.title("🧩 Composizione Debito")

# ── Dati ──────────────────────────────────────────────────────────
df = load_composizione()

if df.empty:
    st.warning("Nessun dato disponibile.")
    st.stop()

if "data_ref" not in df.columns or "aggregato" not in df.columns:
    st.error(
        "I dati pubblicati precedono il nuovo contratto del dataset (`data_ref`/`aggregato`): "
        "rilancia la pipeline o attendi il prossimo aggiornamento."
    )
    st.stop()

df["data_ref"] = pd.to_datetime(df["data_ref"])

# ── Selezione mese ────────────────────────────────────────────────
mesi = sorted(df["data_ref"].unique(), reverse=True)
mese = st.selectbox(
    "Mese di riferimento",
    mesi,
    index=0,
    format_func=lambda d: pd.Timestamp(d).strftime("%m/%Y"),
)
st.caption(
    f"Serie disponibile: {len(mesi)} mesi "
    f"({pd.Timestamp(min(mesi)):%m/%Y} → {pd.Timestamp(max(mesi)):%m/%Y})"
)

corrente = df[df["data_ref"] == mese]

# Esclude "Totale"/"Estero"/"Altri programmi" (aggregati) e le voci "di cui ..."
foglie = corrente[~corrente["sottoinsieme"] & ~corrente["aggregato"]]

totale_row = corrente[corrente["tipologia"] == "Totale"]
totale = totale_row["valore_mln_eur"].iloc[0] if not totale_row.empty else foglie["valore_mln_eur"].sum()

# ── KPI ───────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("💰 Totale Debito", f"€ {totale/1e3:,.0f} mld")
col2.metric("📋 Famiglie", f"{foglie['famiglia'].nunique()}")
btp = foglie[foglie["famiglia"].str.startswith("BTP")]["valore_mln_eur"].sum()
col3.metric("📊 BTP (tutte)", f"{btp/totale*100:.1f}%")

# ── Treemap per famiglia ─────────────────────────────────────────
st.subheader(f"Composizione per Famiglia — {pd.Timestamp(mese):%m/%Y}")

df_fam = (
    foglie.groupby("famiglia", as_index=False)["valore_mln_eur"]
    .sum()
    .sort_values("valore_mln_eur", ascending=False)
)

try:
    import plotly.express as px

    fig = px.treemap(
        df_fam,
        path=["famiglia"],
        values="valore_mln_eur",
        title="Debito per famiglia di strumento (€ mln)",
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, width='stretch')
except ImportError:
    st.bar_chart(df_fam.set_index("famiglia")["valore_mln_eur"] / 1e3)

# ── Serie storica ────────────────────────────────────────────────
st.subheader("Composizione nel tempo")

if len(mesi) > 1:
    storico = df[~df["sottoinsieme"] & ~df["aggregato"] & (df["tipologia"] != "Totale")]
    storico = storico.groupby(["data_ref", "famiglia"], as_index=False)["valore_mln_eur"].sum()
    try:
        import plotly.express as px

        fig = px.line(
            storico,
            x="data_ref",
            y=storico["valore_mln_eur"] / 1e3,
            color="famiglia",
            labels={"x": "Mese", "y": "mld €", "famiglia": "Famiglia"},
            title="Stock per famiglia (mld €)",
        )
        fig.update_layout(height=430, legend={"orientation": "h", "y": -0.25})
        st.plotly_chart(fig, width='stretch')
    except ImportError:
        st.line_chart(storico.pivot(index="data_ref", columns="famiglia", values="valore_mln_eur") / 1e3)
else:
    st.info("Serie storica non disponibile: c'è un solo mese pubblicato.")

# ── Tabella dettaglio ────────────────────────────────────────────
st.subheader("Dettaglio")

df_display = corrente.sort_values("valore_mln_eur", ascending=False).copy()
df_display["pct"] = (df_display["valore_mln_eur"] / totale * 100).round(1)
df_display["valore_mld"] = (df_display["valore_mln_eur"] / 1e3).round(1)
df_display["nota"] = ""
df_display.loc[df_display["aggregato"], "nota"] = "aggregato"
df_display.loc[df_display["sottoinsieme"], "nota"] = "di cui"

st.dataframe(
    df_display[["tipologia", "famiglia", "valore_mld", "pct", "nota"]].rename(columns={
        "tipologia": "Tipologia",
        "famiglia": "Famiglia",
        "valore_mld": "Valore (mld €)",
        "pct": "%",
        "nota": "Nota",
    }),
    width='stretch',
    hide_index=True,
)

# ── Note ──────────────────────────────────────────────────────────
st.caption("""
- **BTP**: Buoni del Tesoro Poliennali (scadenza 3-50 anni)
- **BOT**: Buoni Ordinari del Tesoro (scadenza 3-12 mesi)
- **CCTeu**: Certificati di Credito del Tesoro europei (tasso variabile)
- **BTP €i**: BTP indicizzati all'inflazione (valore rivalutato)
- **BTP Green**: BTP per spesa verde
- Le righe marcate **aggregato** contengono altre righe; quelle **di cui** sono
  sottoinsiemi del totale: nessuna delle due va sommata alle foglie.
""")

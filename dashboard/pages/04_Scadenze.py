"""Scadenze — Maturity wall e rollover del debito."""

import pandas as pd
import streamlit as st
from sources import load_scadenze, load_valuta, load_vita_residua

st.title("⏰ Scadenze Debito")

# ── Dati ──────────────────────────────────────────────────────────
df = load_scadenze()

if df.empty:
    st.warning("Nessun dato disponibile.")
    st.stop()

if "classe_strumento" not in df.columns or "stato" not in df.columns:
    st.error(
        "I dati pubblicati precedono il nuovo contratto del dataset "
        "(`classe_strumento`/`stato`): rilancia la pipeline o attendi il prossimo aggiornamento."
    )
    st.stop()

df["data_ref"] = pd.to_datetime(df["data_ref"])
df["scadenza"] = pd.to_datetime(df["scadenza"])

data_ref = df["data_ref"].max()
df["scadenza_mese"] = df["scadenza"].dt.strftime("%Y-%m")
df["scadenza_anno"] = df["scadenza"].dt.year

# ── Perimetro ─────────────────────────────────────────────────────
# Il mart è full-fidelity: contiene titoli di Stato, prestiti UE (SURE/NGEU) e
# anche le scadenze già passate alla data_ref. Senza filtro la barra dell'anno
# corrente include ~341 mld già rimborsati.
classi = sorted(df["classe_strumento"].unique())
default_classi = ["Titoli di Stato"] if "Titoli di Stato" in classi else classi

col1, col2 = st.columns([2, 1])
with col1:
    classe_filter = st.multiselect("Perimetro", classi, default=default_classi)
with col2:
    includi_scaduti = st.checkbox("Includi scadenze già passate", value=False)

df_base = df[df["classe_strumento"].isin(classe_filter)]
if not includi_scaduti:
    df_base = df_base[df_base["stato"] == "in_circolazione"]

esclusi = df[~df.index.isin(df_base.index)]
mld_esclusi = esclusi["circolante_nom_eur"].sum() / 1e9

if df_base.empty:
    st.warning("Nessun titolo con questo perimetro.")
    st.stop()

st.caption(
    f"Dati al {data_ref.date()} · {len(df_base)} titoli in perimetro · "
    f"esclusi {len(esclusi)} titoli per € {mld_esclusi:,.1f} mld "
    f"(prestiti UE e/o scadenze già passate)"
)

# ── Filtri ────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
anni = sorted(df_base["scadenza_anno"].unique())
anno_default = next((a for a in anni if a >= data_ref.year), anni[-1])
with col1:
    year_filter = st.selectbox(
        "Anno scadenza",
        anni,
        index=anni.index(anno_default),
    )
with col2:
    famiglie = sorted(df_base["tipo_famiglia"].unique())
    tipo_filter = st.multiselect("Famiglia titolo", famiglie, default=famiglie)

df_filtered = df_base[
    (df_base["scadenza_anno"] == year_filter) & (df_base["tipo_famiglia"].isin(tipo_filter))
]

if df_filtered.empty:
    st.warning("Nessun titolo per anno/famiglia selezionati.")
    st.stop()

# ── KPI ───────────────────────────────────────────────────────────
totale = df_filtered["circolante_riv_eur"].sum()
nr_titoli = len(df_filtered)
cedola_media = df_filtered["cedola_pct"].dropna().mean()

col1, col2, col3 = st.columns(3)
col1.metric("💰 Totale in Scadenza", f"€ {totale/1e9:,.1f} mld")
col2.metric("📋 Nr Titoli", f"{nr_titoli}")
col3.metric("📈 Cedola Media", f"{cedola_media:.2f}%" if pd.notna(cedola_media) else "—")

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
        margin={"t": 30},
    )
    st.plotly_chart(fig, width='stretch')
except ImportError:
    st.bar_chart(df_mese.set_index("scadenza_mese")["totale"] / 1e9)

# ── Distribuzione per famiglia ───────────────────────────────────
st.subheader("Distribuzione per Famiglia Titolo")

df_tipo = df_filtered.groupby("tipo_famiglia").agg(
    totale=("circolante_riv_eur", "sum"),
    nr_titoli=("isin", "count"),
    cedola_media=("cedola_pct", "mean"),
).reset_index().sort_values("totale", ascending=False)

try:
    import plotly.express as px

    fig = px.pie(
        df_tipo,
        names="tipo_famiglia",
        values="totale",
        title=f"Scadenze {year_filter} per Famiglia",
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, width='stretch')
except ImportError:
    st.bar_chart(df_tipo.set_index("tipo_famiglia")["totale"] / 1e9)

# ── Tabella dettaglio ────────────────────────────────────────────
st.subheader("Dettaglio Titoli")

df_display = df_filtered[
    ["isin", "tipo", "tipo_famiglia", "emissione", "scadenza", "cedola_pct", "circolante_riv_eur"]
].copy()
df_display["circolante_mld"] = (df_display["circolante_riv_eur"] / 1e9).round(2)
df_display = df_display.drop(columns=["circolante_riv_eur"])

st.dataframe(df_display, width='stretch', hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# Tutto il debito AP (non solo i titoli del Tesoro)
# ═══════════════════════════════════════════════════════════════════
st.divider()
st.subheader("Tutto il debito AP, non solo i titoli")

vita = load_vita_residua()
if vita.empty:
    st.info("Mart della vita residua non disponibile (FPI).")
else:
    ultimo_fpi = vita["data"].max()
    v = vita[vita["data"] == ultimo_fpi]
    fasce = v[v["codice"].isin(["S13.MGD05", "S13.MGD06", "S13.MGD07"])]
    media = v[v["codice"] == "S13.MGD10"]["valore"]

    if not fasce.empty:
        c1, c2, c3, c4 = st.columns(4)
        for col, codice, etichetta in (
            (c1, "S13.MGD05", "Entro 1 anno"),
            (c2, "S13.MGD06", "1-5 anni"),
            (c3, "S13.MGD07", "Oltre 5 anni"),
        ):
            valore = fasce[fasce["codice"] == codice]["valore"].sum()
            col.metric(etichetta, f"€ {valore/1e3:,.0f} mld")
        if not media.empty:
            c4.metric("Vita media", f"{float(media.iloc[0]):.1f} anni")

        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=fasce["fascia"],
                y=fasce["valore"] / 1e3,
                marker_color="#4c78a8",
                text=[f"€{v/1e3:,.0f}" for v in fasce["valore"]],
                textposition="outside",
            ))
            fig.update_layout(
                yaxis_title="mld €",
                height=320,
                margin={"t": 20},
            )
            st.plotly_chart(fig, width="stretch")
        except ImportError:
            st.bar_chart(fasce.set_index("fascia")["valore"] / 1e3)

        st.caption(
            f"Dati FPI al {ultimo_fpi:%m/%Y}: qui c'è **tutto** il debito delle AP, "
            "non solo i titoli del Tesoro. La differenza con la sezione sopra è fatta di "
            "prestiti, depositi e passività degli enti locali."
        )

valuta = load_valuta()
if not valuta.empty:
    ultimo_val = valuta["data"].max()
    vv = valuta[valuta["data"] == ultimo_val]
    euro = vv[vv["codice"] == "S13.MGD11"]["valore"].sum()
    estero = vv[vv["codice"] == "S13.MGD04"]["valore"].sum()
    if euro:
        st.caption(
            f"Valuta al {ultimo_val:%m/%Y}: **{euro/1e3:,.0f} mld in euro** "
            f"e {estero/1e3:,.1f} mld in valuta estera ({estero/euro*100:.2f}%)."
        )

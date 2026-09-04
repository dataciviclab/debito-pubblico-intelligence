"""Panoramica — Control room del debito pubblico italiano.

Sezione 1: Status Board (KPI con soglie)
Sezione 2: Affidabilità dei dati (riconciliazione cross-fonte)
Sezione 3: Profilo temporale (scadenze 12 anni + top ISIN)
Sezione 4: What-if scenari (slider interattivi)
"""

from datetime import date
from pathlib import Path

import streamlit as st
from sources import (
    query_debito_pil,
    query_fpi,
    query_ocpi,
    query_rendimento,
    query_scadenze,
    query_vita_media,
)

ROOT = Path(__file__).resolve().parent.parent.parent
RECON_DIR = ROOT / "data" / "reconcile"

st.set_page_config(page_title="Debito Pubblico · Dashboard", page_icon="🇮🇹", layout="wide")

# ═══════════════════════════════════════════════════════════════════
# SEZIONE 1 — STATUS BOARD
# ═══════════════════════════════════════════════════════════════════

st.title("🇮🇹 Debito Pubblico Italiano")
st.caption(f"Aggiornato al {date.today().isoformat()} · Fonti: Banca d'Italia, Eurostat, OCPI, MEF Tesoro")


@st.cache_data(ttl=3600, show_spinner=False)
def _load_signals():
    """KPI principali da GCS via sources.py."""
    sig = {}

    # Debito/PIL da Eurostat
    try:
        df = query_debito_pil("SELECT anno, debito_pil_pct FROM clean_input WHERE settore='S13' ORDER BY anno DESC LIMIT 2")
        if not df.empty:
            sig["debito_pil"] = float(df.iloc[0]["debito_pil_pct"])
            if len(df) > 1:
                sig["debito_pil_delta"] = float(df.iloc[0]["debito_pil_pct"] - df.iloc[1]["debito_pil_pct"])
    except Exception:
        pass

    # Rendimento 10Y da Eurostat
    try:
        df = query_rendimento("SELECT paese, rendimento_pct FROM clean_input WHERE paese IN ('IT','DE') ORDER BY mese DESC")
        if not df.empty:
            it = df[df["paese"] == "IT"]
            de = df[df["paese"] == "DE"]
            if not it.empty:
                sig["rendimento_10y"] = float(it.iloc[0]["rendimento_pct"])
            if not it.empty and not de.empty:
                sig["spread"] = round(float(it.iloc[0]["rendimento_pct"] - de.iloc[0]["rendimento_pct"]), 2)
    except Exception:
        pass

    # Interessi/PIL e Saldo primario da OCPI
    try:
        df_i = query_ocpi("SELECT valore FROM clean_input WHERE serie = 'I' ORDER BY anno DESC LIMIT 1")
        if not df_i.empty:
            sig["interessi_pil"] = float(df_i.iloc[0]["valore"])
        df_g = query_ocpi("SELECT valore FROM clean_input WHERE serie = 'G' ORDER BY anno DESC LIMIT 1")
        if not df_g.empty:
            sig["saldo_pil"] = float(df_g.iloc[0]["valore"])
    except Exception:
        pass

    # Rollover 12m da scadenze
    try:
        df = query_scadenze("""
            SELECT
                sum(circolante_nom_eur) AS tot,
                sum(CASE WHEN scadenza < date_add(data_ref, INTERVAL 12 MONTH) THEN circolante_nom_eur ELSE 0 END) AS r12
            FROM clean_input WHERE scadenza >= data_ref
        """)
        if not df.empty and df.iloc[0]["tot"] > 0:
            sig["rollover_12m"] = round(float(df.iloc[0]["r12"] / df.iloc[0]["tot"] * 100), 1)
    except Exception:
        pass

    # Debito AP da FPI
    try:
        df = query_fpi("SELECT valore_mln_eur FROM clean_input WHERE tavola_nome='debito_ap_sottosettori' AND codice='S13.MGD' ORDER BY data DESC LIMIT 1")
        if not df.empty:
            sig["debito_ap"] = float(df.iloc[0]["valore_mln_eur"])
    except Exception:
        pass

    # Bd'Italia detiene % da FPI
    try:
        df_det = query_fpi("SELECT valore_mln_eur FROM clean_input WHERE codice='S13.MGD.S121' ORDER BY data DESC LIMIT 1")
        df_ap = query_fpi("SELECT valore_mln_eur FROM clean_input WHERE tavola_nome='debito_ap_sottosettori' AND codice='S13.MGD' ORDER BY data DESC LIMIT 1")
        if not df_det.empty and not df_ap.empty and df_ap.iloc[0]["valore_mln_eur"] > 0:
            sig["banca_italia_pct"] = round(float(df_det.iloc[0]["valore_mln_eur"] / df_ap.iloc[0]["valore_mln_eur"] * 100), 1)
    except Exception:
        pass

    # Vita media residua da MEF
    try:
        df = query_vita_media("SELECT round(max(vita_media_mesi)/12.0, 1) AS anni FROM clean_input WHERE tipologia='TOTALE'")
        if not df.empty and df.iloc[0]["anni"] is not None:
            sig["vita_media"] = float(df.iloc[0]["anni"])
    except Exception:
        pass

    return sig


sig = _load_signals()

if not sig:
    st.warning("Dati non disponibili. Esegui `make run-all` per generare i mart.")
    st.stop()


def _color_threshold(val, threshold, orient="high_bad"):
    """Restituisce 'normal' o 'bad'."""
    if orient == "high_bad" and val > threshold:
        return "bad"
    if orient == "low_bad" and val < threshold:
        return "bad"
    return "normal"


# Riga KPI principali
k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    v = sig.get("debito_pil", 0)
    d = sig.get("debito_pil_delta")
    st.metric("Debito/PIL", f"{v:.1f}%", delta=f"{d:+.1f}%" if d else None,
              delta_color="inverse" if _color_threshold(v, 130) == "bad" else "normal",
              help="Soglia Maastricht: 60%")

with k2:
    v = sig.get("rendimento_10y", 0)
    st.metric("Rendimento 10Y", f"{v:.2f}%",
              help="BTP Italia 10 anni")

with k3:
    v = sig.get("spread", 0)
    c = _color_threshold(v, 2)
    st.metric("Spread BTP-Bund", f"{v:.2f} pp",
              delta_color="inverse" if c == "bad" else "normal",
              help="Soglia: >2 pp = pressione mercato")

with k4:
    v = sig.get("interessi_pil", 0)
    st.metric("Interessi/PIL", f"{v:.2f}%",
              help="Spesa per interessi / PIL")

with k5:
    v = sig.get("saldo_pil", 0)
    st.metric("Saldo Primario/PIL", f"{v:+.1f}%",
              delta_color="inverse" if _color_threshold(v, 0, "low_bad") == "bad" else "normal",
              help="<0 = nuovo debito per gestione")

# Riga KPI secondari
k6, k7, k8, k9 = st.columns(4)

with k6:
    v = sig.get("rollover_12m", 0)
    c = _color_threshold(v, 15)
    st.metric("Rollover 12m", f"{v:.1f}%",
              delta_color="inverse" if c == "bad" else "normal",
              help="% debito in scadenza nei prossimi 12 mesi")

with k7:
    v = sig.get("vita_media", 0)
    c = _color_threshold(v, 5, "low_bad")
    st.metric("Vita Media", f"{v:.1f} anni",
              delta_color="inverse" if c == "bad" else "normal",
              help="<5 anni = durata corta")

with k8:
    v = sig.get("debito_ap", 0)
    st.metric("Debito AP", f"€ {v/1e3:,.0f} mld",
              help="Stock debito Amministrazioni Pubbliche")

with k9:
    v = sig.get("banca_italia_pct", 0)
    st.metric("Bd'Italia detiene", f"{v:.1f}%",
              help="% debito AP detenuto da Banca d'Italia")

st.divider()

# ═══════════════════════════════════════════════════════════════════
# SEZIONE 2 — AFFIDABILITÀ DEI DATI
# ═══════════════════════════════════════════════════════════════════

st.header("2. Affidabilità dei dati")
st.caption("Confronto cross-fonte: lo stesso concetto visto da fonti diverse")

# Carica summary.json prodotto da reconcile.py
summary_path = ROOT / "data" / "reconcile" / "summary.json"
if summary_path.exists():
    import json
    with open(summary_path, encoding="utf-8") as f:
        recon_summary = json.load(f)
else:
    recon_summary = []

if recon_summary:
    # Checklist visiva — auto-generata da summary.json
    cols = st.columns(2)
    for i, item in enumerate(recon_summary):
        with cols[i % 2]:
            n_anom = item.get("n_anomalie", 0)
            tipo = item.get("tipo", "confronto")

            # Icona in base al tipo e alle anomalie
            if tipo == "indicatore":
                icona = "ℹ️"
            elif n_anom == 0:
                icona = "✅"
            elif n_anom <= 2:
                icona = "⚠️"
            else:
                icona = "🔴"

            periodo = item.get("periodo", "")
            dettaglio = item.get("anomalie_dettaglio", "")
            st.markdown(f"{icona} **{item['nome']}** ({periodo})")
            if dettaglio:
                st.caption(dettaglio)

    # CSV dettagliati
    recon_files = sorted(RECON_DIR.glob("reconcile_*.csv")) if RECON_DIR.exists() else []
    if recon_files:
        with st.expander("Dettagli CSV"):
            import pandas as pd
            for f in recon_files:
                if f.name == "summary.json":
                    continue
                st.markdown(f"**{f.stem.replace('reconcile_', '').replace('_', ' ').title()}**")
                try:
                    st.dataframe(pd.read_csv(f), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Errore: {e}")
else:
    st.info("Riconciliazione non disponibile. Esegui `make reconcile` per generare i dati.")

st.divider()

# ═══════════════════════════════════════════════════════════════════
# SEZIONE 3 — PROFILO TEMPORALE
# ═══════════════════════════════════════════════════════════════════

st.header("3. Profilo temporale")

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Scadenze 12 anni")
    try:
        df_scad = query_scadenze("""
            SELECT cast(year(scadenza) AS INT) AS anno,
                   round(sum(circolante_nom_eur)/1e6, 0) AS mln_eur
            FROM clean_input
            WHERE scadenza >= data_ref
            GROUP BY 1 ORDER BY 1
            LIMIT 12
        """)

        if not df_scad.empty:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_scad["anno"].astype(str),
                y=df_scad["mln_eur"],
                marker_color="#1f77b4",
                text=df_scad["mln_eur"].apply(lambda x: f"€{x:,.0f}"),
                textposition="outside",
            ))
            fig.update_layout(
                xaxis_title="Anno",
                yaxis_title="mln EUR",
                height=350,
                margin={"t": 20, "b": 40},
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning("Nessuna scadenza trovata.")
    except Exception as e:
        st.error(f"Errore: {e}")

with col_right:
    st.subheader("Top 10 ISIN")
    try:
        df_isin = query_scadenze("""
            SELECT isin, tipo,
                   round(circolante_nom_eur/1e6, 0) AS mln
            FROM clean_input
            WHERE scadenza >= data_ref
            ORDER BY circolante_nom_eur DESC
            LIMIT 10
        """)
        if not df_isin.empty:
            st.dataframe(df_isin, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Errore: {e}")

st.divider()

# ═══════════════════════════════════════════════════════════════════
# SEZIONE 4 — WHAT-IF SCENARI
# ═══════════════════════════════════════════════════════════════════

st.header("4. Scenari di sostenibilità")
st.caption("d(t+1) = d(t) · (1+i)/(1+g) − sp ·  dove i=tasso interesse, g=crescita nominale, sp=saldo primario")


def _project(d0, i, g, sp, years):
    d = d0 / 100.0
    path = [round(d * 100, 1)]
    for _ in range(years):
        d = d * (1 + i / 100) / (1 + g / 100) - sp / 100
        path.append(round(d * 100, 1))
    return path


# Base: ultimo OCPI debito/PIL
try:
    df_base = query_ocpi("SELECT anno, valore FROM clean_input WHERE serie = 'D' ORDER BY anno DESC LIMIT 1")
    anno_base = int(df_base.iloc[0]["anno"])
    d0 = float(df_base.iloc[0]["valore"])
except Exception:
    anno_base, d0 = 2024, 137.0

HORIZON = 5

# Ipotesi preset: (nome, i%, g%, sp%)
SCEN_PRESETS = [
    ("stato_attuale", 2.89, 2.54, 0.7),
    ("crescita_forte", 2.89, 3.50, 0.7),
    ("crescita_debole", 2.89, 1.00, 0.7),
    ("tassi_alti", 3.50, 2.54, 0.7),
    ("avanzo_primario_2", 2.89, 2.54, 2.0),
    ("avanzo_primario_3", 2.89, 2.54, 3.0),
    ("stress", 3.50, 1.00, 0.0),
]

SCEN_COLORS = {
    "stato_attuale": "#1f77b4",
    "crescita_forte": "#2ecc71",
    "crescita_debole": "#e67e22",
    "tassi_alti": "#e74c3c",
    "avanzo_primario_2": "#9b59b6",
    "avanzo_primario_3": "#8e44ad",
    "stress": "#c0392b",
}


def _project(d0, i, g, sp, years):
    """Proietta debito/PIL: d(t+1) = d(t)·(1+i)/(1+g) − sp."""
    d = d0 / 100.0
    path = [round(d * 100, 1)]
    for _ in range(years):
        d = d * (1 + i / 100) / (1 + g / 100) - sp / 100
        path.append(round(d * 100, 1))
    return path

# Slider
col1, col2, col3 = st.columns(3)
with col1:
    i_custom = st.slider("Tasso interesse (i) %", 0.0, 8.0, 2.89, 0.01)
with col2:
    g_custom = st.slider("Crescita nominale (g) %", 0.0, 8.0, 2.54, 0.01)
with col3:
    sp_custom = st.slider("Saldo primario (sp) % PIL", -5.0, 5.0, 0.7, 0.1)

horizon = 5
years = list(range(anno_base, anno_base + horizon + 1))

import plotly.graph_objects as go

# Calcola traiettorie preset on-the-fly
preset_paths = {nome: _project(d0, i, g, sp, HORIZON) for nome, i, g, sp in SCEN_PRESETS}

fig = go.Figure()

# Preset (tratteggiati, opachi)
for nome, i, g, sp in SCEN_PRESETS:
    fig.add_trace(go.Scatter(
        x=years,
        y=preset_paths[nome],
        name=nome.replace("_", " ").title(),
        line={"color": SCEN_COLORS.get(nome, "#95a5a6"), "width": 1.5, "dash": "dot"},
        opacity=0.5,
    ))

# Custom (solido, spesso)
path_custom = _project(d0, i_custom, g_custom, sp_custom, HORIZON)
fig.add_trace(go.Scatter(
    x=years,
    y=path_custom,
    name="Custom",
    line={"color": "#2c3e50", "width": 3},
))

fig.add_hline(y=60, line_dash="dash", line_color="red", opacity=0.3, annotation_text="Maastricht 60%")
fig.update_layout(
    xaxis_title="Anno",
    yaxis_title="Debito/PIL %",
    height=450,
    margin={"t": 20},
    legend={"orientation": "h", "yanchor": "bottom", "y": -0.25},
)
st.plotly_chart(fig, width="stretch")

# Tabella riepilogativa
import pandas as pd

rows = []
for nome, i, g, sp in SCEN_PRESETS:
    traj = preset_paths[nome]
    rows.append({
        "Scenario": nome.replace("_", " ").title(),
        "i %": f"{i:.2f}",
        "g %": f"{g:.2f}",
        "sp %": f"{sp:+.1f}",
        "Start": f"{traj[0]:.1f}%",
        "End": f"{traj[-1]:.1f}%",
        "Δ": f"{traj[-1] - traj[0]:+.1f} pp",
    })
rows.append({
    "Scenario": "Custom",
    "i %": f"{i_custom:.2f}",
    "g %": f"{g_custom:.2f}",
    "sp %": f"{sp_custom:+.1f}",
    "Start": f"{path_custom[0]:.1f}%",
    "End": f"{path_custom[-1]:.1f}%",
    "Δ": f"{path_custom[-1] - path_custom[0]:+.1f} pp",
})

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

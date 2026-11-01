"""Panoramica — Control room del debito pubblico italiano.

Sezione 1: Status Board (KPI con soglie)
Sezione 2: Affidabilità dei dati (riconciliazione cross-fonte)
Sezione 3: Profilo temporale (scadenze 12 anni + top ISIN)
Sezione 4: What-if scenari (slider interattivi)
"""

from pathlib import Path

import pandas as pd
import streamlit as st
from sources import load_rollover, load_scadenze, load_serie_storiche

ROOT = Path(__file__).resolve().parent.parent.parent
RECON_DIR = ROOT / "data" / "reconcile"
SIGNALS_CSV = ROOT / "data" / "signals" / "signals.csv"

# Nome nel contratto signals.csv -> chiave usata in questa pagina.
CHIAVI = {
    "debito_totale_ap_mln_eur": "debito_ap",
    "debito_pil_pct": "debito_pil",
    "debito_pil_variazione_pp": "debito_pil_delta",
    "rendimento_10y_pct": "rendimento_10y",
    "spread_btp_bund_pp": "spread",
    "spesa_interessi_pil_pct": "interessi_pil",
    "saldo_primario_pil_pct": "saldo_pil",
    "rollover_12m_pct": "rollover_12m",
    "vita_media_anni": "vita_media",
    "quota_banca_italia_pct": "banca_italia_pct",
    "tasso_implicito_pct": "tasso_implicito",
}

st.set_page_config(page_title="Debito Pubblico · Dashboard", page_icon="🇮🇹", layout="wide")

# ═══════════════════════════════════════════════════════════════════
# SEZIONE 1 — STATUS BOARD
# ═══════════════════════════════════════════════════════════════════


@st.cache_data(ttl=3600, show_spinner=False)
def _load_signals():
    """KPI da data/signals/signals.csv, scritto da scripts/signals.py.

    La pagina non ricalcola i numeri: un KPI assente è meglio di un KPI
    calcolato con una formula leggermente diversa da quella dei mart.
    Restituisce (valori, data_riferimento_piu_recente).
    """
    if not SIGNALS_CSV.exists():
        return {}, None
    df = pd.read_csv(SIGNALS_CSV)
    valori = dict(zip(df["segnale"], df["valore"]))
    aggiornato = str(df["data_riferimento"].max()) if "data_riferimento" in df else None
    return {k: valori[n] for n, k in CHIAVI.items() if n in valori}, aggiornato


sig, aggiornato = _load_signals()

st.title("🇮🇹 Debito Pubblico Italiano")
st.caption(
    f"Dati al {aggiornato or 'n/d'} · Fonti: Banca d'Italia, Eurostat, OCPI, MEF Tesoro"
)

if not sig:
    st.warning("Segnali non disponibili. Esegui `make all` (o `make signals`) per generarli.")
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
                    st.dataframe(pd.read_csv(f), width='stretch', hide_index=True)
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
        df_scad = load_rollover().head(12)

        if not df_scad.empty:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_scad["anno_scadenza"].astype(str),
                y=df_scad["scadenza_mln_eur"],
                marker_color="#1f77b4",
                text=df_scad["scadenza_mln_eur"].apply(lambda x: f"€{x:,.0f}"),
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
        df_scad = load_scadenze()
        df_scad = df_scad[
            (df_scad["classe_strumento"] == "Titoli di Stato")
            & (df_scad["stato"] == "in_circolazione")
        ]
        df_isin = df_scad.nlargest(10, "circolante_nom_eur")[
            ["isin", "tipo", "circolante_nom_eur"]
        ].copy()
        df_isin["mln"] = (df_isin["circolante_nom_eur"] / 1e6).round(0).astype("int64")
        df_isin = df_isin[["isin", "tipo", "mln"]]
        if not df_isin.empty:
            st.dataframe(df_isin, width='stretch', hide_index=True)
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


# Base: ultimo OCPI per debito/PIL e crescita nominale
try:
    df_serie = load_serie_storiche()
    df_base = df_serie[df_serie["serie"] == "D"].sort_values("anno").tail(1)
    anno_base = int(df_base.iloc[0]["anno"])
    d0 = float(df_base.iloc[0]["valore"])
    df_o = df_serie[df_serie["serie"] == "O"].sort_values("anno").tail(1)
    g_base = float(df_o.iloc[0]["valore"]) if not df_o.empty else 2.5
except Exception:
    anno_base, d0, g_base = 2024, 137.0, 2.5

# Baseline dai dati, non da costanti: i = tasso implicito OCPI, sp = saldo primario.
# I preset sono differenze rispetto a questa base, così invecchiano con i dati.
i_base = float(sig.get("tasso_implicito", 2.9))
sp_base = float(sig.get("saldo_pil", 0.7))

HORIZON = 5

SCEN_PRESETS = [
    ("stato_attuale", i_base, g_base, sp_base),
    ("crescita_forte", i_base, g_base + 1.0, sp_base),
    ("crescita_debole", i_base, max(g_base - 1.5, 0.0), sp_base),
    ("tassi_alti", i_base + 0.6, g_base, sp_base),
    ("avanzo_primario_2", i_base, g_base, 2.0),
    ("avanzo_primario_3", i_base, g_base, 3.0),
    ("stress", i_base + 0.6, max(g_base - 1.5, 0.0), 0.0),
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

st.caption(
    f"Baseline dai dati ({anno_base}): i = {i_base:.2f}% (tasso implicito OCPI), "
    f"g = {g_base:.2f}% (crescita nominale), sp = {sp_base:+.1f}% PIL (saldo primario)."
)

# Slider
col1, col2, col3 = st.columns(3)
with col1:
    i_custom = st.slider("Tasso interesse (i) %", 0.0, 8.0, round(i_base, 2), 0.01)
with col2:
    g_custom = st.slider("Crescita nominale (g) %", 0.0, 8.0, round(g_base, 2), 0.01)
with col3:
    sp_custom = st.slider("Saldo primario (sp) % PIL", -5.0, 5.0, round(sp_base, 1), 0.1)

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

st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

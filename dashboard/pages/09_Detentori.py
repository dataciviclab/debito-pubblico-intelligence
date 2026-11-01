"""Chi detiene il debito — la mappa dei creditori dello Stato, 1988-oggi."""

import pandas as pd
import streamlit as st
from sources import load_detentori

st.title("🏛️ Chi detiene il debito")

DETENTORI = {
    "S13.MGD.S121": "Banca d'Italia",
    "S13.MGD.S12BI1": "Banche (IFM)",
    "S13.MGD.S12BI2": "Altre istituzioni finanziarie",
    "S13.MGD.S2": "Non residenti",
    "S13.MGD.SBI1": "Altri residenti",
}
TOTALE = "S13.MGD.SBI3"

df = load_detentori()

if df.empty:
    st.warning("Mart detentori non disponibile. Esegui `make run-all`.")
    st.stop()

df["data"] = pd.to_datetime(df["data"])
tot = (
    df[df["codice"] == TOTALE][["data", "valore_mln_eur"]]
    .rename(columns={"valore_mln_eur": "totale"})
)
quote = df[df["codice"].isin(DETENTORI)].merge(tot, on="data", how="left")
quote["quota"] = quote["valore_mln_eur"] / quote["totale"] * 100
pivot = quote.pivot_table(index="data", columns="codice", values="quota").sort_index()

# gli ultimi mesi arrivano con un lag diverso per categoria: si usa l'ultima
# data in cui sono presenti tutte, invece di mostrare zeri dove manca il dato.
complete = pivot.dropna(how="any")
if complete.empty:
    st.warning("Serie detentori non allineate: nessun mese completo.")
    st.stop()

ultimo = complete.iloc[-1]
data_ultima = complete.index[-1]

# ── KPI ───────────────────────────────────────────────────────────
st.caption(f"Quote sul debito delle Amministrazioni Pubbliche al {data_ultima:%m/%Y}")

cols = st.columns(4)
for col, codice in zip(cols, ("S13.MGD.S2", "S13.MGD.S121", "S13.MGD.S12BI1", "S13.MGD.SBI1")):
    col.metric(DETENTORI[codice], f"{ultimo[codice]:.1f}%")

# ── Serie storica ─────────────────────────────────────────────────
st.subheader("Come è cambiata la proprietà del debito")

inizio = pivot["S13.MGD.S2"].first_valid_index()
serie = pivot.loc[inizio:]
serie = serie.rename(columns=DETENTORI)

try:
    import plotly.graph_objects as go

    fig = go.Figure()
    for nome in serie.columns:
        fig.add_trace(go.Scatter(x=serie.index, y=serie[nome], name=nome, line={"width": 2}))
    fig.update_layout(
        yaxis_title="Quota del debito (%)",
        xaxis_title="Mese",
        height=450,
        legend={"orientation": "h", "y": -0.25},
        margin={"t": 20},
    )
    st.plotly_chart(fig, width="stretch")
except ImportError:
    st.line_chart(serie)

# ── Confronto con dieci anni fa ───────────────────────────────────
st.subheader("Chi ha comprato, chi ha venduto")

dieci = complete.index[complete.index <= data_ultima - pd.DateOffset(years=10)]
if len(dieci):
    prima = complete.loc[dieci[-1]]
    variazione = pd.DataFrame({
        "Detentore": [DETENTORI[c] for c in DETENTORI],
        "Quota oggi %": [round(ultimo[c], 1) for c in DETENTORI],
        f"Quota {dieci[-1]:%Y} %": [round(prima[c], 1) for c in DETENTORI],
        "Variazione pp": [round(ultimo[c] - prima[c], 1) for c in DETENTORI],
    }).sort_values("Variazione pp")
    st.dataframe(variazione, width="stretch", hide_index=True)

    picco_bdi = pivot["S13.MGD.S121"].dropna()
    if not picco_bdi.empty:
        st.caption(
            f"La Banca d'Italia è arrivata al **{picco_bdi.max():.1f}%** "
            f"({picco_bdi.idxmax():%m/%Y}) e ora è al {ultimo['S13.MGD.S121']:.1f}%."
        )

st.caption("""
**Metodo.** Quote calcolate sul debito lordo delle AP (`S13.MGD.SBI3`) alla stessa data.
Le serie dei detentori partono dal 1988 e non tutte sono aggiornate allo stesso mese:
il confronto usa l'ultima data in cui sono presenti tutte le voci.
Fonte: Banca d'Italia, FPI (tavola TCCE0200).
""")

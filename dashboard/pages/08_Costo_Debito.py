"""Costo del debito — quanto ci costa averlo e quanto costerà rinnovarlo."""

import streamlit as st
from sources import load_debt_service, load_rendimento_10y

st.title("💸 Costo del debito")

# ── Dati (compose debt_service) ───────────────────────────────────
interessi = load_debt_service("mart_interessi_annui")
service = load_debt_service("mart_debt_service_12m")

if interessi.empty and service.empty:
    st.warning("Mart del costo del debito non disponibili. Esegui `make compose`.")
    st.stop()

# ── Riferimenti di mercato ────────────────────────────────────────
try:
    rend = load_rendimento_10y()
    rend = rend[rend["paese"] == "IT"].sort_values("mese").tail(1)
    rendimento_10y = float(rend.iloc[0]["rendimento_pct"])
    mese_rend = str(rend.iloc[0]["mese"])[:7]
except Exception:
    rendimento_10y, mese_rend = None, None

tot_interessi = interessi["interessi_mln_eur"].sum() / 1000 if not interessi.empty else 0
tot_rimborsi = service["rimborsi_mln_eur"].sum() / 1000 if not service.empty else 0
tot_delta = service["delta_interessi_mln_eur"].sum() / 1000 if not service.empty else 0
cedola_media = (
    (interessi["cedola_ponderata_pct"] * interessi["stock_mln_eur"]).sum()
    / interessi["stock_mln_eur"].sum()
    if not interessi.empty
    else None
)

data_ref = None
for df in (interessi, service):
    if not df.empty and "data_ref" in df.columns:
        data_ref = str(df["data_ref"].max())[:10]

st.caption(f"Titoli in circolazione al {data_ref or 'n/d'} · tassi correnti al {mese_rend or 'n/d'}")

# ── KPI ───────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Interessi annui", f"€ {tot_interessi:,.1f} mld",
          help="Stima sui titoli di Stato in circolazione")
c2.metric("In scadenza 12 mesi", f"€ {tot_rimborsi:,.0f} mld")
c3.metric("Costo del rifinanziamento", f"+{tot_delta:,.1f} mld/anno",
          delta=f"+{tot_delta / tot_interessi * 100:,.0f}% sugli interessi" if tot_interessi else None,
          delta_color="inverse",
          help="Costo annuo aggiuntivo a regime, rifinanziando ai tassi correnti")
if rendimento_10y is not None and cedola_media is not None:
    c4.metric("Cedola media vs 10Y", f"{cedola_media:.2f}% → {rendimento_10y:.2f}%",
              delta=f"{rendimento_10y - cedola_media:+.2f} pp",
              delta_color="inverse",
              help="Il debito nuovo costa più del vecchio: il rialzo entra piano, con i rinnovi")

st.divider()

# ── Interessi per famiglia ────────────────────────────────────────
st.subheader("Dove si paga: interessi per famiglia di strumento")

if not interessi.empty:
    df = interessi.sort_values("interessi_mln_eur", ascending=False).copy()
    df["mld"] = (df["interessi_mln_eur"] / 1000).round(2)
    df["quota_pct"] = (df["interessi_mln_eur"] / df["interessi_mln_eur"].sum() * 100).round(1)
    st.dataframe(
        df[["famiglia", "n_titoli", "stock_mln_eur", "cedola_ponderata_pct",
            "tasso_usato_pct", "mld", "quota_pct"]].rename(columns={
            "famiglia": "Famiglia",
            "n_titoli": "Titoli",
            "stock_mln_eur": "Stock (mln €)",
            "cedola_ponderata_pct": "Cedola %",
            "tasso_usato_pct": "Tasso usato %",
            "mld": "Interessi (mld €)",
            "quota_pct": "Quota %",
        }),
        width="stretch",
        hide_index=True,
    )
else:
    st.info("Nessun dato di interessi disponibile.")

st.divider()

# ── Rifinanziamento 12 mesi ───────────────────────────────────────
st.subheader("Cosa scade e quanto costerà rifinanziarlo")

if not service.empty:
    df = service.sort_values("rimborsi_mln_eur", ascending=False).copy()
    df["rimborsi_mld"] = (df["rimborsi_mln_eur"] / 1000).round(1)
    df["delta_mld"] = (df["delta_interessi_mln_eur"] / 1000).round(2)
    st.dataframe(
        df[["famiglia", "n_titoli", "rimborsi_mld", "cedola_media_pct",
            "tasso_corrente_pct", "delta_mld"]].rename(columns={
            "famiglia": "Famiglia",
            "n_titoli": "Titoli",
            "rimborsi_mld": "Rimborsi 12m (mld €)",
            "cedola_media_pct": "Cedola storica %",
            "tasso_corrente_pct": "Tasso corrente %",
            "delta_mld": "Costo aggiuntivo (mld €/anno)",
        }),
        width="stretch",
        hide_index=True,
    )
else:
    st.info("Nessun titolo in scadenza nei prossimi 12 mesi.")

# ── Ipotesi (dai dati, non dal codice) ────────────────────────────
with st.expander("Come sono calcolati questi numeri (ipotesi dichiarate nei mart)"):
    for titolo, df in (("Interessi annui", interessi), ("Rifinanziamento 12m", service)):
        if df.empty:
            continue
        st.markdown(f"**{titolo}**")
        for _, r in df.iterrows():
            st.markdown(f"- *{r['famiglia']}*: {r['ipotesi']}")

st.caption("""
**Dati vs assunzioni.** Stock, cedole e scadenze vengono dal file MEF dei titoli
(30/09/2026). I tassi "correnti" sono dati di mercato, tranne dove la fonte non
esiste: i BOT non hanno cedola (il costo è lo sconto, approssimato col tasso a 12
mesi), i CCTeu sono a tasso variabile (Euribor 6m + spread), i BTP€i pagano una
cedola reale sul capitale rivalutato. Il costo del rifinanziamento è un
**run-rate**: nell'anno di transizione l'effetto è circa la metà.
""")

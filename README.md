# Debito Pubblico Intelligence

**Quanto debito ha davvero lo Stato italiano? Le fonti ufficiali raccontano la stessa storia?**

Sistema di intelligence sul debito pubblico italiano: raccoglie le fonti ufficiali,
le riconcilia tra loro e trasforma i dati in segnali. Non è un aggregatore — è uno
strumento che rileva quando i numeri "non tornano" e perché, e che simula cosa
succederebbe al debito se le condizioni cambiassero.

- **Copertura:** Italia, serie dal 1861 (Banca d'Italia FPI, mensile)
- **Unità di analisi:** Amministrazioni Pubbliche, sottosettori, strumenti, detentori
- **Dashboard:** [dcl-debito-pubblico.streamlit.app](https://dcl-debito-pubblico.streamlit.app/)

## Cosa risponde

**Le fonti ufficiali sul debito pubblico italiano (Banca d'Italia, Eurostat, MEF,
OCPI) sono coerenti tra loro? E cosa ci dicono sulla sostenibilità del debito?**

Il cuore del sistema è il **fusion layer**: lo stesso numero — il debito dello Stato —
viene letto da fonti indipendenti e confrontato. Se tutti dicono la stessa cifra, il
dato è affidabile. Se divergono, il sistema accende un allarme e va a capire perché:
spesso è una differenza legittima di definizione, a volte è un errore vero nei dati.

Esempi di cosa il sistema ha già rilevato:
- **165 anni di storia**: Banca d'Italia e OCPI raccontano lo stesso debito, al decimale.
- **Anomalia 1995**: Eurostat diverge dal 1995 — spiegata come cambio di definizione
  (notifiche EDP), non errore.
- **Doppio conteggio trovato e corretto**: il file scadenze del Tesoro elenca ogni
  titolo una volta per tranche; un parser ingenuo li somma due volte. Il fusion layer
  l'ha scovato (~53 mld di differenza) e il parser è stato corretto.
- **Costo del debito a bilancio**: gli oneri pagati dal bilancio dello Stato (BDAP)
  superano gli interessi misurati dall'OCPI di ~10-18 mld/anno. È un indicatore di
  scostamento tra costo "vero" a bilancio e stima interessi — la voce BDAP è più
  larga (include spese di emissione e voci di cassa) e si basa su previsioni, non
  su consuntivo.

## Dashboard

La dashboard Streamlit è la pagina pubblica del progetto. La home page (**Panorama**)
unisce in un'unica vista:

1. **Status board** — 9 KPI con soglie calibrate (debito/PIL, rendimento 10Y, spread, interessi, saldo primario, rollover, vita media, debito AP, Bd'Italia)
2. **Affidabilità dati** — 8 riconciliazioni cross-fonte (FPI vs Eurostat, FPI vs OCPI, MEF vs FPI, fabbisogno vs stock, oneri BDAP vs OCPI, consuntivo vs OCPI, accensione vs fabbisogno)
3. **Profilo temporale** — scadenze 12 anni + top 10 ISIN in circolazione
4. **Scenari di sostenibilità** — slider interattivi per i, g, sp con 7 preset + scenario custom

Le altre pagine: Spread BTP-Bund, Composizione titoli, Scadenze dettagliate, Trend Storico (1861–oggi), Flussi Banca d'Italia, Query SQL.

```bash
cd dashboard && streamlit run app.py
```

## I segnali (cosa osserviamo)

Il sistema accende spie su cinque dimensioni, tutte da dati ufficiali:

| Segnale | Cosa misura | Stato recente |
|---|---|---|
| **Debito / PIL** | dimensione del debito rispetto alla produzione annuale | ~137% |
| **i−g** | quanto il debito cresce *da solo* (interessi meno crescita) | appena sopra zero |
| **Saldo primario** | lo Stato incassa più di quanto spende (senza interessi) | positivo, di poco |
| **Rollover 12m** | quanto debito va rimborsato entro 12 mesi | ~360 mld (12,7%) |
| **Spread BTP-Bund** | quanto il mercato ci fa pagare in più della Germania | ~0,8 pp |

## Come funziona

```
toolkit (fetch→clean→mart) → reconcile → dashboard
```

```bash
make run-all          # toolkit: fetch/clean/mart per tutti i dataset
make reconcile        # fusion layer: riconciliazione cross-fonte + summary.json
make test             # pytest: verifica integrità layer
```

**Toolkit** — i dataset Eurostat, FPI, OCPI, MEF sono gestiti da `datasets/*/dataset.yml`:
ogni dataset definisce source → clean SQL → mart SQL. Il toolkit produce parquet in `out/data/`.

**Fusion layer** — `scripts/reconcile.py` confronta le fonti tra loro e produce:
- CSV dettagliati in `data/reconcile/` (per-anno, per-mese)
- `data/reconcile/summary.json` (riepilogo per la dashboard)

**Dashboard** — legge direttamente dai mart (KPI, scadenze, ISIN) e da `summary.json`
(riconciliazioni). Gli scenari sono calcolati on-the-fly.

**BDAP** — `scripts/bdap.py` legge da dataset GCS esterni (entrate/spese Stato,
consuntivo pagamenti) e produce CSV per il fusion layer.

## Fonti

| Fonte | Cosa fornisce |
|---|---|
| Banca d'Italia — BDS FPI | debito AP per sottosettore/strumento/detentore, fabbisogno, scadenze (mensile) |
| Eurostat — `gov_10dd_edpt1` | debito/PIL e stock in milioni di euro (standard Maastricht/EDP) |
| Eurostat — `irt_lt_mcby_m` | rendimento a lungo termine (10Y), Italia e Germania |
| OCPI (Università Cattolica) | 26 serie storiche 1861-2025 (debito, PIL, i−g, saldo primario, interessi) |
| MEF — Dipartimento del Tesoro | composizione e scadenze dei titoli di Stato (ISIN-level), vita media |
| BDAP Stato (MEF-RGS) | entrate e spese dello Stato per titolo/missione/macroaggregato (via catalogo GCS) |

Tutte le fonti sono pubbliche e verificabili.

## Trasparenza e limiti

- Ogni numero è riconducibile alla fonte: il sistema non inventa nulla, normalizza e confronta.
- Le fonti ufficiali a volte cambiano layout o definizioni: il sistema lo segnala,
  non lo nasconde. Le differenze tra fonti possono essere legittime (perimetro,
  valutazione) — il fusion layer le rende esplicite.
- Gli scenari sono esercizi di sensibilità, non previsioni.

## Riferimenti

- Banca d'Italia BDS — [pubblicazione FPI](https://www.bancaditalia.it/statistiche/tematiche/conti-pubblici/dp-pa/)
- MEF Dipartimento del Tesoro — [dati statistici](https://www.dt.mef.gov.it/it/debito_pubblico/dati_statistici/)

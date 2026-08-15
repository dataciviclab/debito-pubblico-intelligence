# Debito Pubblico Intelligence

**Quanto debito ha davvero lo Stato italiano? Le fonti ufficiali raccontano la stessa storia?**

Sistema di intelligence sul debito pubblico italiano: raccoglie le fonti ufficiali,
le riconcilia tra loro e trasforma i dati in segnali — non un aggregatore, ma uno
strumento che rileva quando i numeri "non tornano" e perché.

- **Stato:** bootstrap (2026-08-15)
- **Copertura:** Italia, serie dal 1861 (FPI mensile)
- **Unità di analisi:** Amministrazioni Pubbliche, sottosettori, strumenti, detentori

## La domanda civica

**Le fonti ufficiali sul debito pubblico italiano (Banca d'Italia, MEF, Eurostat,
ISTAT) sono coerenti tra loro? E cosa ci dicono sulla sostenibilità del debito?**

Questa repo risponde con un **fusion layer**: il debito visto da ogni fonte viene
allineato su definizioni esplicite e i delta oltre soglia diventano anomalie da
investigare. È ciò che distingue intelligence da aggregazione.

## Fonti

| Fonte | Cosa | Protocollo | Stato |
|---|---|---|---|
| Banca d'Italia BDS — FPI | debito AP per sottosettore/strumento/detentore, fabbisogno, scadenze | CSV/ZIP | ✅ integrato |
| Eurostat — gov_10dd_edpt1 | debito/PIL e stock debito in MIO_EUR (standard Maastricht/EDP) | SDMX JSON | ✅ integrato |
| Eurostat — irt_lt_mcby_m | rendimento riferimento lungo termine (10Y), mensile | SDMX JSON | ✅ integrato |
| OCPI (Osservatorio Conti Pubblici) | 26 serie storiche 1861-2025 (debito, PIL, i-g, saldo primario) | XLSX | ✅ integrato |
| MEF / Dipartimento del Tesoro | composizione, scadenze ISIN, titoli 12m, vita media (CSV mensili) | CSV | ✅ integrato |

## Pipeline

```
fetch -> normalize -> mart -> reconcile -> signals
```

```bash
make all        # pipeline completa: fetch + normalize + mart + reconcile + signals + panorama + test
make fpi        # solo download Banca d'Italia FPI
make mart       # rebuild mart (comando quotidiano)
make reconcile  # fusion layer
make panorama   # deliverable: data/reporting/panorama.md + .json
python3 test_smoke.py  # verifica integrità layer
```

## Layer dati

| Layer | File | Contenuto |
|---|---|---|
| Raw | `data/raw/fpi_all.csv`, `eurostat_*.csv`, `ocpi_serie_storiche.csv`, `mef_*.csv` | fonti scaricate |
| Build | `data/build/fpi_long.csv`, `data/build/mef_scadenze.parquet` | source-level normalizzato |
| Mart | `data/mart/debt_fatti.parquet` | unica fonte per le query debito |
| Reconcile | `data/reconcile/reconcile_*.csv` | delta cross-fonte (4 casi) |
| Signals | `data/signals/signals.csv` | segnali con soglie |
| Reporting | `data/reporting/panorama.md` + `.json` | deliverable pubblico |

## Contratto dati

Il mart `debt_fatti` ha granularità **data x tavola x codice** con colonne:
`data`, `tavola`, `codice`, `descrizione`, `valore_mln_eur`, `fonte`.

Codici chiave Banca d'Italia FPI:
- `S13.MGD` — debito lordo Amministrazioni Pubbliche (tavola TCCE0225)
- `S1311`/`S1313`/`S1314` — sottosettori (centrale, locale, enti previdenza)
- `F3` / `F4` — strumenti: titoli / prestiti

### Profilo scadenze (ISIN-level, MEF Tesoro)

`data/build/mef_scadenze.parquet`: 1 riga per titolo/tranche con `isin`, `tipo`,
`emissione`, `scadenza`, `cedola_pct`, `valuta`, `circolante_riv_eur`,
`circolante_nom_eur`, `data_ref`. Include titoli esteri (GLOBAL/EMTN), SURE e
NGEU. Query: `queries/04_profilo_scadenze.sql` (per anno) e
`queries/05_rollover_12m.sql` (quota in scadenza a 12 mesi).

Layer MEF aggiuntivi: `data/build/mef_titoli_12m.parquet` (per mese x tipologia,
file ufficiale) e `data/build/mef_vita_media.parquet` (serie mensile vita media).

## Fusion layer (il cuore)

**Stato:** tre casi attivi — FPI vs Eurostat, FPI vs OCPI, MEF vs FPI.

Riconciliazione implementata:
1. **FPI (dicembre, mln EUR)** vs **Eurostat stock MIO_EUR (annuale)** — stesso
   concetto (debito lordo AP, S13). Delta % con soglia 2%.
2. **FPI vs OCPI** (serie C "Debito") — stessa definizione Maastricht.
3. **MEF Tesoro titoli vs FPI titoli AP (F3)** — i titoli di Stato emessi dal
   Tesoro rispetto a tutti i titoli delle AP.
4. **MEF "titoli 12m" ufficiale vs rollover ISIN-level** — due file della stessa
   fonte: verifica del parser + perimetro.

Esiti:
- FPI vs Eurostat: **31 anni (1995-2025), 1 anomalia** (1995, -7% — spiegata,
  divergenza di definizione transitoria all'avvio delle notifiche EDP).
- FPI vs OCPI: **165 anni (1861-2025), 0 anomalie** — due fonti indipendenti
  (Banca d'Italia vs OCPI che combina ISTAT/FMI/AMECO) allineate al decimale.
- MEF vs FPI: **101,1%** (giu-2026) — il Tesoro emette praticamente tutti i titoli
  delle AP. 244 ISIN in circolazione (detail file scadenze).
- Titoli-12m ufficiale vs ISIN: **8/12 mesi identici, 4 divergono** (+53 mld —
  da investigare, probabile disallineamento di valutazione; vedi note).

Ogni delta oltre soglia diventa una **anomalia da investigare**, non un errore.

## Limiti

- Il parser MEF è fragile: i file ufficiali del Tesoro cambiano layout. Il formato
  cella-per-riga permette di recuperare dati anche quando il parser finale richiede fix.
- Definizioni diverse tra fonti sono legittime: il fusion layer le rende esplicite,
  non le nasconde.

## Riferimenti

- `_local/notes/current/NOTE_bankitalia_fpi_2026-07-04.md` — esplorazione FPI precedente
- Issue dataset-incubator #620 — intake FPI (mai evasa)
- [NazarenoLecis/Debito_pubblico_italiano](https://github.com/NazarenoLecis/Debito_pubblico_italiano) — pipeline di riferimento

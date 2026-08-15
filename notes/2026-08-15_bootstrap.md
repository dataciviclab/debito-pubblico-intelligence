# Debito Pubblico Intelligence — bootstrap

Data: 2026-08-15
Stato: prima sessione — scaffold e primo fetch dati

## Cosa è stato fatto

1. **Scaffold repo** `debito-pubblico-intelligence/` seguendo il pattern di
   `opere-pubbliche-intelligence` (pipeline.py single entry, Makefile, mart
   parquet, queries/ SQL, test_smoke.py).
2. **Step fetch FPI funzionante**: riusa la logica di `_local/scripts/fpi/download_and_extract.py`
   (nota: quello script scriveva in `raw/fpi_all.csv`; ora nel repo → `data/raw/fpi_all.csv`).
3. **Step normalize/mart/reconcile/signals** scaffoldati. Reconcile = fusion layer
   (il cuore), ancora vuoto.

## Decisioni bootstrap

- **Dominio**: debito pubblico italiano, intelligence multi-fonte. NON un semplice
  aggregatore: il valore sta nel fusion layer (delta cross-fonte = anomalie).
- **Contratto mart**: `debt_fatti.parquet` con colonne
  `data, tavola, codice, descrizione, valore_mln_eur, fonte`.
- **Fonti prioritarie**: FPI (✅), Eurostat gov_10dd_edpt1 + irt_lt_mcby_m (SDMX),
  MEF Tesoro, OCPI. Il debito locale (SIOPE/OpenBDAP) è out of scope iniziale.
- **Riuso memoria**: FPI era già stato esplorato (NOTE_bankitalia_fpi_2026-07-04),
  issue #620 mai evasa. Non si riapre l'intake: il valore qui è l'intelligence
  cross-fonte, non i 2 dataset territoriali.

## Esito bootstrap dati (stessa sessione)

- **fetch FPI**: OK — 116.833 righe, 9 tavole, serie 1861-12 → 2026-06.
- **mart `debt_fatti.parquet`**: OK — 116.833 righe, 1 fonte.
- **segnali**: debito AP totale (S13.MGD) giu-2026 = **3.207.247 mln EUR** (~3,21 trilioni),
  variazione m/m **+0,82%**. Serie m/m in crescita (mar→giu: 3.158→3.207 mld).
- **Codici reali tavola `debito_ap_sottosettori`**: `S13.MGD` (totale AP),
  `S1311.MGD` (centrali), `S1313.MGD` (locali), `S1314.MGD` (enti previdenza).
  Nota: nel mart il nome tavola è la forma normalizzata (`debito_ap_sottosettori`),
  non la descrizione originale — segnale corretto di conseguenza.
- **Smoke test**: verde.

## Next action

- [x] Verificare download FPI reale e generare primo mart (`make fpi mart test`) — DONE
- [x] Calibrare codici reali FPI nel signals.py (S13.MGD verificato sui dati veri) — DONE
- [x] Eurostat SDMX: gov_10dd_edpt1 (debito/PIL) come prima fonte di riconciliazione — DONE
- [x] Primo reconcile: FPI mensile vs Eurostat trimestrale → delta oltre soglia — DONE
- [ ] Investigare anomalia 1995 (delta -7% FPI vs Eurostat, probabile revisione storica)
- [ ] Eurostat irt_lt_mcby_m (rendimento 10Y) per segnale costo/rendimento
- [ ] OCPI serie lunghe (i-g) — file già in /tmp/ocpi_serie_storiche.xlsx
- [ ] Decide se registrare fonte in source-observatory

## Fusion layer (aggiornamento)

- **fetch Eurostat integrato** (SDMX JSON, decoder generalizzato multi-dimensione):
  `eurostat_gov10dd.csv` (debito/PIL per settore), `eurostat_gov10dd_stock.csv`
  (stock MIO_EUR), `eurostat_irt_lt_mcby.csv` (rendimento 10Y mensile 1980-2026).
- **fetch OCPI integrato**: `ocpi_serie_storiche.csv` (26 serie, 1861-2025, 4.439 celle).
  Scoperta: serie C "Debito" allineata a FPI al decimale; serie S (i-g) disponibile.
- **reconcile.py con 2 casi attivi**:
  - FPI vs Eurostat (31 anni, 1995-2025): 1 anomalia (1995, -7% — spiegata, vedi `2026-08-15_anomalia_1995.md`).
  - FPI vs OCPI (165 anni, 1861-2025): **0 anomalie**, delta 2025 = -0,01%.
- **signals.py esteso**: rendimento 10Y (3,88% lug-2026), costo interesse implicito
  (~124 mld EUR/anno da 10Y x stock).
- **Fix nel percorso**: decoder Eurostat generalizzato (dimensione `unit`);
  ordinamento esplicito in reconcile; fetch OCPI con cache xlsx + estrazione CSV.

## Lezione chiave (fusion layer)

Il primo valore tangibile: **FPI e OCPI convergono per 165 anni** — due catene di
produzione dati indipendenti (Banca d'Italia vs OCPI che combina ISTAT/FMI/AMECO)
raccontano la stessa storia al decimale. Il fusion layer quindi *conferma* la
coerenza dello stock di debito. L'anomalia 1995 (solo vs Eurostat) è l'esempio
perfetto di come il sistema distingua "anomalia da definizione" (spiegabile) da
"anomalia da errore".

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
- **fetch MEF Tesoro integrato**: `mef_composizione.csv` (titoli per tipologia, mln EUR)
  e `mef_scadenze.csv` (ISIN-level: emissione, scadenza, cedola, circolante). Selezione
  dell'ultimo file per data (nome file datato, mese in italiano). Encoding latin-1.
- **reconcile.py con 3 casi attivi**:
  - FPI vs Eurostat (31 anni, 1995-2025): 1 anomalia (1995, -7% — spiegata, vedi `2026-08-15_anomalia_1995.md`).
  - FPI vs OCPI (165 anni, 1861-2025): **0 anomalie**, delta 2025 = -0,01%.
  - MEF vs FPI (giu-2026): **101,1%** — il Tesoro emette quasi tutti i titoli AP. 244 ISIN.
- **signals.py riscritto**: registro di 7 segnali con soglie e categorie
  (debito, costo, sostenibilità). Include debito/PIL (137,1%), i-g (+0,35pp),
  saldo primario (+0,7%), spesa interessi (3,8%), rendimento 10Y (3,88%).

## Profilo scadenze / rollover (aggiornamento)

- **normalize_mef**: `data/build/mef_scadenze.parquet` (515 titoli/tranche, 267 ISIN).
  Include BTP/BOT/CCT + titoli esteri (GLOBAL, EMTN), SURE e NGEU. Date parse,
  cedola estratta, `data_ref` dal header.
- **nuovi layer MEF**: `mef_titoli_12m.parquet` (per mese x tipologia, file ufficiale),
  `mef_vita_media.parquet` (serie mensile vita media residua).
- **Query**: `04_profilo_scadenze.sql` (per anno), `05_rollover_12m.sql`.
- **Profilo**: picchi 2027 (444 mld), 2028 (370), 2031 (339), 2033 (233);
  coda lunga fino al 2072.
- **Rollover 12m**: **419 mld EUR = 10,7%** del residuo (sotto soglia 15%).
- **Caso reconcile 4**: MEF titoli-12m ufficiale vs nostro ISIN → 8/12 mesi
  identici, 4 divergono (+53 mld). Anomalia documentata
  (`2026-08-15_anomalia_rollover_12m.md`): probabile disallineamento di
  valutazione nominale/rivalutato tra i due file MEF.
- **Signals**: 10 segnali (aggiunti vita media 7,0 anni).

## Quadro intelligence (primo quadro completo)

Lo stock di debito è coerente cross-fonte (FPI=Eurostat=OCPI); i titoli Tesoro
coprono il 101% dei titoli AP. I segnali di sostenibilità raccontano una situazione
di attenzione ma non allarmante: debito/PIL alto (137%), i-g appena positivo
(il debito cresce da solo ma di poco), saldo primario positivo (+0,7%), costo
implicito ~124 mld/anno, rollover 12m 10,7%, vita media 7 anni.

## Lezione chiave (fusion layer)

Il primo valore tangibile: **FPI e OCPI convergono per 165 anni** — due catene di
produzione dati indipendenti (Banca d'Italia vs OCPI che combina ISTAT/FMI/AMECO)
raccontano la stessa storia al decimale. Il fusion layer quindi *conferma* la
coerenza dello stock di debito. L'anomalia 1995 (solo vs Eurostat) è l'esempio
perfetto di come il sistema distingua "anomalia da definizione" (spiegabile) da
"anomalia da errore".

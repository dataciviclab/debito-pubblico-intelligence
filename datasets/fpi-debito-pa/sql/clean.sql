-- clean.sql: FPI Banca d'Italia — Finanza Pubblica Italia
--
-- raw_input schema: data, tavola, tavola_nome, codice, controparte, descrizione, valore_mln_eur, fonte
-- Delimiter: ;
--
-- Il CSV è già in formato long/tidy dal preprocess. Il clean passa tutto
-- così com'è (niente trasformazione), ma DuckDB profila i tipi e il toolkit
-- valida required_columns e not_null.
--
-- ATTENZIONE (prima di sommare): la stessa voce può comparire in PIÙ TAVOLE con
-- lo stesso valore. Esempio: S1313.MGD / SBI3 = 74,4 mld sia in TCCE0225
-- (sottosettori) sia in TCCE0250 (amm. locali per comparti) sia in TCCE0275
-- (amm. locali per aree). Sommare il clean senza filtrare `tavola` triplica il
-- numero. I mart filtrano per tavola; le query ad hoc devono farlo a mano.
--
-- Restano inoltre 31 casi di (tavola, codice, controparte, data) duplicati su
-- TCCE0125 (voce S13.FAB, 2 righe a fine anno): dimensione di fonte non ancora
-- identificata, su una voce che non entra nei KPI.

SELECT
    data,
    tavola,
    tavola_nome,
    codice,
    controparte,
    descrizione,
    cast(valore_mln_eur AS double) AS valore_mln_eur,
    fonte
FROM raw_input

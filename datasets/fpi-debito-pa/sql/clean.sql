-- clean.sql: FPI Banca d'Italia — Finanza Pubblica Italia
--
-- raw_input schema: data, tavola, tavola_nome, codice, descrizione, valore_mln_eur, fonte
-- Delimiter: ;
--
-- Il CSV è già in formato long/tidy dal preprocess. Il clean passa tutto
-- così com'è (niente trasformazione), ma DuckDB profila i tipi e il toolkit
-- valida required_columns e not_null.

SELECT
    data,
    tavola,
    tavola_nome,
    codice,
    descrizione,
    cast(valore_mln_eur AS double) AS valore_mln_eur,
    fonte
FROM raw_input

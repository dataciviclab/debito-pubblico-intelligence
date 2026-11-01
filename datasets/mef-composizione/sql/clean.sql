-- clean.sql: MEF Composizione Titoli di Stato — serie mensile
--
-- raw_input (da preprocess.py): data_ref, tipologia, famiglia, colonna,
--   valore_mln_eur, sottoinsieme (S/N), aggregato (S/N)
--
-- Serie lunga: una riga per (mese, tipologia). La dashboard usa solo
-- colonna = 'mln. Euro'; la colonna % resta nel raw ma non arriva al mart.
--
-- Due flag da rispettare quando si somma:
--   sottoinsieme = S  -> voci "di cui ..." (incluse nel totale)
--   aggregato    = S  -> "Totale", "Estero", "Altri programmi di emissione":
--                        contengono righe presenti separatamente

SELECT
    cast(data_ref AS date) AS data_ref,
    tipologia,
    famiglia,
    colonna,
    cast(valore_mln_eur AS double) AS valore_mln_eur,
    sottoinsieme = 'S' AS sottoinsieme,
    aggregato = 'S' AS aggregato
FROM raw_input

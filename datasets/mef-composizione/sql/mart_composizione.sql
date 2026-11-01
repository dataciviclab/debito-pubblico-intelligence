-- mart_composizione.sql: composizione dei titoli di Stato per mese
--
-- Una riga per (data_ref, tipologia). Solo la colonna in mln di euro: la
-- percentuale e' derivabile e averla nel mart romperebbe la chiave.
--
-- Per lo stock del mese corrente:  WHERE data_ref = (SELECT max(data_ref) ...)
-- Per aggregare per famiglia:      WHERE NOT sottoinsieme AND NOT aggregato
--                                  ("di cui ..." e' contenuto nel totale,
--                                   "Totale"/"Estero"/"Altri programmi" sono
--                                   contenitori di righe presenti a parte)

SELECT
    data_ref,
    tipologia,
    famiglia,
    valore_mln_eur,
    sottoinsieme,
    aggregato
FROM clean_input
WHERE colonna = 'mln. Euro'
ORDER BY data_ref, tipologia

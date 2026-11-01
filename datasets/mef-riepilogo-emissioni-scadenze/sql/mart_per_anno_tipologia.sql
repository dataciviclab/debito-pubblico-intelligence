-- mart_per_anno_tipologia.sql
-- Totali emissioni/scadenze per anno × tipologia, valori in mln di euro.
--
-- `totale_mln_segnato` conserva il segno (SCADENZE negative): la somma delle due
-- sezioni di un anno e' l'emissione netta in titoli.
-- `totale_mln` e' il valore assoluto, utile per confrontare i volumi.
--
-- `n_isin` conta solo gli identificativi reali: per gli anni aggregati
-- (2020-2024) il MEF pubblica una riga sola con `isin = 'AGGREGATO'`, che non
-- e' un titolo e non va contato.

SELECT
    anno,
    tipologia,
    sezione,
    min(grano) AS grano,
    COUNT(*) AS n_righe,
    COUNT(DISTINCT isin) FILTER (WHERE grano = 'isin') AS n_isin,
    ROUND(SUM(importo_mln), 1) AS totale_mln_segnato,
    ROUND(SUM(importo_abs_mln), 1) AS totale_mln
FROM clean_input
WHERE importo_abs_mln IS NOT NULL
GROUP BY anno, tipologia, sezione
ORDER BY anno, tipologia, sezione

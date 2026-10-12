-- mart_per_anno_tipologia.sql
-- Totali emissioni/scadenze per anno × tipologia (valori assoluti).

SELECT
    anno,
    tipologia,
    sezione,
    COUNT(*) AS n_righe,
    COUNT(DISTINCT isin) AS n_isin,
    ROUND(SUM(importo_mld), 1) AS totale_mld_segnato,
    ROUND(SUM(importo_abs_mld), 1) AS totale_mld
FROM clean_input
WHERE importo_abs_mld IS NOT NULL
GROUP BY anno, tipologia, sezione
ORDER BY anno, tipologia, sezione

-- Rollover risk: quota di debito in scadenza nei prossimi 12 mesi
-- vs totale in scadenza residuo. Più alto = più rifinanziamento necessario.
WITH totale AS (
    SELECT sum(circolante_nom_eur) AS tot
    FROM read_parquet('data/build/mef_scadenze.parquet')
    WHERE scadenza >= data_ref
),
rollover AS (
    SELECT sum(circolante_nom_eur) AS r12
    FROM read_parquet('data/build/mef_scadenze.parquet')
    WHERE scadenza >= data_ref AND scadenza < date_add(data_ref, INTERVAL 12 MONTH)
)
SELECT round(r12 / 1e6, 0) AS rollover_12m_mln_eur,
       round(tot / 1e6, 0) AS totale_scadenze_mln_eur,
       round(r12 / tot * 100, 1) AS rollover_pct
FROM totale, rollover;

-- mart_rollover_12m.sql: Profilo scadenze e calcolo rollover 12 mesi
--
-- Raggruppa il circolante per anno di scadenza e calcola la quota
-- in scadenza nei prossimi 12 mesi rispetto al totale residuo.
-- Usato da signals (rollover_12m) e panorama (profilo scadenze).

WITH base AS (
    SELECT *,
        cast(year(scadenza) AS integer) AS anno_scadenza,
        cast(year(data_ref) AS integer) AS anno_ref
    FROM clean_input
    WHERE scadenza >= data_ref
),
per_anno AS (
    SELECT
        anno_scadenza,
        anno_ref,
        count(*) AS n_titoli,
        round(sum(circolante_nom_eur) / 1e6, 0) AS scadenza_mln_eur,
        round(sum(circolante_nom_eur) / 1e9, 1) AS scadenza_mld_eur
    FROM base
    GROUP BY 1, 2
),
totale AS (
    SELECT anno_ref, sum(scadenza_mln_eur) AS tot_mln FROM per_anno GROUP BY 1
)
SELECT
    pa.anno_scadenza,
    pa.n_titoli,
    pa.scadenza_mln_eur,
    pa.scadenza_mld_eur,
    round(pa.scadenza_mln_eur / t.tot_mln * 100, 1) AS quota_pct,
    CASE WHEN pa.anno_scadenza <= pa.anno_ref + 1 THEN 'SI' ELSE 'no' END AS in_rollover_12m
FROM per_anno pa JOIN totale t USING (anno_ref)
ORDER BY pa.anno_scadenza

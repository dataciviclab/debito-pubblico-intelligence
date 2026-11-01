-- mart_rollover_12m.sql: Profilo scadenze e calcolo rollover 12 mesi
--
-- Raggruppa il circolante per anno di scadenza e calcola la quota
-- in scadenza nei prossimi 12 mesi rispetto al totale residuo.
-- Usato da signals (rollover_12m) e panorama (profilo scadenze).
--
-- Filtri obbligatori (vedi clean.sql):
--   - solo titoli di Stato: i prestiti UE SURE/NGEU non sono debito in titoli;
--   - solo debito in circolazione: le scadenze gia' passate alla data_ref
--     restano nel mart_scadenze_isin per il rollover realizzato, ma non qui.
-- Prima di questo filtro il totale di riferimento era 3.199,7 mld invece di
-- 2.683,6 (+19%), quindi tutte le quote erano sottostimate.
--
-- `in_rollover_12m` = l'anno di scadenza inizia entro 365 giorni dalla data_ref
-- (finestra mobile, non "anno_ref + 1" di calendario).

WITH base AS (
    SELECT *,
        cast(year(scadenza) AS integer) AS anno_scadenza,
        cast(year(data_ref) AS integer) AS anno_ref,
        scadenza <= data_ref + INTERVAL 365 DAY AS in_12m
    FROM clean_input
    WHERE scadenza >= data_ref
      AND classe_strumento = 'Titoli di Stato'
      AND stato = 'in_circolazione'
),
per_anno AS (
    SELECT
        anno_scadenza,
        anno_ref,
        count(*) AS n_titoli,
        round(sum(circolante_nom_eur) / 1e6, 0) AS scadenza_mln_eur,
        round(sum(circolante_nom_eur) / 1e9, 1) AS scadenza_mld_eur,
        round(sum(CASE WHEN in_12m THEN circolante_nom_eur ELSE 0 END) / 1e6, 0) AS scadenza_12m_mln_eur,
        bool_or(in_12m) AS in_12m,
        max(data_ref) AS data_ref
    FROM base
    GROUP BY 1, 2
),
totale AS (
    SELECT anno_ref, sum(scadenza_mln_eur) AS tot_mln, max(data_ref) AS data_ref
    FROM per_anno GROUP BY 1
)
SELECT
    pa.anno_scadenza,
    pa.n_titoli,
    pa.scadenza_mln_eur,
    pa.scadenza_mld_eur,
    pa.scadenza_12m_mln_eur,
    round(pa.scadenza_mln_eur / t.tot_mln * 100, 1) AS quota_pct,
    CASE WHEN pa.in_12m THEN 'SI' ELSE 'no' END AS in_rollover_12m,
    t.data_ref
FROM per_anno pa JOIN totale t USING (anno_ref)
ORDER BY pa.anno_scadenza

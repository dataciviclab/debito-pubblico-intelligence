-- mart_debt_service_12m.sql — costo di rifinanziare i titoli in scadenza
--
-- Grano: famiglia di strumento, solo titoli con scadenza entro 365 giorni
-- dalla data di riferimento.
--
-- Logica: i titoli che scadono oggi hanno una cedola storica (spesso bassa,
-- emessi quando i tassi erano più bassi). Rifinanziarli al tasso corrente
-- cambia il costo. `delta_interessi_mln_eur` = rimborsi x (corrente - storica).
--
-- Ipotesi di tasso di rifinanziamento (colonna `ipotesi`):
--   BOT        -> tasso a 12 mesi
--   CCTeu      -> Euribor 6m + spread contrattuale
--   altri BTP  -> rendimento 10Y (conservativo sulle scadenze brevi: un BTP
--                 Short a 2 anni renderebbe meno del 10Y)

WITH scad AS (
    SELECT * FROM read_parquet('{support.scadenze.path}' || '/*/mart_scadenze_isin.parquet')
    WHERE classe_strumento = 'Titoli di Stato'
      AND stato = 'in_circolazione'
      AND circolante_nom_eur > 0
      AND scadenza <= data_ref + INTERVAL 365 DAY
),
tassi AS (
    SELECT scadenza_mesi, tasso_pct
    FROM read_parquet('{support.tassi.path}' || '/*/mart_tassi_breve.parquet')
    WHERE mese = (
        SELECT max(mese) FROM read_parquet('{support.tassi.path}' || '/*/mart_tassi_breve.parquet')
    )
),
curva AS (
    SELECT
        max(CASE WHEN scadenza_mesi = 6 THEN tasso_pct END) AS tasso_6m,
        max(CASE WHEN scadenza_mesi = 12 THEN tasso_pct END) AS tasso_12m
    FROM tassi
),
btp10 AS (
    SELECT rendimento_pct AS tasso_10y
    FROM read_parquet('{support.rendimento.path}' || '/*/mart_rendimento_10y.parquet')
    WHERE paese = 'IT'
    ORDER BY mese DESC
    LIMIT 1
),
per_famiglia AS (
    SELECT
        tipo_famiglia AS famiglia,
        count(*) AS n_titoli,
        sum(circolante_nom_eur) / 1e6 AS rimborsi_mln_eur,
        sum(coalesce(cedola_pct, 0) * circolante_nom_eur) / NULLIF(sum(circolante_nom_eur), 0) AS cedola_media_pct,
        max(data_ref) AS data_ref
    FROM scad
    GROUP BY 1
)
SELECT
    p.famiglia,
    p.n_titoli,
    round(p.rimborsi_mln_eur, 1) AS rimborsi_mln_eur,
    round(p.cedola_media_pct, 2) AS cedola_media_pct,
    round(
        CASE
            WHEN p.famiglia = 'BOT' THEN c.tasso_12m
            WHEN p.famiglia = 'CCTeu' THEN c.tasso_6m + coalesce(p.cedola_media_pct, 0)
            ELSE b.tasso_10y
        END, 2
    ) AS tasso_corrente_pct,
    round(
        p.rimborsi_mln_eur *
        (
            CASE
                WHEN p.famiglia = 'BOT' THEN c.tasso_12m
                WHEN p.famiglia = 'CCTeu' THEN c.tasso_6m + coalesce(p.cedola_media_pct, 0)
                ELSE b.tasso_10y
            END - coalesce(p.cedola_media_pct, 0)
        ) / 100, 1
    ) AS delta_interessi_mln_eur,
    CASE
        WHEN p.famiglia = 'BOT' THEN 'tasso 12m (Euribor 12m) come proxy del rendimento di riemissione'
        WHEN p.famiglia = 'CCTeu' THEN 'Euribor 6m + spread contrattuale'
        ELSE 'rendimento BTP 10Y (conservativo: le scadenze brevi rendono meno)'
    END AS ipotesi,
    p.data_ref
FROM per_famiglia p
CROSS JOIN curva c
CROSS JOIN btp10 b
ORDER BY p.rimborsi_mln_eur DESC

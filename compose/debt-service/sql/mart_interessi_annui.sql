-- mart_interessi_annui.sql — costo annuo del debito in titoli, per famiglia
--
-- Grano: famiglia di strumento. Una riga per famiglia + totale? No: il totale
-- si ricava sommando (le famiglie sono partizione dello stock).
--
-- Ipotesi dichiarate in colonna `ipotesi`, non nel codice:
--   BOT    -> tasso a 12 mesi (proxy del rendimento, il BOT è zero coupon
--             e il costo è lo sconto di emissione)
--   CCTeu  -> Euribor 6m + spread contrattuale (il file MEF riporta solo lo spread)
--   altri  -> cedola contrattuale (per i BTP€i è la cedola reale: prudente,
--             esclude la rivalutazione futura del capitale)

WITH scad AS (
    SELECT * FROM read_parquet('{support.scadenze.path}' || '/*/mart_scadenze_isin.parquet')
    WHERE classe_strumento = 'Titoli di Stato'
      AND stato = 'in_circolazione'
      AND circolante_nom_eur > 0
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
per_famiglia AS (
    SELECT
        tipo_famiglia AS famiglia,
        count(*) AS n_titoli,
        sum(circolante_nom_eur) / 1e6 AS stock_mln_eur,
        avg(cedola_pct) AS cedola_media_pct,
        sum(cedola_pct * circolante_nom_eur) / NULLIF(sum(CASE WHEN cedola_pct IS NOT NULL THEN circolante_nom_eur ELSE 0 END), 0) AS cedola_ponderata_pct,
        max(data_ref) AS data_ref
    FROM scad
    GROUP BY 1
)
SELECT
    p.famiglia,
    p.n_titoli,
    round(p.stock_mln_eur, 1) AS stock_mln_eur,
    round(p.cedola_media_pct, 2) AS cedola_media_pct,
    round(p.cedola_ponderata_pct, 2) AS cedola_ponderata_pct,
    round(
        CASE
            WHEN p.famiglia = 'BOT' THEN c.tasso_12m
            WHEN p.famiglia = 'CCTeu' THEN c.tasso_6m + coalesce(p.cedola_ponderata_pct, 0)
            ELSE p.cedola_ponderata_pct
        END, 2
    ) AS tasso_usato_pct,
    round(
        p.stock_mln_eur *
        CASE
            WHEN p.famiglia = 'BOT' THEN c.tasso_12m
            WHEN p.famiglia = 'CCTeu' THEN c.tasso_6m + coalesce(p.cedola_ponderata_pct, 0)
            ELSE coalesce(p.cedola_ponderata_pct, 0)
        END / 100, 1
    ) AS interessi_mln_eur,
    CASE
        WHEN p.famiglia = 'BOT' THEN 'tasso 12m (Euribor 12m) come proxy del rendimento: zero coupon, il costo è lo sconto'
        WHEN p.famiglia = 'CCTeu' THEN 'Euribor 6m + spread contrattuale'
        ELSE 'cedola contrattuale (BTP€i: cedola reale, esclusa la rivalutazione futura)'
    END AS ipotesi,
    p.data_ref
FROM per_famiglia p
CROSS JOIN curva c
ORDER BY interessi_mln_eur DESC

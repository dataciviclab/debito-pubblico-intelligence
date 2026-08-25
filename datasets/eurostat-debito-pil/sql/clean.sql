-- clean.sql: Eurostat gov_10dd_edpt1 — Government debt (Maastricht/EDP)
--
-- raw_input schema: freq, unit, sector, na_item, geo, year, value, flag
-- Pivot: ogni (year, sector) ha 2 righe (PC_GDP e MIO_EUR) → 2 colonne.

SELECT
    cast(year AS int) AS anno,
    sector AS settore,
    max(CASE WHEN unit = 'PC_GDP' THEN cast(value AS double) END) AS debito_pil_pct,
    max(CASE WHEN unit = 'MIO_EUR' THEN cast(value AS double) END) AS stock_mln_eur
FROM raw_input
WHERE na_item = 'GD'
  AND freq = 'A'
  AND geo = 'IT'
  AND year IS NOT NULL
  AND unit IN ('PC_GDP', 'MIO_EUR')
GROUP BY year, sector

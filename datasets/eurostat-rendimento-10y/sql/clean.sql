-- clean.sql: Eurostat irt_lt_mcby_m — Long-term interest rates (10Y)
--
-- raw_input schema: freq, int_rt, geo, year, month, value, flag
-- Due fonti (IT + DE) con identico schema, combinate in raw_input.
-- Output: mese (YYYY-MM), paese, rendimento_pct.

SELECT
    printf('%04d-%02d', cast(year AS int), cast(month AS int)) AS mese,
    geo AS paese,
    cast(value AS double) AS rendimento_pct
FROM raw_input
WHERE year IS NOT NULL
  AND month IS NOT NULL
  AND value IS NOT NULL
ORDER BY year, month, geo

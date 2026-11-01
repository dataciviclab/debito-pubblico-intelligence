-- clean.sql: Eurostat irt_st_m — tassi del mercato monetario (area euro)
--
-- raw_input: freq, int_rt, geo, year, month, value, flag
-- La fonte parte dal 1970 ma i valori esistono solo da fine anni '90 (euro).
-- `int_rt` codifica la scadenza: IRT_M3 → 3, IRT_M6 → 6, IRT_M12 → 12.

SELECT
    make_date(cast(year AS int), cast(month AS int), 1) AS mese,
    cast(replace(int_rt, 'IRT_M', '') AS int) AS scadenza_mesi,
    cast(value AS double) AS tasso_pct
FROM raw_input
WHERE value IS NOT NULL
  AND month IS NOT NULL
  AND year IS NOT NULL

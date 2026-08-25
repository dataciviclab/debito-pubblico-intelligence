-- mart_rendimento_10y.sql: Rendimento 10Y mensile Italia e Germania
--
-- La clean produce già la granularità giusta: 1 riga per (mese, paese).

SELECT
    mese,
    paese,
    rendimento_pct
FROM clean_input
ORDER BY mese, paese

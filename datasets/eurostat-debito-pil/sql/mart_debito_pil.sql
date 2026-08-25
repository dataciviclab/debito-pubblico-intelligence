-- mart_debito_pil.sql: Debito/PIL e stock per sottosettore S13 (Maastricht)
--
-- La clean produce già la granularità giusta: 1 riga per (anno, settore).

SELECT
    anno,
    settore,
    debito_pil_pct,
    stock_mln_eur
FROM clean_input
ORDER BY anno, settore

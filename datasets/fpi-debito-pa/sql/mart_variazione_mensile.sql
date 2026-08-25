-- mart_variazione_mensile.sql: Variazione m/m del debito totale AP (S13.MGD)
--
-- Window function: calcola la variazione percentuale mese su mese.
-- Usato da signals (debito_totale_ap_mm_pct) e panorama.

WITH serie AS (
    SELECT
        data,
        valore_mln_eur,
        lag(valore_mln_eur) OVER (ORDER BY data) AS prev
    FROM clean_input
    WHERE tavola_nome = 'debito_ap_sottosettori'
      AND codice = 'S13.MGD'
)
SELECT
    data,
    valore_mln_eur,
    prev,
    round((valore_mln_eur - prev) / prev * 100, 2) AS delta_pct
FROM serie
ORDER BY data

-- mart_debito_ap.sql: Debito AP per sottosettori e strumenti
--
-- Le tavole principali: TCCE0175 (strumenti), TCCE0225 (sottosettori),
-- TCCE0250/TCCE0275 (amm. locali). Copre il 90% delle query analitiche.
--
-- Uso: signals (debito_totale_ap), reconcile (FPI vs Eurostat/OCPI),
-- panorama (quadro d'insieme).

SELECT
    data,
    tavola,
    tavola_nome,
    codice,
    descrizione,
    valore_mln_eur
FROM clean_input
WHERE tavola IN ('TCCE0175', 'TCCE0225', 'TCCE0250', 'TCCE0275')
ORDER BY data, tavola, codice

-- mart_fabbisogno.sql: Fabbisogno AP per strumenti
--
-- TCCE0125: fabbisogno mensile per strumento (sottosettore).
-- Usato da reconcile caso 5 (fabbisogno vs variazione stock).

SELECT
    data,
    tavola,
    tavola_nome,
    codice,
    descrizione,
    valore_mln_eur
FROM clean_input
WHERE tavola = 'TCCE0125'
ORDER BY data, codice

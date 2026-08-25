-- mart_detentori.sql: Debito AP per detentori
--
-- TCCE0200: detenzione del debito per settore.detentore (es. S13.MGD.S121 = Bd'It).
-- Usato da signals (quota Banca d'Italia) e panorama.

SELECT
    data,
    tavola,
    tavola_nome,
    codice,
    descrizione,
    valore_mln_eur
FROM clean_input
WHERE tavola = 'TCCE0200'
ORDER BY data, codice

-- mart_liquidita.sql — Depositi e liquidità delle AP (tavola TCCE0300)
--
-- ATTENZIONE alla natura: i codici F2/F22OP/F2BI1 sono FLUSSI (variazioni del
-- mese), gli altri (F22DI, F22FA, F2BI3) sono consistenze. La colonna `natura`
-- lo dichiara: sommare i due gruppi non ha senso.
-- La stessa voce può avere più controparti (controparte): per il totale vale
-- SBI3, le altre sono viste parziali.

SELECT
    data,
    codice,
    controparte,
    descrizione,
    CASE
        WHEN codice IN ('S13.F2', 'S13.F22OP', 'S13.F2BI1', 'S1311.F4') THEN 'flusso'
        ELSE 'consistenza'
    END AS natura,
    valore_mln_eur AS valore
FROM clean_input
WHERE tavola = 'TCCE0300'
ORDER BY data, codice

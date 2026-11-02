-- mart_vita_residua.sql — Debito AP per fascia di vita residua (tavola TCCE0325)
--
-- È l'unica vista del debito AP *intero* per scadenza: il rollover dei titoli
-- del Tesoro (mef_scadenze_isin) copre solo una parte delle passività.
--
-- ATTENZIONE unità: S13.MGD10 è la vita media residua in ANNI, non in euro.
-- Per questo c'è la colonna `unita`: sommarlo agli altri codici è un errore.
-- Le fasce MGD05/06/07 partizionano il debito (somma = debito AP); MGD08/09
-- sono sottoinsiemi a tasso variabile e non vanno sommati alle fasce.

SELECT
    data,
    codice,
    descrizione,
    CASE
        WHEN codice = 'S13.MGD05' THEN '<= 1 anno'
        WHEN codice = 'S13.MGD06' THEN '1-5 anni'
        WHEN codice = 'S13.MGD07' THEN '> 5 anni'
        WHEN codice = 'S13.MGD08' THEN 'tasso variabile, 1-5 anni'
        WHEN codice = 'S13.MGD09' THEN 'tasso variabile, > 5 anni'
        WHEN codice = 'S13.MGD10' THEN 'vita media residua'
        ELSE 'altro'
    END AS fascia,
    CASE
        WHEN codice = 'S13.MGD10' THEN 'anni'
        ELSE 'mln_eur'
    END AS unita,
    valore_mln_eur AS valore
FROM clean_input
WHERE tavola = 'TCCE0325'
ORDER BY data, codice

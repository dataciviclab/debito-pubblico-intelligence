-- mart_valuta.sql — Debito AP per valuta e scadenza originaria (tavola TCCE0350)
--
-- Tutti i valori sono in mln di euro. `dimensione` raggruppa i codici in tre
-- letture: valuta (euro / estero), scadenza originaria (breve / oltre 1 anno)
-- e strumento (titoli, prestiti, depositi). Le voci non sono esaustive tra
-- loro: non sommare dimensioni diverse.

SELECT
    data,
    codice,
    controparte,
    descrizione,
    CASE
        WHEN codice = 'S13.MGD11' THEN 'valuta: euro'
        WHEN codice = 'S13.MGD04' THEN 'valuta: estera'
        WHEN codice = 'S13.MGD14' THEN 'scadenza: breve termine'
        WHEN codice = 'S13.MGD01' THEN 'scadenza: oltre 1 anno'
        WHEN codice LIKE 'S13.F32%' THEN 'strumento: titoli m/l'
        WHEN codice LIKE 'S13.F42%' THEN 'strumento: prestiti m/l'
        WHEN codice LIKE 'S13.F2R%' THEN 'strumento: depositi'
        ELSE 'altro'
    END AS dimensione,
    valore_mln_eur AS valore
FROM clean_input
WHERE tavola = 'TCCE0350'
ORDER BY data, codice

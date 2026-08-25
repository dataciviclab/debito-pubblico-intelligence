-- mart_scadenze_isin.sql: Titoli di Stato scadenze ISIN-level
--
-- Usato da:
--   signals: rollover_12m (calcolo dal circolante in scadenza 12m)
--   reconcile: titoli-12m vs calcolo ISIN
--   panorama: profilo scadenze e top ISIN

SELECT
    isin,
    tipo,
    emissione,
    scadenza,
    cedola_pct,
    valuta,
    circolante_riv_eur,
    circolante_nom_eur,
    data_ref
FROM clean_input
ORDER BY scadenza, isin

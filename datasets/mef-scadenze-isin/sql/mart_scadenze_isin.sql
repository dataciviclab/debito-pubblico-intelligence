-- mart_scadenze_isin.sql: Titoli di Stato scadenze ISIN-level
--
-- Usato da:
--   signals: rollover_12m (calcolo dal circolante in scadenza 12m)
--   reconcile: titoli-12m vs calcolo ISIN
--   panorama: profilo scadenze e top ISIN
--
-- Contiene TUTTE le righe della fonte (titoli di Stato, prestiti UE, scadenze
-- passate) per non perdere informazione. Chi aggrega lo stock DEVE filtrare:
--   classe_strumento = 'Titoli di Stato' AND stato = 'in_circolazione'

SELECT
    isin,
    tipo,
    tipo_famiglia,
    emissione,
    scadenza,
    cedola_pct,
    valuta,
    circolante_riv_eur,
    circolante_nom_eur,
    data_ref,
    classe_strumento,
    stato
FROM clean_input
ORDER BY scadenza, isin

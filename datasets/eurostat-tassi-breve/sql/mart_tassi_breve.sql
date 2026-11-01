-- mart_tassi_breve.sql: tassi monetari area euro per mese e scadenza
--
-- Una riga per (mese, scadenza_mesi). Usato dal calcolo del costo del debito:
--   BOT  → tasso a 12 mesi come proxy del rendimento di emissione
--   CCTeu → tasso a 6 mesi + spread (il file MEF riporta solo lo spread)

SELECT
    mese,
    scadenza_mesi,
    tasso_pct
FROM clean_input
ORDER BY mese, scadenza_mesi

-- mart_serie_storiche.sql: OCPI 26 serie storiche 1861-2025
--
-- La clean produce gia' la granularita' giusta: 1 riga per (serie, anno).
-- Questa vista e' usata da:
--   signals: i_g (serie S), saldo_primario (serie G), spesa_interessi (serie I),
--            debito_pil (serie D)
--   scenarios: debito/PIL base per proiezioni
--   reconcile: FPI vs OCPI (serie C "Debito")

SELECT
    serie,
    nome,
    unita,
    anno,
    valore
FROM clean_input
ORDER BY serie, anno

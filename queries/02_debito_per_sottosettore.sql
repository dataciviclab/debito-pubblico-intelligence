-- Debito per sottosettore: ultimo mese disponibile
-- NB: la tavola ha un livello "controparte" (SBI3 totale, SBI4, S13BI1...)
-- che il decoder collassa in un unico codice; max() restituisce il totale.
SELECT codice, descrizione, round(max(valore_mln_eur), 0) AS valore_mln_eur
FROM read_parquet('data/mart/debt_fatti.parquet')
WHERE tavola = 'debito_ap_sottosettori'
  AND data = (SELECT max(data) FROM read_parquet('data/mart/debt_fatti.parquet')
              WHERE tavola = 'debito_ap_sottosettori')
GROUP BY codice, descrizione
ORDER BY max(valore_mln_eur) DESC;

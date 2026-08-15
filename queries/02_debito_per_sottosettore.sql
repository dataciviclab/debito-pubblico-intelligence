-- Debito per sottosettore: ultimo mese disponibile
SELECT codice, descrizione, valore_mln_eur
FROM read_parquet('data/mart/debt_fatti.parquet')
WHERE tavola = 'Debito AP per sottosettori'
  AND data = (SELECT max(data) FROM read_parquet('data/mart/debt_fatti.parquet')
              WHERE tavola = 'Debito AP per sottosettori')
ORDER BY valore_mln_eur DESC;

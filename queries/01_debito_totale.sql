-- Debito totale AP nel tempo (serie mensile, mln EUR)
SELECT data, valore_mln_eur
FROM read_parquet('data/mart/debt_fatti.parquet')
WHERE tavola = 'Debito AP per sottosettori'
  AND codice = 'S13.MGD'
ORDER BY data;

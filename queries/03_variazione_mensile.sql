-- Variazione m/m del debito totale AP (ultimo anno)
WITH serie AS (
  SELECT data, valore_mln_eur,
         lag(valore_mln_eur) OVER (ORDER BY data) AS prev
  FROM read_parquet('data/mart/debt_fatti.parquet')
  WHERE tavola = 'debito_ap_sottosettori'
    AND codice = 'S13.MGD'
)
SELECT data, valore_mln_eur,
       round((valore_mln_eur - prev) / prev * 100, 2) AS delta_pct
FROM serie
WHERE data >= (SELECT max(data) - INTERVAL 12 MONTH FROM serie)
ORDER BY data;

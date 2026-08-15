-- Profilo scadenze: quanto debito scade per anno (in scadenza, dal data_ref)
-- Uso circolante nominale (valori non rivalutati, più conservativi)
SELECT cast(year(scadenza) AS INT) AS anno_scadenza,
       count(*) AS n_titoli,
       round(sum(circolante_nom_eur) / 1e6, 0) AS scadenza_mln_eur,
       round(sum(circolante_nom_eur) / 1e9, 1) AS scadenza_mld_eur
FROM read_parquet('data/build/mef_scadenze.parquet')
WHERE scadenza >= data_ref
GROUP BY 1
ORDER BY 1;

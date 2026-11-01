-- clean.sql — mef_riepilogo_emissioni_scadenze
-- raw_input già parsificato da preprocess.py (comma, UTF-8).
--
-- NOTA unità: la fonte dichiara "mln.€" e i valori restano in milioni. La colonna
-- si chiama `importo_mln`, non `mld`: prima il nome mentiva di 1000x e per gli
-- anni aggregati (2020-2024) il totale usciva come 181.815 "mld" invece di 181,8.
--
-- NOTA segno: nella sezione SCADENZE gli importi sono negativi (flussi in
-- uscita), sia nel formato ISIN (2025+) sia negli anni aggregati.
--
-- NOTA grano: fino al 2024 il MEF pubblica una sola riga annuale per tipologia
-- (`isin = 'AGGREGATO'`); dal 2025 una riga per ISIN. `grano` rende esplicita la
-- differenza, cosi' `n_isin` e i conteggi non confondono i due formati.
--
-- Macro toolkit: normalize_string, cast_int, cast_double.

SELECT
    cast_int(anno) AS anno,
    normalize_string(tipologia) AS tipologia,
    normalize_string(sezione) AS sezione,
    normalize_string(isin) AS isin,
    TRY_CAST(normalize_string(scadenza) AS DATE) AS scadenza,
    normalize_string(tipo_tenore) AS tipo_tenore,
    cast_double(importo_mln) AS importo_mln,
    ABS(cast_double(importo_mln)) AS importo_abs_mln,
    CASE WHEN normalize_string(isin) = 'AGGREGATO' THEN 'aggregato' ELSE 'isin' END AS grano
FROM raw_input
WHERE cast_int(anno) IS NOT NULL
  AND normalize_string(sezione) IS NOT NULL
  AND normalize_string(isin) IS NOT NULL

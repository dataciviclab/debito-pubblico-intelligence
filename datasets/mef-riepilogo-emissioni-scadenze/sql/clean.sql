-- clean.sql — mef_riepilogo_emissioni_scadenze
-- raw_input già parsificato da preprocess.py (comma, UTF-8).
--
-- NOTA fonte: nella sezione SCADENZE gli importi sono NEGATIVI
-- (flussi in uscita). Si conserva il segno + importo_abs_mld per analisi.
--
-- Macro toolkit: normalize_string, cast_int, cast_double.

SELECT
    cast_int(anno) AS anno,
    normalize_string(tipologia) AS tipologia,
    normalize_string(sezione) AS sezione,
    normalize_string(isin) AS isin,
    TRY_CAST(normalize_string(scadenza) AS DATE) AS scadenza,
    normalize_string(tipo_tenore) AS tipo_tenore,
    cast_double(importo_mld) AS importo_mld,
    ABS(cast_double(importo_mld)) AS importo_abs_mld
FROM raw_input
WHERE cast_int(anno) IS NOT NULL
  AND normalize_string(sezione) IS NOT NULL
  AND normalize_string(isin) IS NOT NULL

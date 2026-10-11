-- clean.sql — mef_riepilogo_emissioni_scadenze
-- raw_input già parsificato da preprocess.py.
--
-- NOTA fonte: nella sezione SCADENZE del CSV MEF gli importi sono
-- pubblicati NEGATIVI (flussi in uscita / rimborsi). Qui si conserva il
-- segno e si aggiunge importo_abs_mld per gli usi analitici.

SELECT
    CAST(anno AS INTEGER) AS anno,
    UPPER(TRIM(tipologia)) AS tipologia,
    UPPER(TRIM(sezione)) AS sezione,
    TRIM(isin) AS isin,
    CASE
        WHEN scadenza IS NULL OR TRIM(scadenza) = '' THEN NULL
        ELSE TRY_CAST(TRIM(scadenza) AS DATE)
    END AS scadenza,
    NULLIF(TRIM(tipo_tenore), '') AS tipo_tenore,
    CAST(importo_mld AS DOUBLE) AS importo_mld,
    ABS(CAST(importo_mld AS DOUBLE)) AS importo_abs_mld
FROM read_csv_auto(
    '/home/gabry/dev/dataciviclab-workspace/economia-finanza/debito-pubblico-intelligence/out/data/raw/mef_riepilogo_emissioni_scadenze/2026/raw_input.csv',
    header = true,
    delim = ',',
    columns = {
        'anno': 'VARCHAR',
        'tipologia': 'VARCHAR',
        'sezione': 'VARCHAR',
        'isin': 'VARCHAR',
        'scadenza': 'VARCHAR',
        'tipo_tenore': 'VARCHAR',
        'importo_mld': 'VARCHAR'
    }
)
WHERE anno IS NOT NULL
  AND sezione IS NOT NULL
  AND isin IS NOT NULL

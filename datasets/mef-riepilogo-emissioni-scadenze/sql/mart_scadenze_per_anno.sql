-- mart_scadenze_per_anno.sql
-- Dettaglio ISIN in scadenza (valori assoluti) — ponte verso BDAP 002 rimborsi.

SELECT
    anno,
    tipologia,
    isin,
    scadenza,
    tipo_tenore,
    ROUND(importo_mld, 3) AS importo_mld_segnato,
    ROUND(importo_abs_mld, 3) AS importo_mld
FROM clean_input
WHERE sezione = 'SCADENZE'
  AND isin IS NOT NULL
  AND importo_abs_mld IS NOT NULL
  AND importo_abs_mld > 0
ORDER BY anno, scadenza, tipologia, isin

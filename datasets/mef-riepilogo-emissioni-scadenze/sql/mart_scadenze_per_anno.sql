-- mart_scadenze_per_anno.sql
-- Dettaglio ISIN in scadenza (valori in mln di euro) — ponte verso BDAP 002 rimborsi.
--
-- Solo righe al grano ISIN: per il 2020-2024 il MEF pubblica solo l'aggregato
-- annuale, che vive in `mart_per_anno_tipologia`.

SELECT
    anno,
    tipologia,
    isin,
    scadenza,
    tipo_tenore,
    ROUND(importo_mln, 3) AS importo_mln_segnato,
    ROUND(importo_abs_mln, 3) AS importo_mln
FROM clean_input
WHERE sezione = 'SCADENZE'
  AND grano = 'isin'
  AND isin IS NOT NULL
  AND importo_abs_mln IS NOT NULL
  AND importo_abs_mln > 0
ORDER BY anno, scadenza, tipologia, isin

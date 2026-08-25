-- clean.sql: MEF Scadenze ISIN-level
--
-- raw_input: isin, tipo, emissione, scadenza, cedola_pct, valuta,
--            circolante_riv_eur, circolante_nom_eur, data_ref
-- Il CSV e' gia' parsificato dal preprocess. Cast dei tipi numerici.

SELECT
    isin,
    tipo,
    cast(emissione AS date) AS emissione,
    cast(scadenza AS date) AS scadenza,
    cast(cedola_pct AS double) AS cedola_pct,
    valuta,
    cast(circolante_riv_eur AS double) AS circolante_riv_eur,
    cast(circolante_nom_eur AS double) AS circolante_nom_eur,
    cast(data_ref AS date) AS data_ref
FROM raw_input

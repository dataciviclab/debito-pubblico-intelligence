-- clean.sql: MEF Scadenze ISIN-level
--
-- raw_input: isin, tipo, emissione, scadenza, cedola_pct, valuta,
--            circolante_riv_eur, circolante_nom_eur, data_ref
-- Il CSV e' gia' parsificato dal preprocess. Cast dei tipi numerici.
--
-- ATTENZIONE (fonte): la colonna "Codice ISIN" del file MEF non contiene sempre
-- un ISIN. Oltre ai titoli di Stato (IT + 10 cifre, piu' EMTN/GLOBAL in valuta)
-- elenca i prestiti europei SURE e NGEU, identificati da una descrizione
-- ("NGEU ago.2021/set.2051") e con una riga per tranche/rimborso. Non sono
-- titoli di Stato e, per i prestiti, la riga e' una quota di rimborso e non uno
-- stock: sommarli allo stock gonfia il totale di ~178 mld.
-- ATTENZIONE (tempo): il file contiene anche le scadenze gia' passate alla
-- data_ref (finestra dell'anno): valgono per il rollover realizzato, non per il
-- debito in circolazione (~342 mld a set-2026).
-- ATTENZIONE (encoding): il simbolo € arriva come byte 0x80 (cp1252 letto come
-- latin-1) e il tipo oscillava tra 'BTP\x80i' e 'BTP\x80I'.
--
-- `classe_strumento`, `tipo_famiglia` e `stato` rendono espliciti i filtri, cosi'
-- nessun consumer puo' sommare per sbaglio.

WITH base AS (
    SELECT
        isin,
        regexp_replace(replace(tipo, chr(128), '€'), '^BTP€I ', 'BTP€i ') AS tipo,
        cast(emissione AS date) AS emissione,
        cast(scadenza AS date) AS scadenza,
        cast(cedola_pct AS double) AS cedola_pct,
        valuta,
        cast(circolante_riv_eur AS double) AS circolante_riv_eur,
        cast(circolante_nom_eur AS double) AS circolante_nom_eur,
        cast(data_ref AS date) AS data_ref
    FROM raw_input
)

SELECT
    isin,
    tipo,
    emissione,
    scadenza,
    cedola_pct,
    valuta,
    circolante_riv_eur,
    circolante_nom_eur,
    data_ref,
    CASE
        WHEN starts_with(isin, 'NGEU') THEN 'Prestiti UE - NGEU'
        WHEN starts_with(isin, 'SURE') THEN 'Prestiti UE - SURE'
        WHEN regexp_matches(isin, '^IT[0-9]{10}$') THEN 'Titoli di Stato'
        WHEN tipo IN ('GLOBAL', 'EMTN', 'EUROBOND') OR starts_with(tipo, 'Ispa') THEN 'Titoli di Stato'
        ELSE 'Altro'
    END AS classe_strumento,
    CASE
        WHEN starts_with(tipo, 'BOT') THEN 'BOT'
        WHEN starts_with(tipo, 'BTP€i') THEN 'BTP€i'
        WHEN starts_with(tipo, 'BTP Italia') THEN 'BTP Italia'
        WHEN starts_with(tipo, 'BTP Futura') THEN 'BTP Futura'
        WHEN starts_with(tipo, 'BTP Valore') THEN 'BTP Valore'
        WHEN starts_with(tipo, 'BTP Più') THEN 'BTP Più'
        WHEN starts_with(lower(tipo), 'btp green') THEN 'BTP Green'
        WHEN starts_with(tipo, 'BTP Short') THEN 'BTP Short'
        WHEN starts_with(tipo, 'BTP') THEN 'BTP'
        WHEN starts_with(tipo, 'CCTeu') THEN 'CCTeu'
        WHEN starts_with(tipo, 'Ispa') THEN 'Ispa'
        WHEN tipo IN ('GLOBAL', 'EMTN', 'EUROBOND') THEN tipo
        WHEN starts_with(isin, 'NGEU') THEN 'NGEU'
        WHEN starts_with(isin, 'SURE') THEN 'SURE'
        ELSE tipo
    END AS tipo_famiglia,
    CASE
        WHEN cast(scadenza AS date) < cast(data_ref AS date) THEN 'scaduto'
        ELSE 'in_circolazione'
    END AS stato
FROM base

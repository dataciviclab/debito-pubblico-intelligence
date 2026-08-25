-- clean.sql: OCPI Serie storiche finanza pubblica
--
-- raw_input schema: serie, nome, unita, anno, valore
-- 26 serie (D=debito/PIL, S=i-g, G=saldo primario, I=interessi, C=debito stock, ...)
-- Copre 1861-2025. Il CSV e' gia' in formato long.

SELECT
    serie,
    nome,
    unita,
    cast(anno AS integer) AS anno,
    cast(valore AS double) AS valore
FROM raw_input

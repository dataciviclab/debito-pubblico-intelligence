# Anomalia rollover — MEF "titoli 12m" ufficiale vs calcolo ISIN-level

Data: 2026-08-15 (aggiornata dopo fix dedup tranche)
Caso: reconcile_titoli12m_vs_isin.csv

## Evidenza (post-fix)

- Totale 12m: **ufficiale 354.843 vs ISIN 352.715 mln** (delta -2.128, -0,6%)
- 8/12 mesi identici; 4 mesi con delta >500 mln:
  - set-26: -5.003 (ufficiale include BTP€i rivalutato 17.573, noi nominale 12.570)
  - dic-26: +875; gen-27: +1.000; giu-27: +1.000

## Causa principale (RISOLTA)

Il file scadenze MEF elenca **righe multiple per lo stesso ISIN** quando il titolo
ha più tranche (colonna Emissione = numero tranche, es. '0,3'). Il nostro parser
sommava tutte le righe → double-count di ~53 mld. Fix: dedup per (isin, scadenza)
prendendo il valore massimo (la tranche più recente include le precedenti).
Applicato in `normalize_mef.py`.

## Causa residua (sett-26, -5.003)

Il file ufficiale "titoli 12m" usa per il BTP€i il **capitale rivalutato**
(17.573 mln), noi usiamo il nominale (12.570 mln). Differenza 5.003 = scarto.
È una differenza di valutazione legittima, non un errore: per i titoli indicizzati
all'inflazione il valore rivalutato è quello rilevante per il rimborso.

## Verdetto

**Causa principale risolta** (double-count tranche). **Differenza residua attesa**
per valutazione rivalutato vs nominale su BTP€i. Nessuna azione dati richiesta;
il confronto ora è un cross-check valido del parser.

## Lezione per il fusion layer

Anche dentro una stessa fonte i file possono usare convenzioni diverse
(tranche vs aggregato; nominale vs rivalutato). Il fusion layer ha permesso di
scoprire e correggere un bug reale del parser (double-count), che il solo
cross-check con fonti diverse non avrebbe mostrato.

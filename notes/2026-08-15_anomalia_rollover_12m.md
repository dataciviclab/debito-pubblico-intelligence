# Anomalia rollover — MEF "titoli 12m" ufficiale vs calcolo ISIN-level

Data: 2026-08-15
Caso: reconcile_titoli12m_vs_isin.csv — 4/12 mesi con delta >500 mln

## Evidenza

- Totale 12m: **ufficiale 354.843 mln vs nostro ISIN 408.223 mln** (delta +53.380)
- 8/12 mesi collimano **esattamente** (parser ISIN confermato)
- 4 mesi divergono: set-26 (-5.003), dic-26 (+19.651), gen-27 (+18.863), giu-27 (+19.869)

## Diagnosi preliminare (dic-26)

| Fonte | Valore |
|---|---|
| Ufficiale BTP dic-26 | 18.777 mln |
| Nostri BTP 10 dic-26 (nominale) | 38.554 mln |
| Nostri BTP 10 dic-26 (rivalutato) | 19.777 mln |

Nota: 38.554 − 19.777 = 18.777 → la differenza coincide con la valutazione
rivalutata dei BTP. Ipotesi: disallineamento di valutazione (nominale vs
rivalutato) o classificazione per alcuni titoli nei due file MEF.

## Verdetto

**Da investigare** — non è un errore del parser (8/12 mesi identici), ma un
disallineamento di perimetro/valutazione tra i due file ufficiali MEF stessi
(scadenze ISIN vs titoli-12m). Azione: confrontare titolo-per-titolo i mesi
divergenti (identificare quali ISIN e quale valutazione usa il file ufficiale).

## Nota per il fusion layer

Due file **della stessa fonte (MEF)** non collimano al 100%: è un'ottima
conferma che il valore del sistema sta proprio nel segnalare queste discrepanze
— anche tra file ufficiali, non solo tra fonti diverse.

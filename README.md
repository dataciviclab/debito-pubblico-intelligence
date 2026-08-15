# Debito Pubblico Intelligence

**Quanto debito ha davvero lo Stato italiano? Le fonti ufficiali raccontano la stessa storia?**

Sistema di intelligence sul debito pubblico italiano: raccoglie le fonti ufficiali,
le riconcilia tra loro e trasforma i dati in segnali. Non è un aggregatore — è uno
strumento che rileva quando i numeri "non tornano" e perché, e che simula cosa
succederebbe al debito se le condizioni cambiassero.

- **Copertura:** Italia, serie dal 1861 (Banca d'Italia FPI, mensile)
- **Unità di analisi:** Amministrazioni Pubbliche, sottosettori, strumenti, detentori
- **Output pubblico:** `data/reporting/panorama.md` — un foglio riassuntivo aggiornato a ogni run

## Cosa risponde

**Le fonti ufficiali sul debito pubblico italiano (Banca d'Italia, Eurostat, MEF,
OCPI) sono coerenti tra loro? E cosa ci dicono sulla sostenibilità del debito?**

Il cuore del sistema è il **fusion layer**: lo stesso numero — il debito dello Stato —
viene letto da fonti indipendenti e confrontato. Se tutti dicono la stessa cifra, il
dato è affidabile. Se divergono, il sistema accende un allarme e va a capire perché:
spesso è una differenza legittima di definizione, a volte è un errore vero nei dati.

Esempi di cosa il sistema ha già rilevato:
- **165 anni di storia**: Banca d'Italia e OCPI raccontano lo stesso debito, al decimale.
- **Anomalia 1995**: Eurostat diverga dal 1995 — spiegata come cambio di definizione
  (notifiche EDP), non errore.
- **Doppio conteggio trovato e corretto**: il file scadenze del Tesoro elenca ogni
  titolo una volta per tranche; un parser ingenuo li somma due volte. Il fusion layer
  l'ha scovato (~53 mld di differenza) e il parser è stato corretto.

## I segnali (cosa osserviamo)

Il sistema accende spie su cinque dimensioni, tutte da dati ufficiali:

| Segnale | Cosa misura | Stato recente |
|---|---|---|
| **Debito / PIL** | dimensione del debito rispetto alla produzione annuale | ~137% |
| **i−g** | quanto il debito cresce *da solo* (interessi meno crescita) | appena sopra zero |
| **Saldo primario** | lo Stato incassa più di quanto spende (senza interessi) | positivo, di poco |
| **Rollover 12m** | quanto debito va rimborsato entro 12 mesi | ~360 mld (12,7%) |
| **Spread BTP-Bund** | quanto il mercato ci fa pagare in più della Germania | ~0,8 pp |

## Scenari di sostenibilità

Partendo dall'ultimo valore reale del debito/PIL, il sistema proietta la traiettoria
a 5 anni sotto ipotesi diverse su costo del debito (i), crescita (g) e avanzo
primario (sp), usando l'identità di sostenibilità:

```
d(t+1) = d(t)·(1+i)/(1+g) − sp
```

Risultato chiave (base 2025, 137,1%): **lo stato attuale è quasi stabile** (−1,2pp in
5 anni); la **crescita debole** (+9,7pp) e i **tassi alti** (+3pp) lo farebbero salire;
un **avanzo primario al 3%** (−12,8pp) è la leva sotto controllo politico con effetto
maggiore. Non previsioni, ma sensibilità: "cosa cambia se...".

## Fonti

| Fonte | Cosa fornisce |
|---|---|
| Banca d'Italia — BDS FPI | debito AP per sottosettore/strumento/detentore, fabbisogno, scadenze (mensile) |
| Eurostat — `gov_10dd_edpt1` | debito/PIL e stock in milioni di euro (standard Maastricht/EDP) |
| Eurostat — `irt_lt_mcby_m` | rendimento a lungo termine (10Y), Italia e Germania |
| OCPI (Università Cattolica) | 26 serie storiche 1861-2025 (debito, PIL, i−g, saldo primario, interessi) |
| MEF — Dipartimento del Tesoro | composizione e scadenze dei titoli di Stato (ISIN-level), vita media |

Tutte le fonti sono pubbliche e verificabili.

## Come funziona

```
fetch → normalize → mart → reconcile → signals → scenario → panorama
```

```bash
make all            # esegue l'intera pipeline
make panorama       # genera data/reporting/panorama.md + .json
python3 test_smoke.py   # verifica l'integrità dei layer
```

I dati sono scaricati dal web a ogni run e normalizzati in un archivio uniforme
(`data/mart/`). Il **fusion layer** confronta le fonti tra loro. I **segnali**
calcolano gli indicatori con soglie esplicite. Gli **scenari** proiettano la
traiettoria del debito/PIL. Tutto converge nel **panorama**.

## Trasparenza e limiti

- Ogni numero è riconducibile alla fonte: il sistema non inventa nulla, normalizza e confronta.
- Le fonti ufficiali a volte cambiano layout o definizioni: il sistema lo segnala,
  non lo nasconde. Le differenze tra fonti possono essere legittime (perimetro,
  valutazione) — il fusion layer le rende esplicite.
- Gli scenari sono esercizi di sensibilità, non previsioni.

## Riferimenti

- [NazarenoLecis/Debito_pubblico_italiano](https://github.com/NazarenoLecis/Debito_pubblico_italiano) — pipeline di riferimento sul parsing FPI
- Banca d'Italia BDS — [pubblicazione FPI](https://www.bancaditalia.it/statistiche/tematiche/conti-pubblici/dp-pa/)
- MEF Dipartimento del Tesoro — [dati statistici](https://www.dt.mef.gov.it/it/debito_pubblico/dati_statistici/)

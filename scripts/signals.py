#!/usr/bin/env python3
"""
Step signals: segnali con soglie calibrate sullo storico.

Segnali attivi:
  - debito_totale_ap: livello e variazione m/m del debito AP (S13.MGD, FPI)
  - rendimento_10y: ultimo rendimento e variazione m/m (Eurostat irt_lt_mcby_m)
  - debito_pil: debito/PIL ultimo anno disponibile (Eurostat gov_10dd_edpt1, PC_GDP)
  - i_g: differenziale interessi-crescita (OCPI serie S) — termometro dinamica debito
  - saldo_primario: % PIL (OCPI serie G) — capacità di ripagare senza nuovi debiti
  - spesa_interessi_pil: % PIL (OCPI serie I)

Soglie (bootstrap, da calibrare sul primo storico completo):
  - debito/PIL: > 130% alto (Italia sopra da anni) — confronto con storico
  - i-g: > 0 significa debito che cresce da solo (interessi > crescita)
  - saldo primario: < 0 significa nuovi debiti per coprire la gestione corrente

Output: data/signals/signals.csv + summary a terminale.
"""

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SIG_DIR = ROOT / "data" / "signals"

# (nome, query sorgente, descrizione) — valore atteso: numero
# ogni riga: SELECT <valore> [, <precedente>] FROM read_csv/parquet(...)
SIGNAL_QUERIES = {
    "debito_totale_ap_mln_eur": (
        "SELECT valore_mln_eur FROM read_parquet('data/mart/debt_fatti.parquet') "
        "WHERE tavola='debito_ap_sottosettori' AND codice='S13.MGD' ORDER BY data DESC LIMIT 1"
    ),
    "debito_totale_ap_mm_pct": (
        "WITH s AS (SELECT valore_mln_eur FROM read_parquet('data/mart/debt_fatti.parquet') "
        "WHERE tavola='debito_ap_sottosettori' AND codice='S13.MGD' ORDER BY data DESC LIMIT 2) "
        "SELECT (max(valore_mln_eur) - min(valore_mln_eur)) / min(valore_mln_eur) * 100 FROM s"
    ),
    "rendimento_10y_pct": (
        "SELECT rendimento_pct FROM read_csv('data/raw/eurostat_irt_lt_mcby.csv') "
        "ORDER BY mese DESC LIMIT 1"
    ),
    "debito_pil_pct": (
        "SELECT debito_pil_pct FROM read_csv('data/raw/eurostat_gov10dd.csv') "
        "WHERE settore='S13' ORDER BY anno DESC LIMIT 1"
    ),
    "i_g_pp": (
        "SELECT valore FROM read_csv('data/raw/ocpi_serie_storiche.csv') "
        "WHERE serie='S' ORDER BY anno DESC LIMIT 1"
    ),
    "saldo_primario_pil_pct": (
        "SELECT valore FROM read_csv('data/raw/ocpi_serie_storiche.csv') "
        "WHERE serie='G' ORDER BY anno DESC LIMIT 1"
    ),
    "spesa_interessi_pil_pct": (
        "SELECT valore FROM read_csv('data/raw/ocpi_serie_storiche.csv') "
        "WHERE serie='I' ORDER BY anno DESC LIMIT 1"
    ),
}

SIGNAL_META = {
    "debito_totale_ap_mln_eur": ("debito totale AP (mln EUR)", "debito", None),
    "debito_totale_ap_mm_pct": ("variazione debito m/m (%)", "debito", None),
    "rendimento_10y_pct": ("rendimento 10Y (%)", "costo", None),
    "debito_pil_pct": ("debito/PIL (%)", "sostenibilita", ">130: alto"),
    "i_g_pp": ("i-g (pp)", "sostenibilita", ">0: debito cresce da solo"),
    "saldo_primario_pil_pct": ("saldo primario (% PIL)", "sostenibilita", "<0: nuovo debito per gestione"),
    "spesa_interessi_pil_pct": ("spesa interessi (% PIL)", "sostenibilita", None),
}


def run():
    SIG_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    report = []
    for name, query in SIGNAL_QUERIES.items():
        try:
            val = con.execute(query).fetchone()
        except Exception as exc:  # fonte opzionale non disponibile
            print(f"[signals] skip {name}: {exc}")
            continue
        if val is None or val[0] is None:
            continue
        value = float(val[0])
        label, cat, soglia = SIGNAL_META[name]
        report.append({"segnale": name, "descrizione": label, "categoria": cat, "valore": round(value, 3)})
        msg = f"[signals] {label}: {value:.3f}"
        if soglia:
            msg += f"  ({soglia})"
        print(msg)

    out = SIG_DIR / "signals.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["segnale", "descrizione", "categoria", "valore"])
        w.writeheader()
        w.writerows(report)
    print(f"[signals] OK {out}: {len(report)} segnali")


if __name__ == "__main__":
    run()

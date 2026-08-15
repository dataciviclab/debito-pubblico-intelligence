#!/usr/bin/env python3
"""
Step signals: segnali con soglie calibrate sullo storico.

Segnali attivi:
  - debito_totale_ap: livello e variazione m/m del debito AP (S13.MGD)
  - rendimento_10y: ultimo rendimento e variazione m/m (Eurostat irt_lt_mcby_m)
  - costo_debito_stock: interesse implicito ~ rendimento 10Y x stock debito (ordine di grandezza)

Output: data/signals/signals.csv + summary a terminale.
"""

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
MART_DIR = ROOT / "data" / "mart"
RAW_DIR = ROOT / "data" / "raw"
SIG_DIR = ROOT / "data" / "signals"


def run():
    fatti = MART_DIR / "debt_fatti.parquet"
    rates = RAW_DIR / "eurostat_irt_lt_mcby.csv"
    if not fatti.exists():
        print("[ERRORE] mart prima dei segnali")
        sys.exit(1)

    SIG_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    rows = con.execute("""
        SELECT data, valore_mln_eur
        FROM read_parquet('data/mart/debt_fatti.parquet')
        WHERE tavola = 'debito_ap_sottosettori'
          AND codice = 'S13.MGD'
        ORDER BY data DESC
        LIMIT 13
    """).fetchall()

    if not rows:
        print("[signals] nessun dato per debito totale AP (S13.MGD) — verificare codice tavola")
        sys.exit(0)

    latest = rows[0][1]
    prev = rows[1][1] if len(rows) > 1 else None
    delta = (latest - prev) / prev * 100 if prev else None
    print(f"[signals] debito totale AP: ultimo {latest:,.0f} mln EUR")
    if delta is not None:
        print(f"[signals] variazione m/m: {delta:+.2f}%")

    if rates.exists():
        rrows = con.execute("""
            SELECT mese, rendimento_pct
            FROM read_csv('data/raw/eurostat_irt_lt_mcby.csv')
            ORDER BY mese DESC
            LIMIT 2
        """).fetchall()
        if rrows:
            r_latest, r_prev = rrows[0][1], (rrows[1][1] if len(rrows) > 1 else None)
            r_delta = r_latest - r_prev if r_prev is not None else None
            print(f"[signals] rendimento 10Y: {r_latest:.2f}% (mese {rrows[0][0]})")
            if r_delta is not None:
                print(f"[signals] variazione rendimento m/m: {r_delta:+.2f} pp")
            annual_cost = latest / 100.0 * r_latest / 1000.0
            print(f"[signals] costo interesse implicito ~ {annual_cost:,.0f} mld EUR/anno (10Y x stock)")

    # Report CSV dei segnali chiave
    report = [{
        "segnale": "debito_totale_ap_mln_eur",
        "valore": round(latest, 0),
        "variazione_mm_pct": round(delta, 2) if delta is not None else None,
    }]
    if rates.exists() and rrows:
        report.append({
            "segnale": "rendimento_10y_pct",
            "valore": r_latest,
            "variazione_mm_pp": round(r_delta, 2) if r_delta is not None else None,
        })
    out = SIG_DIR / "signals.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["segnale", "valore", "variazione_mm_pct", "variazione_mm_pp"])
        w.writeheader()
        w.writerows(report)
    print(f"[signals] OK {out}")


if __name__ == "__main__":
    run()

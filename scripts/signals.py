#!/usr/bin/env python3
"""
Step signals: segnali con soglie calibrate sullo storico.

Segnali previsti (bootstrap):
  - debito_totale_mensile: livello e variazione m/m
  - soglie iniziali da calibrare sui primi dati scaricati
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
MART_DIR = ROOT / "data" / "mart"
SIG_DIR = ROOT / "data" / "signals"


def run():
    fatti = MART_DIR / "debt_fatti.parquet"
    if not fatti.exists():
        print("[ERRORE] mart prima dei segnali")
        sys.exit(1)

    SIG_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE fatti AS
        SELECT * FROM read_parquet('{fatti}')
    """)

    rows = con.execute("""
        SELECT data, valore_mln_eur
        FROM fatti
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
    print(f"[signals] debito totale AP: ultimo {latest:.0f} mln EUR")
    print(f"[signals] variazione m/m: {delta:+.2f}%" if delta is not None else "[signals] variazione m/m: n/d")


if __name__ == "__main__":
    run()

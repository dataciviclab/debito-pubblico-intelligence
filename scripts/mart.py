#!/usr/bin/env python3
"""
Step mart: dataset queryabile (debito per sottosettore/strumento/detentore).

Il mart unico `debt_fatti` ha granularità data x tavola x codice.
Le query analitiche vivono in queries/*.sql e leggono da qui.
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "data" / "build"
MART_DIR = ROOT / "data" / "mart"


def run():
    src = BUILD_DIR / "fpi_long.csv"
    if not src.exists():
        print("[ERRORE] normalize fpi prima del mart")
        sys.exit(1)

    MART_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE fpi AS SELECT * FROM read_csv('{src}', delim=';')")

    con.execute(f"""
        COPY (SELECT data, tavola_nome AS tavola, codice, descrizione, valore_mln_eur, fonte
              FROM fpi) TO '{MART_DIR / "debt_fatti.parquet"}' (FORMAT parquet)
    """)
    n = con.execute("SELECT count(*) FROM fpi").fetchone()[0]
    print(f"[mart] OK {MART_DIR / 'debt_fatti.parquet'}: {n} righe")


if __name__ == "__main__":
    run()

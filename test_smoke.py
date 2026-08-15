#!/usr/bin/env python3
"""
Smoke test di integrità: verifica che i layer prodotti esistano e abbiano forma
attesa. Antidoto alle regressioni — run rapido dopo `make all`.
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
MART = ROOT / "data" / "mart" / "debt_fatti.parquet"


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main():
    if not MART.exists():
        fail(f"mart mancante: {MART}")

    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{MART}')").fetchone()[0]
    if n == 0:
        fail("mart vuoto")

    tavole = con.execute(f"SELECT count(DISTINCT tavola) FROM read_parquet('{MART}')").fetchone()[0]
    fonti = con.execute(f"SELECT count(DISTINCT fonte) FROM read_parquet('{MART}')").fetchone()[0]

    print(f"[OK] mart: {n} righe, {tavole} tavole, {fonti} fonti")
    print("[OK] smoke test superato")


if __name__ == "__main__":
    main()

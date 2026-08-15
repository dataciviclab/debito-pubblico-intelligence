#!/usr/bin/env python3
"""
Step normalize: layer source-level -> long/tidy standard.

Aggiunge colonne di provenienza, non elimina nulla.
Output: data/build/fpi_long.csv (parquet se DuckDB disponibile).
"""

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
BUILD_DIR = ROOT / "data" / "build"

FPI_TABLE_NAMES = {
    "TCCE0125": "fabbisogno_ap_strumenti",
    "TCCE0175": "debito_ap_strumenti",
    "TCCE0200": "debito_ap_detentori",
    "TCCE0225": "debito_ap_sottosettori",
    "TCCE0250": "debito_amm_locali_comparti",
    "TCCE0275": "debito_amm_locali_aree",
    "TCCE0300": "depositi_liquidita_ap",
    "TCCE0325": "debito_ap_vita_residua",
    "TCCE0350": "debito_ap_scadenza_valuta",
}


def _read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def normalize_fpi():
    src = RAW_DIR / "fpi_all.csv"
    if not src.exists():
        print("[ERRORE] fetch fpi prima di normalizzare")
        sys.exit(1)
    rows = _read_csv(src)
    for r in rows:
        r["tavola_nome"] = FPI_TABLE_NAMES.get(r["tavola"], r["tavola"])
        r["fonte"] = "banca_ditalia_fpi"

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / "fpi_long.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["data", "tavola", "tavola_nome", "codice", "descrizione", "valore_mln_eur", "fonte"], delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"[normalize] fpi OK {out}: {len(rows)} righe")


def run():
    normalize_fpi()


if __name__ == "__main__":
    run()

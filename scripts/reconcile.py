#!/usr/bin/env python3
"""
Step reconcile: fusion layer — riconciliazione cross-fonte.

Questo è il cuore dell'intelligence: lo stesso "debito" visto da fonti diverse
(competenza vs cassa, Maastricht vs Banca d'Italia) viene allineato e i delta
oltre soglia diventano anomalie da investigare.

Stato: bootstrap — il primo caso di riconciliazione è FPI (debito AP) vs
Eurostat EDP (debito/PIL) appena la fonte Eurostat è disponibile.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MART_DIR = ROOT / "data" / "mart"
RECON_DIR = ROOT / "data" / "reconcile"


def run():
    fatti = MART_DIR / "debt_fatti.parquet"
    if not fatti.exists():
        print("[ERRORE] mart prima di reconcile")
        sys.exit(1)

    RECON_DIR.mkdir(parents=True, exist_ok=True)
    print("[reconcile] framework pronto — nessuna fonte Eurostat ancora disponibile")
    print("[reconcile] TODO: debito mensile FPI vs debito/PIL trimestrale Eurostat vs OCPI")


if __name__ == "__main__":
    run()

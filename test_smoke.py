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
MEF_SCAD = ROOT / "data" / "build" / "mef_scadenze.parquet"
RECON = ROOT / "data" / "reconcile" / "reconcile_fpi_vs_eurostat.csv"
RECON_OCPI = ROOT / "data" / "reconcile" / "reconcile_fpi_vs_ocpi.csv"
RECON_MEF = ROOT / "data" / "reconcile" / "reconcile_mef_vs_fpi.csv"
RECON_T12 = ROOT / "data" / "reconcile" / "reconcile_titoli12m_vs_isin.csv"
RECON_FAB = ROOT / "data" / "reconcile" / "reconcile_fabbisogno_vs_stock.csv"
RECON_ONERI = ROOT / "data" / "reconcile" / "reconcile_oneri_bdap_vs_ocpi.csv"
RECON_ACC = ROOT / "data" / "reconcile" / "reconcile_accensione_vs_fabbisogno.csv"
PANORAMA = ROOT / "data" / "reporting" / "panorama.json"
SCEN = ROOT / "data" / "scenarios" / "scenarios.json"


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

    if not RECON.exists():
        fail(f"reconcile mancante: {RECON}")
    recon_rows = con.execute(f"SELECT count(*) FROM read_csv('{RECON}')").fetchone()[0]
    if recon_rows == 0:
        fail("reconcile vuoto")
    print(f"[OK] reconcile eurostat: {recon_rows} anni confrontati")

    if not RECON_OCPI.exists():
        fail(f"reconcile ocpi mancante: {RECON_OCPI}")
    recon_ocpi = con.execute(f"SELECT count(*) FROM read_csv('{RECON_OCPI}')").fetchone()[0]
    if recon_ocpi == 0:
        fail("reconcile ocpi vuoto")
    print(f"[OK] reconcile ocpi: {recon_ocpi} anni confrontati")

    if not RECON_MEF.exists():
        fail(f"reconcile mef mancante: {RECON_MEF}")
    recon_mef = con.execute(f"SELECT count(*) FROM read_csv('{RECON_MEF}')").fetchone()[0]
    if recon_mef == 0:
        fail("reconcile mef vuoto")
    print(f"[OK] reconcile mef: {recon_mef} record")

    if not MEF_SCAD.exists():
        fail(f"scadenze mef mancanti: {MEF_SCAD}")
    n_isin = con.execute(f"SELECT count(DISTINCT isin) FROM read_parquet('{MEF_SCAD}')").fetchone()[0]
    if n_isin == 0:
        fail("scadenze mef vuote")
    print(f"[OK] scadenze mef: {n_isin} ISIN distinti")

    if not RECON_T12.exists():
        fail(f"reconcile titoli12m mancante: {RECON_T12}")
    recon_t12 = con.execute(f"SELECT count(*) FROM read_csv('{RECON_T12}')").fetchone()[0]
    if recon_t12 == 0:
        fail("reconcile titoli12m vuoto")
    print(f"[OK] reconcile titoli12m: {recon_t12} mesi confrontati")

    if not PANORAMA.exists():
        fail(f"panorama mancante: {PANORAMA}")
    import json
    with open(PANORAMA, encoding="utf-8") as f:
        panorama = json.load(f)
    if not panorama.get("segnali") or not panorama.get("profilo"):
        fail("panorama senza segnali/profilo")
    print(f"[OK] panorama: {len(panorama['segnali'])} segnali, {len(panorama['profilo'])} anni profilo")

    if not RECON_FAB.exists():
        fail(f"reconcile fabbisogno mancante: {RECON_FAB}")
    recon_fab = con.execute(f"SELECT count(*) FROM read_csv('{RECON_FAB}')").fetchone()[0]
    if recon_fab == 0:
        fail("reconcile fabbisogno vuoto")
    print(f"[OK] reconcile fabbisogno: {recon_fab} mesi confrontati")

    if not SCEN.exists():
        fail(f"scenari mancanti: {SCEN}")
    with open(SCEN, encoding="utf-8") as f:
        scen = json.load(f)
    if not scen.get("scenari"):
        fail("scenari vuoti")
    print(f"[OK] scenari: {len(scen['scenari'])} ipotesi, orizzonte {scen.get('orizzonte_anni')} anni")

    for name, path in [("oneri", RECON_ONERI), ("accensione", RECON_ACC)]:
        if not path.exists():
            fail(f"reconcile {name} mancante: {path}")
        n = con.execute(f"SELECT count(*) FROM read_csv('{path}')").fetchone()[0]
        if n == 0:
            fail(f"reconcile {name} vuoto")
        print(f"[OK] reconcile {name}: {n} anni confrontati")

    print("[OK] smoke test superato")


if __name__ == "__main__":
    main()

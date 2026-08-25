#!/usr/bin/env python3
"""Preprocess MEF Titoli in scadenza 12 mesi. Usage: python preprocess.py raw_input.csv"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from mef_common import download_latest_csv, parse_amount, read_mef_csv

MONTHS = {"gen":1,"feb":2,"mar":3,"apr":4,"mag":5,"giu":6,"lug":7,"ago":8,"set":9,"ott":10,"nov":11,"dic":12}

def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"
    data = download_latest_csv("titoli_scadenza_prossimi_12_mesi")
    if data is None:
        sys.exit(1)
    rows = read_mef_csv(data)
    header_idx = None
    for i, r in enumerate(rows):
        if r and (r[0] or "").strip().upper() == "MESI":
            header_idx = i
            break
    if header_idx is None:
        print("[ERRORE] intestazione non trovata")
        sys.exit(1)
    header = [(h or "").strip() for h in rows[header_idx]]
    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        if (r[0] or "").strip().upper() == "TOTALE":
            continue
        parts = r[0].strip().split("-")
        if len(parts) != 2 or parts[0].lower() not in MONTHS:
            continue
        year = 2000 + int(parts[1])
        month = MONTHS[parts[0].lower()]
        for i in range(1, len(header)):
            col = header[i]
            if col == "TOTALE" or not col or i >= len(r):
                continue
            val = parse_amount(r[i])
            if val is not None:
                records.append({"mese_scadenza": f"{year:04d}-{month:02d}", "tipologia": col, "valore_mln_eur": val})
        tot_idx = header.index("TOTALE") if "TOTALE" in header else None
        if tot_idx is not None and tot_idx < len(r):
            tot = parse_amount(r[tot_idx])
            if isinstance(tot, (int, float)):
                records.append({"mese_scadenza": f"{year:04d}-{month:02d}", "tipologia": "TOTALE", "valore_mln_eur": tot})
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mese_scadenza", "tipologia", "valore_mln_eur"])
        w.writeheader()
        w.writerows(records)
    print(f"[mef-titoli-12m] OK {output}: {len(records)} celle")

if __name__ == "__main__":
    main()

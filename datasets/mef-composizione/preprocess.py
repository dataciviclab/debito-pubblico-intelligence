#!/usr/bin/env python3
"""Preprocess MEF Composizione Titoli Stato. Usage: python preprocess.py raw_input.csv"""
import sys, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from mef_common import download_latest_csv, parse_amount, read_mef_csv

def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"
    data = download_latest_csv("composizione_titoli_stato")
    if data is None:
        sys.exit(1)
    rows = read_mef_csv(data)
    header_idx = None
    for i, r in enumerate(rows):
        if r and any("tipologia" in (c or "").lower() or "mese" in (c or "").lower() for c in r[:3]):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0
    header = [(h or "").strip() for h in rows[header_idx]]
    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        for i in range(1, len(header)):
            col = header[i]
            if not col or col == "TOTALE" or i >= len(r):
                continue
            val = parse_amount(r[i])
            if val is not None:
                records.append({"tipologia": r[0].strip(), "colonna": col, "valore_mln_eur": val})
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["tipologia", "colonna", "valore_mln_eur"])
        w.writeheader()
        w.writerows(records)
    print(f"[mef-composizione] OK {output}: {len(records)} celle")

if __name__ == "__main__":
    main()

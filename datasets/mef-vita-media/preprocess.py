#!/usr/bin/env python3
"""Preprocess MEF Vita Media Ponderata. Usage: python preprocess.py raw_input.csv"""
import sys, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from mef_common import download_latest_csv, parse_amount, read_mef_csv

MONTHS = {"gen":1,"feb":2,"mar":3,"apr":4,"mag":5,"giu":6,"lug":7,"ago":8,"set":9,"ott":10,"nov":11,"dic":12}

def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"
    data = download_latest_csv("vita_media_ponderata")
    if data is None:
        sys.exit(1)
    rows = read_mef_csv(data)
    header_idx = None
    for i, r in enumerate(rows):
        if r and len(r) > 1 and (r[1] or "").strip() == "BOT":
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
        parts = r[0].strip().split("-")
        if len(parts) != 2 or parts[0].lower() not in MONTHS:
            continue
        year = 2000 + int(parts[1])
        month = MONTHS[parts[0].lower()]
        for i, col in enumerate(header):
            if not col or i == 0 or i >= len(r):
                continue
            val = parse_amount(r[i])
            if val is not None:
                records.append({"mese": f"{year:04d}-{month:02d}", "tipologia": col, "vita_media_mesi": val})
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mese", "tipologia", "vita_media_mesi"])
        w.writeheader()
        w.writerows(records)
    print(f"[mef-vita-media] OK {output}: {len(records)} celle")

if __name__ == "__main__":
    main()

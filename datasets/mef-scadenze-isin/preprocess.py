#!/usr/bin/env python3
"""
Preprocess MEF Scadenze ISIN-level.

Scarica l'ultimo file scadenze dal portale MEF, parsifica i record ISIN
e produce raw_input.csv per il toolkit.

Usage: python preprocess.py raw_input.csv

Output: isin, tipo, emissione, scadenza, cedola_pct, valuta,
        circolante_riv_eur, circolante_nom_eur, data_ref

Fonte: https://www.dt.mef.gov.it/it/debito_pubblico/dati_statistici/scadenze_titoli_suddivise_anno/
"""

import sys
from collections import defaultdict
from pathlib import Path

# Add parent dir for shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from mef_common import download_latest_csv, parse_amount, parse_date, read_mef_csv

import csv


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"

    data = download_latest_csv("scadenze_titoli_suddivise_anno")
    if data is None:
        sys.exit(1)

    rows = read_mef_csv(data)

    # Find header row with "Codice ISIN"
    header_idx = None
    for i, r in enumerate(rows):
        if r and (r[0] or "").strip() == "Codice ISIN":
            header_idx = i
            break
    if header_idx is None:
        print("[ERRORE] intestazione 'Codice ISIN' non trovata")
        sys.exit(1)

    # Find data_ref from header text
    data_ref = "2026-01-01"  # fallback
    for r in rows[:header_idx]:
        for cell in r:
            if "al" in str(cell).lower() and "20" in str(cell):
                import re
                m = re.search(r"(\d{1,2})\s+\w+\s+(\d{4})", str(cell))
                if m:
                    from datetime import date
                    months = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,
                              "maggio":5,"giugno":6,"luglio":7,"agosto":8,
                              "settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
                    day = int(m.group(1))
                    mon = months.get(m.group(0).split()[1].lower(), 1)
                    data_ref = f"{m.group(2)}-{mon:02d}-{day:02d}"

    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        isin = r[0].strip()
        tipo = (r[1] or "").strip() if len(r) > 1 else ""
        emissione = parse_date(r[2]) if len(r) > 2 else None
        scadenza = parse_date(r[3]) if len(r) > 3 else None
        cedola = parse_amount(r[4]) if len(r) > 4 else None
        valuta = (r[5] or "").strip() if len(r) > 5 else ""
        circ_riv = parse_amount(r[6]) if len(r) > 6 else None
        circ_nom = parse_amount(r[7]) if len(r) > 7 else None
        if scadenza is None:
            continue
        records.append({
            "isin": isin, "tipo": tipo,
            "emissione": str(emissione) if emissione else "",
            "scadenza": str(scadenza),
            "cedola_pct": cedola or "",
            "valuta": valuta,
            "circolante_riv_eur": circ_riv or "",
            "circolante_nom_eur": circ_nom or "",
            "data_ref": data_ref,
        })

    # Dedup tranche: same ISIN can appear multiple times, take max circolante
    best = {}
    for r in records:
        key = (r["isin"], r["scadenza"])
        if key not in best:
            best[key] = r
            continue
        cur = best[key]
        for col in ("circolante_riv_eur", "circolante_nom_eur"):
            cur_val = float(cur[col]) if cur[col] else 0
            new_val = float(r[col]) if r[col] else 0
            if new_val > cur_val:
                cur[col] = r[col]
    records = list(best.values())

    fieldnames = [
        "isin", "tipo", "emissione", "scadenza", "cedola_pct",
        "valuta", "circolante_riv_eur", "circolante_nom_eur", "data_ref",
    ]
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)

    print(f"[mef-scadenze] OK {output}: {len(records)} ISIN")


if __name__ == "__main__":
    main()

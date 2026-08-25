#!/usr/bin/env python3
"""
Preprocess OCPI - Osservatorio sul Conto Pubblico Italiano.

Scarica il file Excel delle serie storiche e produce raw_input.csv.
Usage: python preprocess.py raw_input.csv
"""

import csv
import io
import re
import sys
import urllib.request

OCPI_PAGE = "https://osservatoriocpi.unicatt.it/ocpi-servizi-serie-storiche"
USER_AGENT = "Mozilla/5.0"


def _find_xlsx_url() -> str:
    req = urllib.request.Request(OCPI_PAGE, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")
    all_links = [m.group(1) for m in re.finditer(r'href=\"([^\"]+)\"', html)]
    links = [l for l in all_links if l.lower().endswith(('.xlsx', 'xls'))]

    if not links:
        print("[ERRORE] ocpi: nessun link .xlsx trovato")
        sys.exit(1)
    href = links[0]
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://osservatoriocpi.unicatt.it" + href
    if href.startswith("http"):
        return href
    return "https://osservatoriocpi.unicatt.it/" + href


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"
    import openpyxl
    url = _find_xlsx_url()
    print(f"[ocpi] download {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        xlsx_bytes = resp.read()
    print(f"[ocpi] scaricato {len(xlsx_bytes)} bytes")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb["serie storiche"]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[1]
    years = [h for h in header[5:] if h is not None]
    series_rows = []
    for r in rows[2:]:
        sid, name, unit = r[1], r[2], r[3]
        if sid is None or name is None:
            continue
        for i, y in enumerate(years):
            val = r[5 + i] if (5 + i) < len(r) else None
            if val is None:
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            series_rows.append({"serie": sid, "nome": name, "unita": unit, "anno": int(y), "valore": val})
    fieldnames = ["serie", "nome", "unita", "anno", "valore"]
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(series_rows)
    n = len({r["serie"] for r in series_rows})
    print(f"[ocpi] OK {output}: {len(series_rows)} celle, {n} serie")


if __name__ == "__main__":
    main()

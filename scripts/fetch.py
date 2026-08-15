#!/usr/bin/env python3
"""
Step fetch: scarica le fonti ufficiali del debito pubblico.

Fonti:
  fpi      -> Banca d'Italia BDS, pubblicazione FPI (Finanza pubblica: fabbisogno e debito)
              ZIP -> FPI_DATA.zip -> TCCE*.zip -> CSV wide; convertito in long (tidy).
  eurostat -> SDMX per gov_10dd_edpt1 (debito/PIL trimestrale) e irt_lt_mcby_m (rendimento 10Y)
  ocpi     -> OCPI serie storiche finanza pubblica (Excel da universo Cattolica)

Il layer source-level conserva il dato grezzo: nessuna colonna originale eliminata.
"""

import csv
import io
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

USER_AGENT = "DataCivicLab pipeline/1.0"

FPI_URL = "https://a2a.bancaditalia.it/infostat/dataservices/export/IT/CSV/ALL/PUBLICATION/BANKITALIA/DIFF/FPI"
FPI_CACHE = ROOT / "data" / "raw" / ".cache" / "BANKITALIA_DIFF_FPI.zip"

GEO_LABELS = {
    "ITC": "Nord-ovest",
    "ITH": "Nord-est",
    "ITI": "Centro",
    "ITF": "Sud",
    "ITG": "Isole",
}

ALL_TABLES = {
    "TCCE0125": "Fabbisogno AP per strumenti",
    "TCCE0175": "Debito AP per strumenti",
    "TCCE0200": "Debito AP per detentori",
    "TCCE0225": "Debito AP per sottosettori",
    "TCCE0250": "Debito Amm.locali per comparti",
    "TCCE0275": "Debito Amm.locali per aree",
    "TCCE0300": "Depositi e liquidita AP",
    "TCCE0325": "Debito AP per vita residua",
    "TCCE0350": "Debito AP per scadenza/valuta",
}


def _download(url, path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        path.write_bytes(resp.read())


def _read_legend(zip_bytes):
    legend = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if "LEGEND" in name.upper():
                text = zf.read(name).decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(text), delimiter=";")
                for row in reader:
                    codice = str(row.get("Codice") or "").strip()
                    desc = str(row.get("Descrizione") or "").strip()
                    if codice and desc:
                        parts = codice.split(".")
                        if len(parts) >= 8:
                            legend[f"{parts[3]}.{parts[4]}"] = desc
                        legend[codice] = desc
    return legend


def _decode_code(column):
    if not column.startswith("FPI_FP."):
        return ""
    parts = column.split(".")
    if len(parts) < 8:
        return ""
    geo = parts[2]
    if geo != "IT":
        return f"{geo}.{parts[4]}"
    return f"{parts[3]}.{parts[4]}"


def _wide_to_long(csv_bytes, table_code, legend, filter_year=None):
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = []
    for row in reader:
        data_oss = (row.get("DATA_OSS") or "").strip()
        if not data_oss:
            continue
        if filter_year is not None and not data_oss.startswith(str(filter_year)):
            continue
        for colname, value in row.items():
            if colname == "DATA_OSS" or not value:
                continue
            try:
                valore = float(value.replace(",", "."))
            except (ValueError, AttributeError):
                continue
            codice = _decode_code(colname)
            if not codice:
                continue
            rows.append({
                "data": data_oss,
                "tavola": table_code,
                "codice": codice,
                "descrizione": legend.get(codice, ""),
                "valore_mln_eur": valore,
            })
    return rows


def fetch_fpi(filter_year=None):
    print("[fpi] download ZIP ...")
    _download(FPI_URL, FPI_CACHE)

    with zipfile.ZipFile(FPI_CACHE) as zf:
        data_zip = zipfile.ZipFile(io.BytesIO(zf.read("FPI_DATA.zip")))
        legend = _read_legend(zf.read("FPI_LEGEND.zip"))
        for geo, label in GEO_LABELS.items():
            for strumento in ["MGD", "F3", "F4"]:
                legend[f"{geo}.{strumento}"] = f"Amm. locali ({label}): debito lordo"

    all_rows = []
    for code in ALL_TABLES:
        member = f"{code}_IT.zip"
        if member not in data_zip.namelist():
            continue
        with zipfile.ZipFile(io.BytesIO(data_zip.read(member))) as tz:
            csvs = [n for n in tz.namelist() if n.endswith(".csv")]
            if not csvs:
                continue
            rows = _wide_to_long(tz.read(csvs[0]), code, legend, filter_year)
            all_rows.extend(rows)

    if not all_rows:
        print(f"[ERRORE] fpi: nessuna riga (anno={filter_year})")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / "fpi_all.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["data", "tavola", "codice", "descrizione", "valore_mln_eur"], delimiter=";")
        w.writeheader()
        w.writerows(all_rows)
    print(f"[fpi] OK {out}: {len(all_rows)} righe")


def fetch_eurostat():
    print("[eurostat] ... da implementare (SDMX gov_10dd_edpt1, irt_lt_mcby_m)")


def fetch_ocpi():
    print("[ocpi] ... da implementare (serie storiche finanza pubblica)")


def run(source=None):
    if source in (None, "fpi"):
        fetch_fpi()
    if source in (None, "eurostat"):
        fetch_eurostat()
    if source in (None, "ocpi"):
        fetch_ocpi()


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    run(src)

#!/usr/bin/env python3
"""
Step normalize MEF: scadenze ISIN-level -> parquet queryabile.

Input:  data/raw/mef_scadenze.csv  (latin-1, ; delim, date GG/MM/AAAA, numeri . ,)
Output: data/build/mef_scadenze.parquet

Colonne: isin, tipo, emissione, scadenza, cedola, valuta,
         circolante_riv_eur, circolante_nom_eur, data_ref
"""

import csv
import io
import re
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
BUILD_DIR = ROOT / "data" / "build"

COUPON_RE = re.compile(r"^\d+([.,]\d+)?$")


def _parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s):
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_coupon(s):
    """Cedola/Spread: numero (es. 3,200) o '-' o testo."""
    s = (s or "").strip()
    if not s or s == "-":
        return None
    if COUPON_RE.match(s):
        return float(s.replace(",", "."))
    return None


def _data_ref():
    """Data di aggiornamento dal header del file, fallback: oggi."""
    raw = (RAW_DIR / "mef_scadenze.csv").read_bytes()
    for enc in ("utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    m = re.search(r"al (\d{1,2} [a-z]+ \d{4})", text, re.I)
    if not m:
        return date.today()
    months = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
              "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
              "novembre": 11, "dicembre": 12}
    parts = m.group(1).split()
    return date(int(parts[2]), months.get(parts[1].lower(), 1), int(parts[0]))


def run():
    src = RAW_DIR / "mef_scadenze.csv"
    if not src.exists():
        print("[ERRORE] fetch mef prima di normalizzare")
        sys.exit(1)

    raw = src.read_bytes()
    for enc in ("utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))

    # trova l'intestazione
    header_idx = None
    for i, r in enumerate(rows):
        if r and (r[0] or "").strip() == "Codice ISIN":
            header_idx = i
            break
    if header_idx is None:
        print("[ERRORE] intestazione 'Codice ISIN' non trovata")
        sys.exit(1)

    data_ref = _data_ref()
    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        isin = r[0].strip()
        tipo = (r[1] or "").strip() if len(r) > 1 else ""
        emissione = _parse_date(r[2]) if len(r) > 2 else None
        scadenza = _parse_date(r[3]) if len(r) > 3 else None
        cedola = _parse_coupon(r[4]) if len(r) > 4 else None
        valuta = (r[5] or "").strip() if len(r) > 5 else ""
        circ_riv = _parse_amount(r[6]) if len(r) > 6 else None
        circ_nom = _parse_amount(r[7]) if len(r) > 7 else None
        if scadenza is None:
            continue
        records.append({
            "isin": isin,
            "tipo": tipo,
            "emissione": emissione,
            "scadenza": scadenza,
            "cedola_pct": cedola,
            "valuta": valuta,
            "circolante_riv_eur": circ_riv,
            "circolante_nom_eur": circ_nom,
            "data_ref": data_ref,
        })

    if not records:
        print("[ERRORE] nessun record valido in mef_scadenze")
        sys.exit(1)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE scadenze (
            isin VARCHAR, tipo VARCHAR, emissione DATE, scadenza DATE,
            cedola_pct DOUBLE, valuta VARCHAR,
            circolante_riv_eur DOUBLE, circolante_nom_eur DOUBLE, data_ref DATE
        )
    """)
    con.executemany(
        "INSERT INTO scadenze VALUES (?,?,?,?,?,?,?,?,?)",
        [(r["isin"], r["tipo"], r["emissione"], r["scadenza"], r["cedola_pct"],
          r["valuta"], r["circolante_riv_eur"], r["circolante_nom_eur"], r["data_ref"])
         for r in records],
    )
    out = BUILD_DIR / "mef_scadenze.parquet"
    con.execute(f"COPY scadenze TO '{out}' (FORMAT parquet)")
    print(f"[normalize] mef scadenze OK {out}: {len(records)} titoli (data_ref {data_ref})")


if __name__ == "__main__":
    run()

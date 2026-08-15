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

    # Dedup tranche: il file MEF elenca righe multiple per lo stesso ISIN quando il
    # titolo ha più tranche (la colonna 'Emissione' riporta il numero tranche, es.
    # '0,3'). Il circolante della tranche più recente include le precedenti, quindi
    # si prende il massimo per (isin, scadenza) per evitare double-count.
    from collections import defaultdict
    best = {}
    for r in records:
        key = (r["isin"], r["scadenza"])
        if key not in best:
            best[key] = r
            continue
        cur = best[key]
        for col in ("circolante_riv_eur", "circolante_nom_eur"):
            if (cur.get(col) is None) or (r.get(col) is not None and r[col] > cur[col]):
                cur[col] = r.get(col)
    records = list(best.values())

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

    normalize_titoli_12m()
    normalize_vita_media()


def _parse_mef_csv(path):
    raw = path.read_bytes()
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def normalize_titoli_12m():
    """Titoli in scadenza nei prossimi 12 mesi: per mese x tipologia (mln EUR)."""
    src = RAW_DIR / "mef_titoli_12m.csv"
    if not src.exists():
        return
    text = _parse_mef_csv(src)
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    header_idx = None
    for i, r in enumerate(rows):
        if r and (r[0] or "").strip() == "MESI":
            header_idx = i
            break
    if header_idx is None:
        print("[normalize] mef_titoli_12m: intestazione non trovata")
        return
    header = [h.strip() for h in rows[header_idx]]

    MONTHS = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
              "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}
    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        mese = r[0].strip()  # es. 'ago-26'
        parts = mese.split("-")
        if len(parts) != 2 or parts[0].lower() not in MONTHS:
            continue
        year = 2000 + int(parts[1])
        month = MONTHS[parts[0].lower()]
        for i in range(1, len(header)):
            col = header[i]
            if col == "TOTALE":
                continue
            val = _parse_amount(r[i]) if i < len(r) else None
            if val is None:
                continue
            records.append({
                "mese_scadenza": f"{year:04d}-{month:02d}",
                "tipologia": col,
                "valore_mln_eur": val,
            })
        tot = _parse_amount(r[header.index("TOTALE")]) if "TOTALE" in header else None
        if tot is not None:
            records.append({"mese_scadenza": f"{year:04d}-{month:02d}",
                            "tipologia": "TOTALE", "valore_mln_eur": tot})

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE t12 (mese_scadenza VARCHAR, tipologia VARCHAR, valore_mln_eur DOUBLE)")
    con.executemany("INSERT INTO t12 VALUES (?,?,?)",
                    [(r["mese_scadenza"], r["tipologia"], r["valore_mln_eur"]) for r in records])
    out = BUILD_DIR / "mef_titoli_12m.parquet"
    con.execute(f"COPY t12 TO '{out}' (FORMAT parquet)")
    print(f"[normalize] mef titoli_12m OK {out}: {len(records)} celle")


def normalize_vita_media():
    """Vita media ponderata: serie mensile per tipologia (mesi)."""
    src = RAW_DIR / "mef_vita_media.csv"
    if not src.exists():
        return
    text = _parse_mef_csv(src)
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    header_idx = None
    for i, r in enumerate(rows):
        if r and len(r) > 1 and (r[1] or "").strip() == "BOT":
            header_idx = i
            break
    if header_idx is None:
        print("[normalize] mef_vita_media: intestazione non trovata")
        return
    header = [(h or "").strip() for h in rows[header_idx]]

    MONTHS = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
              "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}
    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        mese = r[0].strip()
        parts = mese.split("-")
        if len(parts) != 2 or parts[0].lower() not in MONTHS:
            continue
        year = 2000 + int(parts[1])
        month = MONTHS[parts[0].lower()]
        for i, col in enumerate(header):
            if not col or col == "" or i == 0:
                continue
            if i >= len(r):
                continue
            val = _parse_amount(r[i])
            if val is None:
                continue
            records.append({
                "mese": f"{year:04d}-{month:02d}",
                "tipologia": col,
                "vita_media_mesi": val,
            })

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE vmedia (mese VARCHAR, tipologia VARCHAR, vita_media_mesi DOUBLE)")
    con.executemany("INSERT INTO vmedia VALUES (?,?,?)",
                    [(r["mese"], r["tipologia"], r["vita_media_mesi"]) for r in records])
    out = BUILD_DIR / "mef_vita_media.parquet"
    con.execute(f"COPY vmedia TO '{out}' (FORMAT parquet)")
    print(f"[normalize] mef vita_media OK {out}: {len(records)} celle")


if __name__ == "__main__":
    run()

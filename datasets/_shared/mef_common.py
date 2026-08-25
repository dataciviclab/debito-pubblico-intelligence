"""Shared utilities for MEF preprocessing."""

import csv
import io
import re
import urllib.request
from pathlib import Path

MEF_BASE = "https://www.dt.mef.gov.it/it/debito_pubblico/dati_statistici"
USER_AGENT = "Mozilla/5.0"

MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def mef_csv_links(page_path: str) -> list[str]:
    """Scarica la pagina HTML e estrae i link ai CSV."""
    url = f"{MEF_BASE}/{page_path}/"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")
    pat = re.compile(r'href="([^"]*\.csv)"', re.IGNORECASE)
    return sorted({m.group(1) for m in pat.finditer(html)})


def file_date(base: str):
    """Estrae la data dal nome file MEF. Formati: al-DD-mese-AAAA o DD.MM.AAAA"""
    m = re.search(r"al(\d{1,2})?-?(\d{1,2})-([a-z]+)-(\d{4})", base)
    if m:
        day = m.group(2) or m.group(1)
        month_num = MONTHS.get(m.group(3).lower())
        if month_num:
            return (int(m.group(4)), month_num, int(day))
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", base)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def download_latest_csv(page_path: str):
    """Scarica l'ultimo CSV dalla pagina MEF e ritorna i bytes."""
    links = mef_csv_links(page_path)
    best, best_key = None, None
    for link in links:
        key = file_date(Path(link).name)
        if key and (best_key is None or key > best_key):
            best_key, best = key, link
    if best is None:
        print(f"[mef] nessun CSV datato su {page_path}")
        return None
    url = f"https://www.dt.mef.gov.it{best}"
    print(f"[mef] download {best} ...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    print(f"[mef] scaricato {len(data)} bytes")
    return data


def read_mef_csv(data: bytes) -> list[list[str]]:
    """Legge un CSV MEF gestendo encoding latin-1."""
    for enc in ("utf-8", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.reader(io.StringIO(text), delimiter=";"))


def parse_amount(s: str):
    """Parsing numero italiano: 1.234,56 -> 1234.56"""
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s: str):
    """Parsing data GG/MM/AAAA."""
    from datetime import datetime
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None

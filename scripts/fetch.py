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
import json
import re
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


def _eurostat_series(payload):
    """Decodifica un payload SDMX JSON Eurostat in righe long.

    Gestisce dimensioni variabili: ogni dimensione in payload['id'] (ordine fisso)
    contribuisce alla posizione flat con stride = prodotto delle size successive.
    Il codice di ogni dimensione è derivato dall'index delle category.
    """
    dims = payload["id"]
    categories = {d: payload["dimension"][d]["category"]["index"] for d in dims}
    labels = {d: payload["dimension"][d]["category"]["label"] for d in dims}
    sizes = [len(categories[d]) for d in dims]

    strides = []
    acc = 1
    for s in reversed(sizes):
        strides.append(acc)
        acc *= s
    strides.reverse()

    def decode(pos):
        coords = {}
        for i, d in enumerate(dims):
            coord = pos // strides[i]
            pos %= strides[i]
            code = [c for c, idx in categories[d].items() if idx == coord]
            coords[d] = code[0] if code else ""
        return coords

    rows = []
    for value_key, val in payload["value"].items():
        coords = decode(int(value_key))
        rows.append({
            **coords,
            "valore": val,
        })

    rows.sort(key=lambda r: tuple(r.get(d, "") for d in dims))
    return rows


def _eurostat_get(dataset, params):
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    req = Request(f"{url}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        return json.load(resp)


def fetch_eurostat():
    print("[eurostat] debito/PIL per settore (gov_10dd_edpt1, PC_GDP, na_item=GD) ...")
    payload = _eurostat_get("gov_10dd_edpt1", {"geo": "IT", "unit": "PC_GDP", "na_item": "GD"})
    rows = _eurostat_series(payload)
    for r in rows:
        r["anno"] = r.pop("time")
        r["settore"] = r.pop("sector")
        r["debito_pil_pct"] = r.pop("valore")
        for k in ("freq", "unit", "geo", "na_item"):
            r.pop(k, None)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / "eurostat_gov10dd.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["anno", "settore", "debito_pil_pct"])
        w.writeheader()
        w.writerows(rows)
    print(f"[eurostat] OK {out}: {len(rows)} righe")

    print("[eurostat] stock debito in MIO_EUR (gov_10dd_edpt1, na_item=GD) ...")
    payload = _eurostat_get("gov_10dd_edpt1", {"geo": "IT", "unit": "MIO_EUR", "na_item": "GD"})
    rows = _eurostat_series(payload)
    for r in rows:
        r["anno"] = r.pop("time")
        r["settore"] = r.pop("sector")
        r["stock_mln_eur"] = r.pop("valore")
        for k in ("freq", "unit", "geo", "na_item"):
            r.pop(k, None)

    out = RAW_DIR / "eurostat_gov10dd_stock.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["anno", "settore", "stock_mln_eur"])
        w.writeheader()
        w.writerows(rows)
    print(f"[eurostat] OK {out}: {len(rows)} righe")

    print("[eurostat] rendimento 10Y mensile (irt_lt_mcby_m) ...")
    payload = _eurostat_get("irt_lt_mcby_m", {"geo": "IT"})
    rows = _eurostat_series(payload)
    for r in rows:
        r["mese"] = r.pop("time")
        r["rendimento_pct"] = r.pop("valore")
        for k in ("freq", "int_rt", "geo"):
            r.pop(k, None)

    out = RAW_DIR / "eurostat_irt_lt_mcby.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["mese", "rendimento_pct"])
        w.writeheader()
        w.writerows(rows)
    print(f"[eurostat] OK {out}: {len(rows)} righe")


def fetch_ocpi():
    """Serie storiche OCPI (Università Cattolica) — Excel con 26 serie, 1861-2025.

    Scarica la pagina serie storiche, trova il link .xlsx, estrae le serie "dato"
    in formato long. Fonte terza: non scarica se il file è già presente.
    """
    import re

    import openpyxl

    out = RAW_DIR / "ocpi_serie_storiche.xlsx"
    if not out.exists():
        page = "https://osservatoriocpi.unicatt.it/ocpi-servizi-serie-storiche"
        print(f"[ocpi] cerco link su {page} ...")
        req = Request(page, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "ignore")
        links = re.findall(r'href=["\']([^"\']*\.(?:xlsx|xls))["\']', html, re.I)
        if not links:
            print("[ERRORE] ocpi: nessun link .xlsx trovato")
            sys.exit(1)
        # preferisce il link assoluto; risolve relativi
        href = links[0]
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = "https://osservatoriocpi.unicatt.it" + href
        elif href.startswith("http"):
            url = href
        else:
            url = "https://osservatoriocpi.unicatt.it/" + href
        print(f"[ocpi] download {url} ...")
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        with urlopen(req, timeout=120) as resp:
            out.write_bytes(resp.read())
        print(f"[ocpi] scaricato {out} ({out.stat().st_size} bytes)")
    else:
        print(f"[ocpi] xlsx già presente: {out}")

    wb = openpyxl.load_workbook(out, read_only=True, data_only=True)
    ws = wb["serie storiche"]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[1]
    years = [h for h in header[5:] if h is not None]

    series_rows = []
    for r in rows[2:]:
        sid = r[1]
        name = r[2]
        unit = r[3]
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
            series_rows.append({
                "serie": sid,
                "nome": name,
                "unita": unit,
                "anno": int(y),
                "valore": val,
            })

    csv_out = RAW_DIR / "ocpi_serie_storiche.csv"
    with open(csv_out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["serie", "nome", "unita", "anno", "valore"])
        w.writeheader()
        w.writerows(series_rows)
    print(f"[ocpi] OK {csv_out}: {len(series_rows)} celle")


def _mef_csv_links(page_path, suffix_pat):
    """Estrae link a CSV da una pagina MEF del portale dt.mef.gov.it."""
    url = f"https://www.dt.mef.gov.it/it/debito_pubblico/dati_statistici/{page_path}/"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")
    links = sorted(set(l for l in re.findall(r'href=["\']([^"\']*\.csv)["\']', html, re.I)))
    return links


def _mef_file_date(base):
    """Data dal nome file MEF.

    Formati supportati:
      'al-31-luglio-2026'  (mese in italiano)
      '30.06.2026'         (gg.mm.aaaa)
    Ritorna (anno, mese, giorno) o None.
    """
    MONTHS = {
        "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
        "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
        "novembre": 11, "dicembre": 12,
    }
    m = re.search(r"al(\d{1,2})?-?(\d{1,2})-(d{0,10}|[a-z]+)-(\d{4})", base)
    if m:
        day, month_txt, year = m.group(2) or m.group(1), m.group(3), m.group(4)
        month_num = MONTHS.get(month_txt.lower())
        if month_num is None:
            return None
        return (int(year), month_num, int(day))
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", base)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _download_mef_csv(page_path, out_name):
    """Scarica l'ultimo CSV (per data) dalla pagina MEF."""
    links = _mef_csv_links(page_path, r"\.csv$")
    best = None
    best_key = None
    for link in links:
        base = Path(link).name
        key = _mef_file_date(base)
        if key is None:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best = link
    if best is None:
        print(f"[mef] nessun CSV datato trovato su {page_path}")
        return None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / out_name
    url = "https://www.dt.mef.gov.it" + best
    print(f"[mef] download {best} ...")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=120) as resp:
        out.write_bytes(resp.read())
    print(f"[mef] OK {out} ({out.stat().st_size} bytes)")
    return out


def fetch_mef():
    """MEF Dipartimento del Tesoro — titoli di Stato.

    Scarica:
      - composizione titoli in circolazione (riepilogo per tipologia, CSV mensile)
      - scadenze per anno (ISIN-level, CSV mensile): emissione, scadenza, cedola,
        circolante -> base per il terzo caso reconcile (flussi che spiegano lo stock)
      - titoli in scadenza nei prossimi 12 mesi (per mese/tipologia) -> cross-check rollover
      - vita media ponderata (serie storica mensile) -> benchmark durata
    """
    _download_mef_csv(
        "composizione_titoli_stato",
        "mef_composizione.csv",
    )
    _download_mef_csv(
        "scadenze_titoli_suddivise_anno",
        "mef_scadenze.csv",
    )
    _download_mef_csv(
        "titoli_scadenza_prossimi_12_mesi",
        "mef_titoli_12m.csv",
    )
    _download_mef_csv(
        "vita_media_ponderata",
        "mef_vita_media.csv",
    )


def run(source=None):
    if source in (None, "fpi"):
        fetch_fpi()
    if source in (None, "eurostat"):
        fetch_eurostat()
    if source in (None, "ocpi"):
        fetch_ocpi()
    if source in (None, "mef"):
        fetch_mef()


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else None
    run(src)

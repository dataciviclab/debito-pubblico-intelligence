"""
Preprocess MEF Riepilogo emissioni e scadenze (BTP/BOT, ecc.).

Scopre gli URL CSV dal frontend DT usando il form `selezione-anno`,
scarica i file per anno×tipologia e produce raw_input.csv.

I nomi file cambiano tra gli anni (underscore vs trattini, suffissi):
quindi NON hardcodiamo i filename — li leggiamo dalla pagina.

Usage: python preprocess.py raw_input.csv [anno_min] [anno_max]

Output: anno, tipologia, sezione, isin, scadenza, tipo_tenore, importo_mld

Fonte: dt.mef.gov.it riepilogo_emissioni
"""

from __future__ import annotations

import csv
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from mef_common import USER_AGENT, parse_amount, parse_date

SITE = "https://www.dt.mef.gov.it"
PAGES = {
    "BTP": "/it/debito_pubblico/dati_statistici/riepilogo_emissioni/riepilogo_emissioni_btp/",
    "BOT": "/it/debito_pubblico/dati_statistici/riepilogo_emissioni/riepilogo_emissioni_bot/",
    "CCTeu": "/it/debito_pubblico/dati_statistici/riepilogo_emissioni/riepilogo_emissioni_ccteu/",
    "BTP_ITALIA": "/it/debito_pubblico/dati_statistici/riepilogo_emissioni/riepilogo_emissioni_btp_italia/",
    "BTPEI": "/it/debito_pubblico/dati_statistici/riepilogo_emissioni/riepilogo_emissioni_btpei/",
}

ISIN_RE = re.compile(r"(IT[0-9]{10})")
DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")
TENOR_RE = re.compile(r"^([0-9]+[MY])$")
CSV_HREF_RE = re.compile(r'href="([^"]+\.csv)"', re.IGNORECASE)


def http_get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def discover_csv(page: str, year: int) -> str | None:
    """URL assoluto del CSV per anno usando il form selezione-anno."""
    url = f"{SITE}{page}?selezione-anno={year}"
    try:
        html = http_get(url).decode("utf-8", "ignore")
    except Exception as exc:
        print(f"[riepilogo] page fail {page} {year}: {exc}")
        return None
    hrefs = CSV_HREF_RE.findall(html)
    if not hrefs:
        return None
    href = hrefs[0]
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{SITE}{href}"
    return f"{SITE}/export/sites/sitodt/modules/documenti_it/debito_pubblico/dati_statistici/riepilogo_emissioni/{href}"


def parse_isin_format(text: str, tipologia: str, anno: int) -> list[dict]:
    """Formato 2025+: ISIN + scadenza + importi mensili, sezioni EMISSIONI/SCADENZE."""
    rows = [r for r in csv.reader(text.splitlines(), delimiter=";")]
    records: list[dict] = []
    sezione = None
    tipo_tenore = None

    for r in rows:
        if not r:
            continue
        cells = [(c or "").strip() for c in r]
        joined = ";".join(cells)

        for c in cells[:2]:
            u = c.upper()
            if u.startswith("EMISSIONI"):
                sezione = "EMISSIONI"
                tipo_tenore = None
            elif u.startswith("SCADENZE"):
                sezione = "SCADENZE"
                tipo_tenore = None

        for c in cells[:3]:
            m = TENOR_RE.match(c)
            if m:
                tipo_tenore = m.group(1)

        isin_m = ISIN_RE.search(joined)
        if not isin_m or sezione is None:
            continue
        isin = isin_m.group(1)

        date_m = DATE_RE.search(joined)
        scadenza = parse_date(date_m.group(1)) if date_m else None

        seen_date = False
        candidates: list[float] = []
        for c in cells:
            if date_m and c == date_m.group(1):
                seen_date = True
                continue
            if not seen_date:
                continue
            val = parse_amount(c)
            if val is not None:
                candidates.append(val)
        nonzero = [v for v in candidates if abs(v) > 1e-9]
        importo = nonzero[-1] if nonzero else (candidates[-1] if candidates else None)

        records.append(
            {
                "anno": str(anno),
                "tipologia": tipologia,
                "sezione": sezione,
                "isin": isin,
                "scadenza": scadenza.isoformat() if scadenza else "",
                "tipo_tenore": tipo_tenore or "",
                "importo_mld": "" if importo is None else f"{importo:.3f}",
            }
        )
    return records


def parse_aggregate_format(text: str, tipologia: str, anno: int) -> list[dict]:
    """Formato ≤2024: righe mensili/trimestrali per tenore + totale annuale.

    Il file non ha ISIN. La riga annuale è quella che inizia con "Totale"
    e NON contiene "trim". Le ultime 3 celle numeriche di quella riga sono:
        emissioni (lordo), scadenze, nette   — in mln EUR.
    """
    rows = [r for r in csv.reader(text.splitlines(), delimiter=";")]
    records: list[dict] = []
    annual_vals: list[float] = []

    for r in rows:
        if not r:
            continue
        cells = [(c or "").strip() for c in r]
        first = cells[0] if cells else ""
        low = first.lower()
        if not low.startswith("totale"):
            continue
        if (
            "trim" in low
            or "trim." in low
            or "1°" in low
            or "2°" in low
            or "3°" in low
            or "4°" in low
        ):
            continue
        vals: list[float] = []
        for c in cells[1:]:
            v = parse_amount(c)
            if v is not None:
                vals.append(v)
        if len(vals) >= 3:
            annual_vals = vals[-3:]
            break

    if not annual_vals:
        return []

    emissioni, scadenze, _netta = annual_vals
    records.append(
        {
            "anno": str(anno),
            "tipologia": tipologia,
            "sezione": "EMISSIONI",
            "isin": "AGGREGATO",
            "scadenza": "",
            "tipo_tenore": "TOTALE",
            "importo_mld": f"{emissioni:.3f}",
        }
    )
    records.append(
        {
            "anno": str(anno),
            "tipologia": tipologia,
            "sezione": "SCADENZE",
            "isin": "AGGREGATO",
            "scadenza": "",
            "tipo_tenore": "TOTALE",
            "importo_mld": f"{scadenze:.3f}",
        }
    )
    return records


def parse_file(data: bytes, tipologia: str, anno: int) -> list[dict]:
    text = None
    for enc in ("utf-8", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return []

    # detect format: ISIN-level se contiene "ISIN" e "IT00"
    if "ISIN" in text.upper() and re.search(r"IT[0-9]{10}", text):
        return parse_isin_format(text, tipologia, anno)
    return parse_aggregate_format(text, tipologia, anno)


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"
    y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
    y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2026
    # default: BTP+BOT (i due principali per il ponte 034)
    tipologie = ["BTP", "BOT"]

    all_records: list[dict] = []
    for tip in tipologie:
        page = PAGES[tip]
        for year in range(y0, y1 + 1):
            url = discover_csv(page, year)
            if not url:
                print(f"[riepilogo] no csv {tip} {year}")
                continue
            print(f"[riepilogo] {tip} {year} -> {url.split('/')[-1][:70]}")
            try:
                data = http_get(url)
            except Exception as exc:
                print(f"[riepilogo] download fail {tip} {year}: {exc}")
                continue
            recs = parse_file(data, tip, year)
            print(f"[riepilogo]   {len(recs)} righe ISIN")
            all_records.extend(recs)

    fields = [
        "anno",
        "tipologia",
        "sezione",
        "isin",
        "scadenza",
        "tipo_tenore",
        "importo_mld",
    ]
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_records)
    print(f"[riepilogo] OK {output}: {len(all_records)} righe, anni {y0}-{y1}")


if __name__ == "__main__":
    main()

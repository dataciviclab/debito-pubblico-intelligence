"""
Preprocess MEF Scadenze ISIN-level.

Scarica l'ultimo file scadenze dal portale MEF, parsifica i record ISIN
e produce raw_input.csv per il toolkit.

Usage: python preprocess.py raw_input.csv

Output: isin, tipo, emissione, scadenza, cedola_pct, valuta,
        circolante_riv_eur, circolante_nom_eur, data_ref

Fonte: https://www.dt.mef.gov.it/it/debito_pubblico/dati_statistici/scadenze_titoli_suddivise_anno/

Note sul formato:
- le colonne si leggono per NOME (l'ordine nel file MEF non è un contratto);
- la cella "Cedola/Spread" contiene numero + etichetta ("0,550 Cedola reale",
  '3,250 "step up"'), quindi serve `parse_amount_leading`;
- la colonna "Codice ISIN" non contiene sempre un ISIN: per i prestiti SURE/NGEU
  contiene una descrizione. Il parser resta fedele alla fonte, la distinzione
  si fa nel clean (`classe_strumento`);
- `data_ref` deve essere trovata nell'intestazione: niente fallback silenzioso,
  altrimenti la finestra "in circolazione" si sposta senza errori.
"""

import csv
import re
import sys
from pathlib import Path

# Add parent dir for shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

from mef_common import (
    MONTHS,
    download_latest_csv,
    parse_amount,
    parse_amount_leading,
    parse_date,
    read_mef_csv,
)

HEADER_KEY = "codice isin"

# nome logico -> prefissi accettati nell'intestazione MEF
COLUMNS = {
    "isin": ("codice isin",),
    "tipo": ("tipo titolo",),
    "emissione": ("emissione",),
    "scadenza": ("scadenza",),
    "cedola": ("cedola", "cedola/spread"),
    "valuta": ("valuta",),
    "circ_riv": ("circolante euro (rivalutato)", "circolante rivalutato"),
    "circ_nom": ("circolante euro (nominale)", "circolante nominale"),
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _find_columns(header: list[str]) -> dict[str, int]:
    """Indice di colonna per nome, non per posizione."""
    normed = [_norm(c) for c in header]
    idx: dict[str, int] = {}
    for name, prefixes in COLUMNS.items():
        for i, cell in enumerate(normed):
            if any(cell.startswith(p) for p in prefixes):
                idx[name] = i
                break
    missing = [n for n in COLUMNS if n not in idx]
    if missing:
        print(f"[ERRORE] colonne non trovate: {missing}\nintestazione: {header}")
        sys.exit(1)
    return idx


def _parse_data_ref(rows: list[list[str]], header_idx: int) -> str:
    """Data di riferimento dal testo sopra l'intestazione ("al 30 settembre 2026")."""
    for r in rows[:header_idx]:
        for cell in r:
            m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", str(cell or ""))
            if not m:
                continue
            month = MONTHS.get(m.group(2).lower())
            if month is None:
                continue
            return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"
    print("[ERRORE] data di riferimento non trovata nell'intestazione del file MEF")
    sys.exit(1)


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"

    data = download_latest_csv("scadenze_titoli_suddivise_anno")
    if data is None:
        sys.exit(1)

    rows = read_mef_csv(data)

    header_idx = None
    for i, r in enumerate(rows):
        if any(_norm(c) == HEADER_KEY for c in r):
            header_idx = i
            break
    if header_idx is None:
        print("[ERRORE] intestazione 'Codice ISIN' non trovata")
        sys.exit(1)

    col = _find_columns(rows[header_idx])
    data_ref = _parse_data_ref(rows, header_idx)

    def cell(r, name):
        i = col[name]
        return r[i] if i < len(r) else ""

    records = []
    for r in rows[header_idx + 1:]:
        if not r or not (cell(r, "isin") or "").strip():
            continue
        isin = cell(r, "isin").strip()
        scadenza = parse_date(cell(r, "scadenza"))
        if scadenza is None:
            continue
        emissione = parse_date(cell(r, "emissione"))
        cedola = parse_amount_leading(cell(r, "cedola"))
        circ_riv = parse_amount(cell(r, "circ_riv"))
        circ_nom = parse_amount(cell(r, "circ_nom"))
        records.append({
            "isin": isin,
            "tipo": cell(r, "tipo").strip(),
            "emissione": str(emissione) if emissione else "",
            "scadenza": str(scadenza),
            "cedola_pct": "" if cedola is None else cedola,
            "valuta": cell(r, "valuta").strip(),
            "circolante_riv_eur": "" if circ_riv is None else circ_riv,
            "circolante_nom_eur": "" if circ_nom is None else circ_nom,
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
        for c in ("circolante_riv_eur", "circolante_nom_eur"):
            cur_val = float(cur[c]) if cur[c] else 0
            new_val = float(r[c]) if r[c] else 0
            if new_val > cur_val:
                cur[c] = r[c]
    records = list(best.values())

    fieldnames = [
        "isin", "tipo", "emissione", "scadenza", "cedola_pct",
        "valuta", "circolante_riv_eur", "circolante_nom_eur", "data_ref",
    ]
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)

    senza_cedola = sum(1 for r in records if r["cedola_pct"] == "" and not r["tipo"].startswith("BOT"))
    print(
        f"[mef-scadenze] OK {output}: {len(records)} righe, data_ref {data_ref}, "
        f"{senza_cedola} non-BOT senza cedola"
    )


if __name__ == "__main__":
    main()

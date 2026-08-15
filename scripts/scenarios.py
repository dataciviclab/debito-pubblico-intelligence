#!/usr/bin/env python3
"""
Step scenario: traiettorie del debito/PIL.

Identità di sostenibilità (formula di riferimento):
    d_{t+1} = d_t * (1 + i) / (1 + g) - sp_t
dove:
    d  = debito/PIL (ratio)
    i  = tasso d'interesse implicito medio (%)
    g  = tasso di crescita nominale del PIL (%)
    sp = saldo primario (% PIL, avanzo > 0)

Lo scenario parte dal valore reale più recente (OCPI debito/PIL) e proietta
in avanti per un orizzonte fissato sotto diverse ipotesi su (i, g, sp).
Serve a capire "cosa succede al debito se cambiano le condizioni", non a
prevedere il futuro.

Output: data/scenarios/scenarios.json + summary a terminale.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SCEN_DIR = ROOT / "data" / "scenarios"

HORIZON = 5  # anni di proiezione

# ipotesi: (nome, i, g, sp)
BASE = [
    ("stato_attuale", 2.89, 2.54, 0.7),      # ultimi valori osservati
    ("crescita_forte", 2.89, 3.50, 0.7),     # g più alta
    ("crescita_debole", 2.89, 1.00, 0.7),    # g più bassa
    ("tassi_alti", 3.50, 2.54, 0.7),         # costo medio del debito più alto
    ("avanzo_primario_2", 2.89, 2.54, 2.0),  # avanzo primario robusto
    ("avanzo_primario_3", 2.89, 2.54, 3.0),  # avanzo primario forte
    ("stress", 3.50, 1.00, 0.0),             # peggior combinazione
]


def _last_ocpi(con, serie):
    with open(RAW_DIR / "ocpi_serie_storiche.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    vals = [(int(r["anno"]), float(r["valore"])) for r in rows if r["serie"] == serie]
    return max(vals, key=lambda x: x[0])


def _project(d0, i, g, sp, years):
    """Proietta il debito/PIL con l'identità di sostenibilità."""
    i_p, g_p, sp_p = i / 100.0, g / 100.0, sp / 100.0
    d = d0 / 100.0
    path = [round(d * 100, 1)]
    for _ in range(years):
        d = d * (1 + i_p) / (1 + g_p) - sp_p
        path.append(round(d * 100, 1))
    return path


def run():
    SCEN_DIR.mkdir(parents=True, exist_ok=True)
    d_year, d0 = _last_ocpi(RAW_DIR / "ocpi_serie_storiche.csv", "D")

    scenarios = []
    for name, i, g, sp in BASE:
        path = _project(d0, i, g, sp, HORIZON)
        scenarios.append({
            "nome": name,
            "i_pct": i,
            "g_pct": g,
            "saldo_primario_pct": sp,
            "debito_pil_start_pct": path[0],
            "debito_pil_end_pct": path[-1],
            "traiettoria": path,
        })
        delta = path[-1] - path[0]
        print(f"[scenario] {name:20s}: {path[0]:6.1f}% -> {path[-1]:6.1f}% ({delta:+.1f} pp)")

    out = SCEN_DIR / "scenarios.json"
    payload = {
        "anno_base": d_year,
        "orizzonte_anni": HORIZON,
        "formula": "d(t+1) = d(t)*(1+i)/(1+g) - sp",
        "scenari": scenarios,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[scenario] OK {out}")


if __name__ == "__main__":
    run()

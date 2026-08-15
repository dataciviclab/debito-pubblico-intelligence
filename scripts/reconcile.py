#!/usr/bin/env python3
"""
Step reconcile: fusion layer — riconciliazione cross-fonte.

Confronta lo stesso concetto (debito lordo Amministrazioni Pubbliche) visto da
fonti diverse e materializza i delta. Ogni scostamento oltre soglia è un'anomalia
da investigare, NON un errore: le definizioni differiscono legittimamente.

Primo caso (bootstrap):
  FPI Banca d'Italia (mensile, fine mese)   -> debito AP, codice S13.MGD
  Eurostat gov_10dd_edpt1 (annuale, MIO_EUR) -> Government consolidated gross debt, S13

Allineamento: FPI mese di dicembre di ciascun anno vs Eurostat anno.
Delta % = (eurostat - fpi_dic) / fpi_dic * 100.
Soglia anomalia: |delta| > 2%.
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RECON_DIR = ROOT / "data" / "reconcile"

ANOMALY_THRESHOLD_PCT = 2.0


def _read_fpi_december(con):
    """Debito AP totale (S13.MGD) a dicembre di ogni anno da FPI."""
    return con.execute("""
        SELECT cast(strftime(data, '%Y') AS INT) AS anno,
               max_by(valore_mln_eur, data) AS fpi_dic_mln_eur
        FROM read_parquet('data/mart/debt_fatti.parquet')
        WHERE tavola = 'debito_ap_sottosettori'
          AND codice = 'S13.MGD'
        GROUP BY 1
        ORDER BY 1
    """).fetchall()


def run():
    fatti = ROOT / "data" / "mart" / "debt_fatti.parquet"
    euro = RAW_DIR / "eurostat_gov10dd_stock.csv"
    if not fatti.exists() or not euro.exists():
        print("[ERRORE] servono mart FPI e fetch eurostat")
        sys.exit(1)

    RECON_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE fpi AS SELECT * FROM read_parquet('{fatti}')")
    con.execute(f"CREATE TABLE eurostat AS SELECT * FROM read_csv('{euro}')")

    fpi_dic = _read_fpi_december(con)
    eur_rows = con.execute("""
        SELECT anno, stock_mln_eur FROM eurostat WHERE settore = 'S13' ORDER BY anno
    """).fetchall()

    eur_map = {anno: val for anno, val in eur_rows}
    report = []
    for anno, fpi_val in fpi_dic:
        eur_val = eur_map.get(anno)
        if eur_val is None:
            continue
        delta_pct = (eur_val - fpi_val) / fpi_val * 100
        report.append({
            "anno": anno,
            "fpi_dic_mln_eur": round(fpi_val, 1),
            "eurostat_mln_eur": round(eur_val, 1),
            "delta_pct": round(delta_pct, 2),
            "anomalia": "SI" if abs(delta_pct) > ANOMALY_THRESHOLD_PCT else "no",
        })

    out = RECON_DIR / "reconcile_fpi_vs_eurostat.csv"
    import csv
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["anno", "fpi_dic_mln_eur", "eurostat_mln_eur", "delta_pct", "anomalia"])
        w.writeheader()
        w.writerows(report)

    anomalies = [r for r in report if r["anomalia"] == "SI"]
    print(f"[reconcile] FPI vs Eurostat: {len(report)} anni confrontati, {len(anomalies)} anomalie (soglia {ANOMALY_THRESHOLD_PCT}%)")
    print(f"[reconcile] OK {out}")
    for a in anomalies[-5:]:
        print(f"[reconcile]   anomalia {a['anno']}: delta {a['delta_pct']:+.2f}% "
              f"(FPI {a['fpi_dic_mln_eur']:,.0f} vs EUR {a['eurostat_mln_eur']:,.0f})")
    if report:
        last = report[-1]
        print(f"[reconcile] ultimo anno ({last['anno']}): delta {last['delta_pct']:+.2f}%")


if __name__ == "__main__":
    run()

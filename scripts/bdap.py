#!/usr/bin/env python3
"""
Estrattore BDAP Stato (entrate/spese) — consuma i clean parquet dal catalogo GCS.

Non scarica nulla: legge direttamente i dataset già pubblicati dal Lab
(bdap_entrate_stato, bdap_spese_stato) via lab_connectors.gcs.paths.
Usato da reconcile per i casi 6 (oneri vs interessi OCPI) e 7 (accensione
prestiti vs fabbisogno FPI).

Output (celle estratte, non layer):
  data/build/bdap_stato_summary.csv — per anno: entrate tributarie,
    accensione prestiti, oneri debito, rimborsi, totale spese
"""

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "data" / "build"

YEARS = range(2008, 2025)


def _url(slug, year):
    from lab_connectors.gcs.paths import gs_url
    return gs_url("clean", "clean_parquet", slug=slug, year=year)


def _last_available(con, slug):
    """Ritorna il primo URL disponibile (dall'anno più recente)."""
    for year in sorted(YEARS, reverse=True):
        url = _url(slug, year)
        try:
            n = con.execute(f"SELECT count(*) FROM read_parquet('{url}')").fetchone()[0]
            if n and n > 0:
                return url
        except Exception:
            continue
    return None


def build_summary():
    """Aggrega per anno entrate e spese di interesse per il debito."""
    con = duckdb.connect()
    ent_url = _last_available(con, "bdap_entrate_stato")
    spe_url = _last_available(con, "bdap_spese_stato")
    if not ent_url or not spe_url:
        print("[ERRORE] BDAP non disponibile su GCS")
        sys.exit(1)

    rows = con.execute(f"""
        WITH ent AS (
            SELECT esercizio_finanziario AS anno,
                   sum(CASE WHEN codice_titolo = '1' THEN previsioni_definitive_cp END) AS trib_cp,
                   sum(CASE WHEN codice_titolo = '4' THEN previsioni_definitive_cp END) AS accensione_cp
            FROM read_parquet('{ent_url}')
            GROUP BY 1
        ),
        spe AS (
            SELECT esercizio_finanziario AS anno,
                   sum(CASE WHEN macroaggregato = 'ONERI DEL DEBITO PUBBLICO' THEN previsioni_definitive_cp END) AS oneri_cp,
                   sum(CASE WHEN macroaggregato = 'RIMBORSO DEL DEBITO PUBBLICO' THEN previsioni_definitive_cp END) AS rimborsi_cp,
                   sum(previsioni_definitive_cp) AS totale_spese_cp
            FROM read_parquet('{spe_url}')
            GROUP BY 1
        )
        SELECT e.anno, e.trib_cp, e.accensione_cp, s.oneri_cp, s.rimborsi_cp, s.totale_spese_cp
        FROM ent e JOIN spe s USING(anno)
        ORDER BY e.anno
    """).fetchall()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / "bdap_stato_summary.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anno", "trib_cp", "accensione_cp", "oneri_cp", "rimborsi_cp", "totale_spese_cp"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5]])
    print(f"[bdap] OK {out}: {len(rows)} anni")
    return out


if __name__ == "__main__":
    build_summary()

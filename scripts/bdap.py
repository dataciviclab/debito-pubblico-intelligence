"""
Estrattore BDAP Stato (entrate/spese + consuntivo pagamenti).

Non scarica nulla: legge i dataset già prodotti dal Lab.
- bdap_entrate_stato, bdap_spese_stato (previsioni) via GCS
- bdap_pagamenti_stato (CONSUNTIVO) via GCS

Tutti i dati sono in gs://dataciviclab-{mart|clean}/bilancio-pubblico/

Usato da reconcile per:
  caso 6: oneri consuntivi vs interessi OCPI (e vs oneri previsti BDAP)
  caso 7: accensione prestiti vs fabbisogno FPI

Output (celle estratte, non layer):
  data/build/bdap_stato_summary.csv   — per anno: trib, accensione, oneri, rimborsi
  data/build/bdap_consuntivo_debito.csv — serie consuntivo missione Debito pubblico
"""

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "data" / "build"

YEARS = range(2008, 2025)

PREFIX = "bilancio-pubblico/"


def _url(slug, year):
    from lab_connectors.gcs.paths import gs_url

    return gs_url("clean", "clean_parquet", slug=slug, year=year, prefix=PREFIX)


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
        w.writerow(
            [
                "anno",
                "trib_cp",
                "accensione_cp",
                "oneri_cp",
                "rimborsi_cp",
                "totale_spese_cp",
            ]
        )
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5]])
    print(f"[bdap] OK {out}: {len(rows)} anni")
    return out


def _consuntivo_file_urls(con):
    """URL dei mart consuntivo per anno da GCS."""
    from lab_connectors.gcs.paths import gs_url

    urls = []
    for year in range(2014, 2026):
        try:
            url = gs_url(
                "mart",
                "mart_parquet",
                slug="bdap_pagamenti_stato",
                year=year,
                table="mart_pagamenti_missione_categoria",
                prefix=PREFIX,
            )
            n = con.execute(f"SELECT count(*) FROM read_parquet('{url}')").fetchone()[0]
            if n and n > 0:
                urls.append(url)
        except Exception:
            continue
    return urls


def build_consuntivo():
    """Serie consuntiva della missione 'Debito pubblico' (interessi/rimborsi).

    Legge il mart bdap_pagamenti_stato (2014-2025) da GCS.
    """
    con = duckdb.connect()
    file_urls = _consuntivo_file_urls(con)
    if not file_urls:
        print("[bdap] consuntivo: nessun mart disponibile su GCS (skip)")
        return None

    rows = con.execute(f"""
        SELECT esercizio_finanziario AS anno,
               round(sum(CASE WHEN upper(categoria) LIKE '%INTERESSI%' THEN totale_pagato END)/1e6, 1) AS interessi_mln,
               round(sum(CASE WHEN upper(categoria) LIKE '%RIMBORSO%' THEN totale_pagato END)/1e6, 1) AS rimborsi_mln,
               round(sum(totale_pagato)/1e6, 1) AS totale_mln
        FROM read_parquet({file_urls!r})
        WHERE upper(missione) LIKE '%DEBITO%'
        GROUP BY 1 ORDER BY 1
    """).fetchall()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / "bdap_consuntivo_debito.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anno", "interessi_mln", "rimborsi_mln", "totale_mln"])
        for r in rows:
            w.writerow(r)
    print(f"[bdap] consuntivo OK {out}: {len(rows)} anni")
    return out


if __name__ == "__main__":
    build_summary()
    build_consuntivo()

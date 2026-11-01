"""
Estrattore BDAP Stato (entrate/spese + consuntivo pagamenti).

Non scarica nulla: legge i **mart** già prodotti dal repo `bilancio-pubblico`.
- bdap_entrate_stato → mart_entrate_titolo_natura_anno  (tributi, accensione prestiti)
- bdap_spese_stato   → mart_investimenti_vs_corrente    (oneri e rimborsi del debito)
- bdap_pagamenti_stato → mart_costo_debito_bilancio     (consuntivo: interessi_pagati, rimborsi_pagati)
Tutti in gs://dataciviclab-mart/bilancio-pubblico/.

Usato da reconcile per:
  caso 6: oneri consuntivi vs interessi OCPI (e vs oneri previsti BDAP)
  caso 7: accensione prestiti vs fabbisogno FPI

Nota sulle unità: i mart delle entrate sono in euro (esatti); quello delle spese
è in mld con un decimale, quindi gli importi di spesa hanno una precisione di
~100 mln. Prima si leggeva il clean (euro esatti): la differenza è <0,05% e
accettabile per un indicatore, ma è il motivo per cui i valori possono
discostarsi leggermente rispetto alle versioni precedenti.

Output (celle estratte, non layer):
  data/build/bdap_stato_summary.csv     — per anno: trib, accensione, oneri, rimborsi
  data/build/bdap_consuntivo_debito.csv — serie consuntivo missione Debito pubblico
"""

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "data" / "build"

YEARS = range(2008, 2026)

PREFIX = "bilancio-pubblico/"


def _mart_urls(con, slug, table):
    """URL dei mart su GCS: file flat (unico) oppure partizionati per anno.

    I repos del Lab pubblicano in due modi: alcuni mart sono un file unico
    (`mart_parquet_flat`), altri sono partizionati `{anno}/{table}.parquet`.
    Qui si prova prima il flat, poi le partizioni disponibili.
    """
    from lab_connectors.gcs.paths import gs_url

    try:
        flat = gs_url("mart", "mart_parquet_flat", slug=slug, table=table, prefix=PREFIX)
        if con.execute(f"SELECT count(*) FROM read_parquet('{flat}')").fetchone()[0]:
            return [flat]
    except Exception:
        pass

    urls = []
    for year in sorted(YEARS, reverse=True):
        try:
            url = gs_url(
                "mart",
                "mart_parquet",
                slug=slug,
                year=year,
                table=table,
                prefix=PREFIX,
            )
            n = con.execute(f"SELECT count(*) FROM read_parquet('{url}')").fetchone()[0]
            if n and n > 0:
                urls.append(url)
        except Exception:
            continue
    return urls


def build_summary():
    """Aggrega per anno entrate e spese di interesse per il debito."""
    con = duckdb.connect()
    ent_urls = _mart_urls(con, "bdap_entrate_stato", "mart_entrate_titolo_natura_anno")
    spe_urls = _mart_urls(con, "bdap_spese_stato", "mart_investimenti_vs_corrente")
    if not ent_urls or not spe_urls:
        print("[ERRORE] mart BDAP non disponibili su GCS")
        sys.exit(1)

    rows = con.execute(f"""
        WITH ent AS (
            SELECT anno,
                   sum(CASE WHEN codice_titolo = '1' THEN totale_cp END) AS trib_cp,
                   sum(CASE WHEN codice_titolo = '4' THEN totale_cp END) AS accensione_cp
            FROM read_parquet({ent_urls!r})
            GROUP BY 1
        ),
        spe AS (
            SELECT anno,
                   round(onere_debito_mld * 1e9, 1) AS oneri_cp,
                   round(rimborso_debito_mld * 1e9, 1) AS rimborsi_cp,
                   round(totale_mld * 1e9, 1) AS totale_spese_cp
            FROM read_parquet({spe_urls!r})
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


def build_consuntivo():
    """Serie consuntiva della missione 'Debito pubblico' (interessi/rimborsi).

    Legge `mart_costo_debito_bilancio`, che espone già le componenti
    (`interessi_pagati`, `rimborsi_pagati`, `altri_oneri_debito`): niente filtri
    sul testo di `categoria`, che cambia nome nel tempo (fino al 2022 era
    "INTERESSI PASSIVI E REDDITI DA CAPITALE").
    """
    con = duckdb.connect()
    urls = _mart_urls(con, "bdap_pagamenti_stato", "mart_costo_debito_bilancio")
    if not urls:
        print("[bdap] consuntivo: nessun mart disponibile su GCS (skip)")
        return None

    rows = con.execute(f"""
        SELECT anno,
               round(interessi_pagati / 1e6, 1) AS interessi_mln,
               round(rimborsi_pagati / 1e6, 1) AS rimborsi_mln,
               round(spesa_missione_debito / 1e6, 1) AS totale_mln
        FROM read_parquet({urls!r})
        ORDER BY anno
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

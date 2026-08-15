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

Secondo caso: FPI vs OCPI (serie C "Debito", milioni EUR correnti).
Le definizioni coincidono (stesso stock Maastricht); il delta conferma la coerenza.

Terzo caso: MEF Tesoro scadenze (ISIN-level, circolante titoli) vs FPI debito AP in
titoli (S13.F3). I perimetri NON coincidono (MEF = solo titoli di Stato emessi dal
Tesoro; FPI = tutti i titoli di tutte le AP) quindi un delta sistematico è atteso;
l'anomalia reale sarebbe una rottura del rapporto nel tempo.

Quarto caso: MEF "titoli in scadenza 12m" (file ufficiale per mese) vs rollover
calcolato da noi dal file ISIN-level scadenze. Stessa fonte MEF, due file diversi:
verifica del nostro parser + perimetro (8/12 mesi collimano, 4 divergono — da capire).
"""

import csv
import io
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


def _compare(con, name, fpi_dic, other_rows, out_path):
    other_map = {anno: val for anno, val in other_rows}
    report = []
    for anno, fpi_val in fpi_dic:
        other_val = other_map.get(anno)
        if other_val is None:
            continue
        delta_pct = (other_val - fpi_val) / fpi_val * 100
        report.append({
            "anno": anno,
            "fpi_dic_mln_eur": round(fpi_val, 1),
            f"{name}_mln_eur": round(other_val, 1),
            "delta_pct": round(delta_pct, 2),
            "anomalia": "SI" if abs(delta_pct) > ANOMALY_THRESHOLD_PCT else "no",
        })

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["anno", "fpi_dic_mln_eur", f"{name}_mln_eur", "delta_pct", "anomalia"])
        w.writeheader()
        w.writerows(report)

    anomalies = [r for r in report if r["anomalia"] == "SI"]
    print(f"[reconcile] FPI vs {name}: {len(report)} anni confrontati, {len(anomalies)} anomalie (soglia {ANOMALY_THRESHOLD_PCT}%)")
    print(f"[reconcile] OK {out_path}")
    for a in anomalies[-5:]:
        print(f"[reconcile]   anomalia {a['anno']}: delta {a['delta_pct']:+.2f}% "
              f"(FPI {a['fpi_dic_mln_eur']:,.0f} vs {name} {a[f'{name}_mln_eur']:,.0f})")
    if report:
        last = report[-1]
        print(f"[reconcile] ultimo anno ({last['anno']}): delta {last['delta_pct']:+.2f}%")
    return report


def run():
    fatti = ROOT / "data" / "mart" / "debt_fatti.parquet"
    euro = RAW_DIR / "eurostat_gov10dd_stock.csv"
    ocpi = RAW_DIR / "ocpi_serie_storiche.csv"
    if not fatti.exists() or not euro.exists():
        print("[ERRORE] servono mart FPI e fetch eurostat")
        sys.exit(1)

    RECON_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    fpi_dic = _read_fpi_december(con)

    print("=== CASO 1: FPI vs Eurostat (gov_10dd_edpt1) ===")
    eur_rows = con.execute("""
        SELECT anno, stock_mln_eur FROM read_csv('data/raw/eurostat_gov10dd_stock.csv')
        WHERE settore = 'S13' ORDER BY anno
    """).fetchall()
    _compare(con, "eurostat", fpi_dic, eur_rows, RECON_DIR / "reconcile_fpi_vs_eurostat.csv")

    if ocpi.exists():
        print("\n=== CASO 2: FPI vs OCPI (serie C 'Debito') ===")
        ocpi_rows = con.execute("""
            SELECT anno, valore FROM read_csv('data/raw/ocpi_serie_storiche.csv')
            WHERE serie = 'C' ORDER BY anno
        """).fetchall()
        _compare(con, "ocpi", fpi_dic, ocpi_rows, RECON_DIR / "reconcile_fpi_vs_ocpi.csv")
    else:
        print("\n[reconcile] ocpi non disponibile (skip caso 2)")
    mef = RAW_DIR / "mef_scadenze.csv"
    mef_comp = RAW_DIR / "mef_composizione.csv"
    if mef_comp.exists():
        print("\n=== CASO 3: MEF composizione titoli (Tesoro) vs FPI debito AP in titoli (F3) ===")
        # Totale titoli Tesoro in circolazione (mln EUR, stessa unità di FPI)
        import csv as _csv

        total_mef = None
        raw = mef_comp.read_bytes()
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        for row in _csv.reader(io.StringIO(text), delimiter=";"):
            if row and row[0].strip() == "Totale":
                total_mef = float(row[1].replace(".", "").replace(",", "."))
                break
        if total_mef is None:
            print("[reconcile] MEF composizione: Totale non trovato")
            return
        print(f"[reconcile] totale titoli Tesoro in circolazione (MEF): {total_mef:,.0f} mln EUR")

        fpi_f3 = con.execute("""
            SELECT data, sum(valore_mln_eur)
            FROM read_parquet('data/mart/debt_fatti.parquet')
            WHERE (tavola = 'debito_ap_strumenti' AND codice = 'S13.F31')
               OR (tavola = 'debito_ap_strumenti' AND codice = 'S13.F32')
            GROUP BY data ORDER BY data DESC LIMIT 1
        """).fetchall()
        if fpi_f3 and fpi_f3[0][1]:
            fpi_titoli = fpi_f3[0][1]
            ratio = total_mef / fpi_titoli * 100 if fpi_titoli else None
            print(f"[reconcile] FPI titoli AP (F31+F32, {fpi_f3[0][0]}): {fpi_titoli:,.0f} mln EUR")
            if ratio:
                print(f"[reconcile] rapporto MEF/FPI titoli: {ratio:.1f}% "
                      f"(atteso ~100%: il Tesoro emette quasi tutti i titoli AP)")
        out = RECON_DIR / "reconcile_mef_vs_fpi.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = _csv.writer(f)
            w.writerow(["data", "mef_titoli_mln_eur", "fpi_titoli_mln_eur", "rapporto_pct"])
            w.writerow([fpi_f3[0][0] if fpi_f3 else None, round(total_mef, 0),
                        round(fpi_titoli, 0) if fpi_titoli else None,
                        round(ratio, 2) if ratio else None])
        print(f"[reconcile] OK {out}")

        if mef.exists():
            n_isin = sum(1 for line in mef.read_bytes().decode("latin-1").splitlines()
                         if line.startswith("IT"))
            print(f"[reconcile] scadenze MEF: {n_isin} ISIN in circolazione (detail file)")
    else:
        print("\n[reconcile] mef non disponibile (skip caso 3)")

    # CASO 4: MEF titoli-12m (ufficiale) vs nostro rollover ISIN-level
    t12 = ROOT / "data" / "build" / "mef_titoli_12m.parquet"
    scad = ROOT / "data" / "build" / "mef_scadenze.parquet"
    if t12.exists() and scad.exists():
        print("\n=== CASO 4: MEF titoli-12m (ufficiale) vs rollover ISIN-level ===")
        import csv as _csv

        rows = con.execute("""
            SELECT mese_scadenza, sum(valore_mln_eur)
            FROM read_parquet('data/build/mef_titoli_12m.parquet')
            WHERE tipologia = 'TOTALE' GROUP BY 1 ORDER BY 1
        """).fetchall()
        off_map = {m: v for m, v in rows}

        ours = con.execute("""
            SELECT strftime(scadenza, '%Y-%m'), round(sum(circolante_nom_eur)/1e6, 0)
            FROM read_parquet('data/build/mef_scadenze.parquet')
            WHERE scadenza >= data_ref AND scadenza < date_add(data_ref, INTERVAL 12 MONTH)
            GROUP BY 1 ORDER BY 1
        """).fetchall()

        report = []
        for mese, nostro in ours:
            ufficiale = off_map.get(mese)
            if ufficiale is None:
                continue
            delta = nostro - ufficiale
            delta_pct = delta / ufficiale * 100 if ufficiale else None
            report.append({
                "mese": mese,
                "ufficiale_mln_eur": round(ufficiale, 0),
                "isin_mln_eur": round(nostro, 0),
                "delta_mln_eur": round(delta, 0),
                "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
                "anomalia": "SI" if abs(delta) > 500 else "no",
            })

        tot_off = sum(r["ufficiale_mln_eur"] for r in report)
        tot_our = sum(r["isin_mln_eur"] for r in report)
        print(f"[reconcile] totale 12m: ufficiale {tot_off:,.0f} vs ISIN {tot_our:,.0f} "
              f"mln EUR (delta {tot_our-tot_off:+,.0f})")
        n_anom = sum(1 for r in report if r["anomalia"] == "SI")
        print(f"[reconcile] mesi con delta >500 mln: {n_anom}/{len(report)}")
        for r in report:
            if r["anomalia"] == "SI":
                print(f"[reconcile]   {r['mese']}: uff {r['ufficiale_mln_eur']:,.0f} vs "
                      f"isin {r['isin_mln_eur']:,.0f} (delta {r['delta_mln_eur']:+,.0f})")

        out = RECON_DIR / "reconcile_titoli12m_vs_isin.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = _csv.writer(f)
            w.writerow(["mese", "ufficiale_mln_eur", "isin_mln_eur", "delta_mln_eur", "delta_pct", "anomalia"])
            for r in report:
                w.writerow([r["mese"], r["ufficiale_mln_eur"], r["isin_mln_eur"],
                            r["delta_mln_eur"], r["delta_pct"], r["anomalia"]])
        print(f"[reconcile] OK {out}")


if __name__ == "__main__":
    run()

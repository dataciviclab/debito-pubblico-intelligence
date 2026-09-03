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

Quinto caso: fabbisogno AP (TCCE0125) vs variazione dello stock di debito (S13.MGD).
Identità contabile: variazione stock = fabbisogno + aggiustamento stock-flussi (SFA).
Il delta è il SFA implicito — la parte di variazione del debito non spiegata dal
fabbisogno (es. operazioni fuori bilancio, riallocazioni, effetti di cambio).

Sesto caso: oneri del debito a bilancio (BDAP spese Stato) vs interessi OCPI.
INDICATORE, non confronto pari tra stessi concetti. Verificato:
- gli oneri BDAP sono interamente del MEF (stato_previsione = codice ministero, 02 = MEF)
- BDAP (solo Stato centrale) SUPERA OCPI (tutte le AP) di ~10-18 mld/anno → la voce
  "oneri per il servizio del debito" è definita più larga degli interessi puri:
  include spese di emissione/collocamento e voci di cassa su titoli indicizzati
- BDAP è PREVISIONE (≠ consuntivo, come da note candidate); OCPI è consuntivo a competenza
- l'eccezione 2022 (OCPI sopra di 7 mld) è coerente col rialzo dei tassi (competenza > cassa)
Valore: mostra lo scostamento sistematico tra costo "vero" a bilancio e stima interessi.

Settimo caso: accensione prestiti (BDAP entrate Stato, Titolo IV) vs fabbisogno FPI.
INDICATORE, non identità esatta: l'accensione è il flusso LORDO dello Stato (include
rifinanziamento + gestione tesoreria), il fabbisogno FPI è il NETTO delle AP. Il
residuo accensione - (fabbisogno + rimborsi) misura quanto indebitamento lordo va a
costituire riserve di liquidità. Perimetro: BDAP Stato vs FPI tutte le AP.
"""

import csv
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datasets._shared.paths import (
    MART_FPI_AP,
    MART_FPI_FAB,
    MART_MEF_COMP,
    MART_MEF_SCAD,
    MART_MEF_T12,
    MART_OCPI,
    RECON_DIR,
)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

ANOMALY_THRESHOLD_PCT = 2.0


def _read_fpi_december(con):
    """Debito AP totale (S13.MGD) a dicembre di ogni anno da FPI."""
    return con.execute("""
        SELECT cast(strftime(data, '%Y') AS INT) AS anno,
               max_by(valore_mln_eur, data) AS fpi_dic_mln_eur
        FROM read_parquet('out/data/mart/fpi_debito_pa/2026/mart_debito_ap.parquet')
        WHERE tavola_nome = 'debito_ap_sottosettori'
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

    # Genera dettaglio anomalie per summary
    anom_detail = ", ".join(f"{a['anno']} (delta {a['delta_pct']:+.2f}%)" for a in anomalies[:5])
    periodo = f"{report[0]['anno']}–{report[-1]['anno']}" if report else "?"
    return {
        "n_confrontati": len(report),
        "n_anomalie": len(anomalies),
        "anomalie_dettaglio": anom_detail,
        "periodo": periodo,
    }


def run():
    if not MART_FPI_AP.exists():
        print(f"[ERRORE] mart FPI mancante: {MART_FPI_AP}")
        sys.exit(1)
    str(MART_OCPI)

    RECON_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    summary = []

    fpi_dic = _read_fpi_december(con)

    print("=== CASO 1: FPI vs Eurostat (gov_10dd_edpt1) ===")
    eur_rows = con.execute("""
        SELECT anno, stock_mln_eur FROM read_parquet('out/data/mart/eurostat_debito_pil/2026/mart_debito_pil.parquet')
        WHERE settore = 'S13' ORDER BY anno
    """).fetchall()
    s1 = _compare(con, "eurostat", fpi_dic, eur_rows, RECON_DIR / "reconcile_fpi_vs_eurostat.csv")
    summary.append({
        "id": "fpi_vs_eurostat",
        "nome": "FPI vs Eurostat",
        "fonti": "Banca d'Italia FPI, Eurostat gov_10dd_edpt1",
        "periodo": s1["periodo"],
        "tipo": "confronto",
        "n_confrontati": s1["n_confrontati"],
        "n_anomalie": s1["n_anomalie"],
        "anomalie_dettaglio": s1["anomalie_dettaglio"],
        "csv": "reconcile_fpi_vs_eurostat.csv",
    })

    if MART_OCPI.exists():
        print("\n=== CASO 2: FPI vs OCPI (serie C 'Debito') ===")
        ocpi_rows = con.execute("""
            SELECT anno, valore FROM read_parquet('out/data/mart/ocpi_serie_storiche/2026/mart_serie_storiche.parquet')
            WHERE serie = 'C' ORDER BY anno
        """).fetchall()
        s2 = _compare(con, "ocpi", fpi_dic, ocpi_rows, RECON_DIR / "reconcile_fpi_vs_ocpi.csv")
        summary.append({
            "id": "fpi_vs_ocpi",
            "nome": "FPI vs OCPI",
            "fonti": "Banca d'Italia FPI, MEF OCPI",
            "periodo": s2["periodo"],
            "tipo": "confronto",
            "n_confrontati": s2["n_confrontati"],
            "n_anomalie": s2["n_anomalie"],
            "anomalie_dettaglio": s2["anomalie_dettaglio"],
            "csv": "reconcile_fpi_vs_ocpi.csv",
        })
    else:
        print("\n[reconcile] ocpi non disponibile (skip caso 2)")
    mef_comp_parquet = str(MART_MEF_COMP) if MART_MEF_COMP.exists() else None
    if mef_comp_parquet:
        print("\n=== CASO 3: MEF composizione titoli (Tesoro) vs FPI debito AP in titoli (F3) ===")
        # Totale titoli Tesoro in circolazione (mln EUR, stessa unità di FPI)
        import csv as _csv

        total_mef_rows = con.execute(f"""
            SELECT sum(valore_mln_eur) FROM read_parquet('{mef_comp_parquet}')
            WHERE tipologia = 'Totale'
        """).fetchall()
        total_mef = total_mef_rows[0][0] if total_mef_rows and total_mef_rows[0][0] else None
        if total_mef is None:
            print("[reconcile] MEF composizione: Totale non trovato")
            return
        print(f"[reconcile] totale titoli Tesoro in circolazione (MEF): {total_mef:,.0f} mln EUR")

        fpi_f3 = con.execute("""
            SELECT data, sum(valore_mln_eur)
            FROM read_parquet('out/data/mart/fpi_debito_pa/2026/mart_debito_ap.parquet')
            WHERE (tavola_nome = 'debito_ap_strumenti' AND codice = 'S13.F31')
               OR (tavola_nome = 'debito_ap_strumenti' AND codice = 'S13.F32')
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

        n_isin_rows = con.execute(f"SELECT count(*) FROM read_parquet('{MART_MEF_SCAD!s}')").fetchall()
        n_isin = n_isin_rows[0][0] if n_isin_rows else 0
        print(f"[reconcile] scadenze MEF: {n_isin} ISIN in circolazione")

        if ratio is not None:
            summary.append({
                "id": "mef_vs_fpi_titoli",
                "nome": "MEF titoli vs FPI titoli",
                "fonti": "MEF Tesoro composizione, Banca d'Italia FPI",
                "periodo": str(fpi_f3[0][0])[:7] if fpi_f3 else "?",
                "tipo": "rapporto",
                "rapporto_pct": round(ratio, 1),
                "n_anomalie": 0 if 95 <= ratio <= 105 else 1,
                "anomalie_dettaglio": f"rapporto {ratio:.1f}%",
                "csv": "reconcile_mef_vs_fpi.csv",
            })
    else:
        print("\n[reconcile] mef non disponibile (skip caso 3)")

    # CASO 4: MEF titoli-12m (ufficiale) vs nostro rollover ISIN-level
    if MART_MEF_T12.exists() and MART_MEF_SCAD.exists():
        print("\n=== CASO 4: MEF titoli-12m (ufficiale) vs rollover ISIN-level ===")
        import csv as _csv

        rows = con.execute("""
            SELECT mese_scadenza, sum(valore_mln_eur)
            FROM read_parquet('out/data/mart/mef_titoli_12m/2026/mart_titoli_12m.parquet')
            WHERE tipologia = 'TOTALE' AND try_cast(valore_mln_eur AS double) IS NOT NULL GROUP BY 1 ORDER BY 1
        """).fetchall()
        off_map = {m: v for m, v in rows}

        ours = con.execute("""
            SELECT strftime(scadenza, '%Y-%m'), round(sum(circolante_nom_eur)/1e6, 0)
            FROM read_parquet('out/data/mart/mef_scadenze_isin/2026/mart_scadenze_isin.parquet')
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

        if report:
            mese_min = report[0]["mese"]
            mese_max = report[-1]["mese"]
            anom_mesi = [r["mese"] for r in report if r["anomalia"] == "SI"]
            summary.append({
                "id": "titoli12m_vs_isin",
                "nome": "MEF titoli-12m vs rollover ISIN",
                "fonti": "MEF Tesoro titoli-12m, MEF Tesoro ISIN-level",
                "periodo": f"{mese_min}–{mese_max}",
                "tipo": "confronto",
                "n_confrontati": len(report),
                "n_anomalie": len(anom_mesi),
                "anomalie_dettaglio": ", ".join(anom_mesi[:5]),
                "csv": "reconcile_titoli12m_vs_isin.csv",
            })

    # CASO 5: fabbisogno AP (TCCE0125) vs variazione stock (S13.MGD)
    if MART_FPI_FAB.exists():
        print("\n=== CASO 5: fabbisogno AP vs variazione stock (SFA implicito) ===")
        import csv as _csv

        # stock mensile (serie): per calcolare la variazione m/m
        stock = con.execute("""
            SELECT data, valore_mln_eur
            FROM read_parquet('out/data/mart/fpi_debito_pa/2026/mart_debito_ap.parquet')
            WHERE tavola_nome = 'debito_ap_sottosettori' AND codice = 'S13.MGD'
            ORDER BY data
        """).fetchall()
        stock_map = {d: v for d, v in stock}

        fab = con.execute(f"""
            SELECT data, valore_mln_eur
            FROM read_parquet('{MART_FPI_FAB!s}')
            WHERE tavola_nome = 'fabbisogno_ap_strumenti' AND codice = 'S13.MGD'
            ORDER BY data
        """).fetchall()
        fab_map = {d: v for d, v in fab}

        # variazione stock = stock[t] - stock[t-1]; SFA = variazione - fabbisogno
        import datetime

        report = []
        for d, f in fab_map.items():
            first_this = datetime.date(d.year, d.month, 1)
            prev_month_end = first_this - datetime.timedelta(days=1)
            # cerchiamo l'ultima osservazione <= prev_month_end
            prev_vals = [v for dd, v in stock_map.items() if dd <= prev_month_end]
            prev_val = prev_vals[-1] if prev_vals else None
            cur_val = stock_map.get(d)
            if prev_val is None or cur_val is None:
                continue
            d_stock = cur_val - prev_val
            sfa = d_stock - f
            report.append({
                "mese": d.isoformat()[:7],
                "fabbisogno_mln_eur": round(f, 0),
                "variazione_stock_mln_eur": round(d_stock, 0),
                "sfa_implicito_mln_eur": round(sfa, 0),
            })

        report = report[-36:]  # ultimi 3 anni
        tot_fab = sum(r["fabbisogno_mln_eur"] for r in report)
        tot_var = sum(r["variazione_stock_mln_eur"] for r in report)
        tot_sfa = sum(r["sfa_implicito_mln_eur"] for r in report)
        print(f"[reconcile] ultimi {len(report)} mesi: fabbisogno cum {tot_fab:,.0f} vs "
              f"variazione stock cum {tot_var:,.0f} mln (SFA cum {tot_sfa:+,.0f})")
        big = [r for r in report if abs(r["sfa_implicito_mln_eur"]) > 20000]
        print(f"[reconcile] mesi con |SFA| >20 mld: {len(big)}")
        for r in big[-5:]:
            print(f"[reconcile]   {r['mese']}: fab {r['fabbisogno_mln_eur']:,.0f} vs "
                  f"Δstock {r['variazione_stock_mln_eur']:,.0f} (SFA {r['sfa_implicito_mln_eur']:+,.0f})")

        out = RECON_DIR / "reconcile_fabbisogno_vs_stock.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = _csv.writer(f)
            w.writerow(["mese", "fabbisogno_mln_eur", "variazione_stock_mln_eur", "sfa_implicito_mln_eur"])
            for r in report:
                w.writerow([r["mese"], r["fabbisogno_mln_eur"], r["variazione_stock_mln_eur"],
                            r["sfa_implicito_mln_eur"]])
        print(f"[reconcile] OK {out}")

        if report:
            summary.append({
                "id": "fabbisogno_vs_stock",
                "nome": "Fabbisogno vs variazione stock",
                "fonti": "Banca d'Italia FPI",
                "periodo": f"{report[0]['mese']}–{report[-1]['mese']}",
                "tipo": "identita_contabile",
                "n_confrontati": len(report),
                "sfa_cumulato_mld": round(tot_sfa / 1e3, 1),
                "n_anomalie": len(big),
                "anomalie_dettaglio": f"SFA cumulato {tot_sfa/1e3:+.1f} mld su {len(report)} mesi",
                "csv": "reconcile_fabbisogno_vs_stock.csv",
            })

    # CASO 6+7: BDAP Stato (oneri vs OCPI; accensione prestiti vs fabbisogno FPI)
    bdap = ROOT / "data" / "build" / "bdap_stato_summary.csv"
    ocpi_parquet = str(MART_OCPI) if MART_OCPI.exists() else None
    if bdap.exists() and ocpi_parquet:
        import csv as _csv

        print("\n=== CASO 6: oneri debito BDAP vs interessi OCPI ===")
        # interessi OCPI: serie J = spesa per interessi in mln EUR correnti
        ocpi_rows = con.execute(f"""SELECT anno, valore FROM read_parquet('{ocpi_parquet}') WHERE serie = 'J'""").fetchall()
        ocpi_int = {int(r[0]): float(r[1]) for r in ocpi_rows}

        report6 = []
        for r in _csv.DictReader(open(bdap)):  # noqa: SIM115
            anno = int(r["anno"])
            oneri = float(r["oneri_cp"]) / 1e6  # EUR -> mln
            ocpi_v = ocpi_int.get(anno)
            if ocpi_v is None:
                continue
            delta = oneri - ocpi_v
            report6.append({
                "anno": anno,
                "oneri_bdap_mln_eur": round(oneri, 0),
                "interessi_ocpi_mln_eur": round(ocpi_v, 0),
                "delta_mln_eur": round(delta, 0),
                "delta_pct": round(delta / ocpi_v * 100, 1),
            })
        tot6 = sum(r["delta_mln_eur"] for r in report6)
        print(f"[reconcile] oneri BDAP vs OCPI: {len(report6)} anni, delta medio "
              f"{tot6/len(report6):+.0f} mln/anno" if report6 else "nessun dato")
        for r in report6[-3:]:
            print(f"[reconcile]   {r['anno']}: BDAP {r['oneri_bdap_mln_eur']:,.0f} vs "
                  f"OCPI {r['interessi_ocpi_mln_eur']:,.0f} (delta {r['delta_mln_eur']:+,.0f})")
        out6 = RECON_DIR / "reconcile_oneri_bdap_vs_ocpi.csv"
        with open(out6, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=["anno", "oneri_bdap_mln_eur", "interessi_ocpi_mln_eur",
                                                "delta_mln_eur", "delta_pct"])
            w.writeheader()
            w.writerows(report6)
        print(f"[reconcile] OK {out6}")

        if report6:
            avg_delta = tot6 / len(report6)
            summary.append({
                "id": "oneri_bdap_vs_ocpi",
                "nome": "Oneri debito BDAP vs interessi OCPI",
                "fonti": "MEF BDAP, MEF OCPI",
                "periodo": f"{report6[0]['anno']}–{report6[-1]['anno']}",
                "tipo": "indicatore",
                "n_confrontati": len(report6),
                "delta_medio_mld": round(avg_delta / 1e3, 1),
                "n_anomalie": 0,
                "anomalie_dettaglio": f"delta medio {avg_delta/1e3:+.1f} mld/anno (previsione vs stima)",
                "csv": "reconcile_oneri_bdap_vs_ocpi.csv",
            })

        # SOTTOCASO 6b: CONSUNTIVO missione debito vs interessi OCPI
        consuntivo = ROOT / "data" / "build" / "bdap_consuntivo_debito.csv"
        if consuntivo.exists():
            print("\n=== CASO 6b: consuntivo interessi (pagati) vs OCPI ===")
            report6b = []
            for r in _csv.DictReader(open(consuntivo)):  # noqa: SIM115
                anno = int(r["anno"])
                cons = float(r["interessi_mln"])
                ocpi_v = ocpi_int.get(anno)
                if ocpi_v is None:
                    continue
                delta = cons - ocpi_v
                report6b.append({
                    "anno": anno,
                    "consuntivo_mln_eur": round(cons, 0),
                    "ocpi_mln_eur": round(ocpi_v, 0),
                    "delta_mln_eur": round(delta, 0),
                    "delta_pct": round(delta / ocpi_v * 100, 1),
                })
            tot6b = sum(r["delta_mln_eur"] for r in report6b)
            avg6b = tot6b / len(report6b) if report6b else None
            print(f"[reconcile] consuntivo vs OCPI: {len(report6b)} anni, "
                  f"delta medio {avg6b:+.0f} mln/anno" if avg6b is not None else "nessun dato")
            for r in report6b:
                print(f"[reconcile]   {r['anno']}: cons {r['consuntivo_mln_eur']:,.0f} vs "
                      f"OCPI {r['ocpi_mln_eur']:,.0f} (delta {r['delta_mln_eur']:+,.0f} = {r['delta_pct']:+.1f}%)")
            out6b = RECON_DIR / "reconcile_consuntivo_vs_ocpi.csv"
            with open(out6b, "w", encoding="utf-8", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=["anno", "consuntivo_mln_eur", "ocpi_mln_eur",
                                                    "delta_mln_eur", "delta_pct"])
                w.writeheader()
                w.writerows(report6b)
            print(f"[reconcile] OK {out6b}")

            if report6b:
                summary.append({
                    "id": "consuntivo_vs_ocpi",
                    "nome": "Consuntivo interessi vs OCPI",
                    "fonti": "MEF BDAP consuntivo, MEF OCPI",
                    "periodo": f"{report6b[0]['anno']}–{report6b[-1]['anno']}",
                    "tipo": "confronto",
                    "n_confrontati": len(report6b),
                    "delta_medio_mld": round(avg6b / 1e3, 1) if avg6b else 0,
                    "n_anomalie": 0,
                    "anomalie_dettaglio": f"delta medio {avg6b/1e3:+.1f} mld/anno" if avg6b else "nessun dato",
                    "csv": "reconcile_consuntivo_vs_ocpi.csv",
                })

        print("\n=== CASO 7: accensione prestiti BDAP vs fabbisogno AP FPI ===")
        # fabbisogno annuale: somma del fabbisogno mensile S13.MGD per anno
        fab_annual = con.execute(f"""
            SELECT cast(strftime(data, '%Y') AS INT) anno, sum(valore_mln_eur) tot
            FROM read_parquet('{MART_FPI_FAB!s}')
            WHERE tavola_nome = 'fabbisogno_ap_strumenti' AND codice = 'S13.MGD'
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        fab_map = {a: v for a, v in fab_annual}

        report7 = []
        for r in _csv.DictReader(open(bdap)):  # noqa: SIM115
            anno = int(r["anno"])
            accensione = float(r["accensione_cp"]) / 1e6  # EUR -> mln
            fab = fab_map.get(anno)
            if fab is None:
                continue
            delta = accensione - fab
            report7.append({
                "anno": anno,
                "accensione_bdap_mln_eur": round(accensione, 0),
                "fabbisogno_fpi_mln_eur": round(fab, 0),
                "delta_mln_eur": round(delta, 0),
            })
        if report7:
            last7 = report7[-1]
            print(f"[reconcile] {last7['anno']}: accensione {last7['accensione_bdap_mln_eur']:,.0f} vs "
                  f"fabbisogno FPI {last7['fabbisogno_fpi_mln_eur']:,.0f} (delta {last7['delta_mln_eur']:+,.0f})")
            out7 = RECON_DIR / "reconcile_accensione_vs_fabbisogno.csv"
            with open(out7, "w", encoding="utf-8", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=["anno", "accensione_bdap_mln_eur",
                                                    "fabbisogno_fpi_mln_eur", "delta_mln_eur"])
                w.writeheader()
                w.writerows(report7)
            print(f"[reconcile] OK {out7}")

            summary.append({
                "id": "accensione_vs_fabbisogno",
                "nome": "Accensione prestiti vs fabbisogno",
                "fonti": "MEF BDAP, Banca d'Italia FPI",
                "periodo": f"{report7[0]['anno']}–{report7[-1]['anno']}",
                "tipo": "indicatore",
                "n_confrontati": len(report7),
                "n_anomalie": 0,
                "anomalie_dettaglio": "perimetro diverso (lordo Stato vs netto AP)",
                "csv": "reconcile_accensione_vs_fabbisogno.csv",
            })

    # ── Scrivi summary.json ────────────────────────────────────────
    summary_path = RECON_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    con.close()
    print(f"\n[reconcile] OK summary: {len(summary)} casi -> {summary_path}")


if __name__ == "__main__":
    run()

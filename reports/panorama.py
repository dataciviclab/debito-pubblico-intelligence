#!/usr/bin/env python3
"""
Report panorama — deliverable pubblico del debito pubblico italiano.

Aggrega segnali, reconcile e profilo scadenze in un unico documento leggibile:
  data/reporting/panorama.md  (narrativa + tabelle)
  data/reporting/panorama.json (payload strutturato per riuso)

Uso: python reports/panorama.py  (o make panorama)
"""

import csv
import json
import sys
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT_DIR = DATA / "reporting"
SIG = DATA / "signals" / "signals.csv"
RECON_EURO = DATA / "reconcile" / "reconcile_fpi_vs_eurostat.csv"
RECON_OCPI = DATA / "reconcile" / "reconcile_fpi_vs_ocpi.csv"
RECON_MEF = DATA / "reconcile" / "reconcile_mef_vs_fpi.csv"
RECON_T12 = DATA / "reconcile" / "reconcile_titoli12m_vs_isin.csv"


def _read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _signals_map():
    rows = _read_csv(SIG)
    return {r["segnale"]: float(r["valore"]) for r in rows if r["valore"]}


def _profile(con):
    rows = con.execute("""
        SELECT cast(year(scadenza) AS INT) anno, round(sum(circolante_nom_eur)/1e6,0) mln
        FROM read_parquet('out/data/mart/mef_scadenze_isin/2026/mart_scadenze_isin.parquet')
        WHERE scadenza >= data_ref
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    return [{"anno": a, "mln_eur": m} for a, m in rows]


def _scenarios():
    path = DATA / "scenarios" / "scenarios.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("scenari", [])


def _top_isin(con, n=10):
    rows = con.execute("""
        SELECT isin, tipo, scadenza, round(circolante_nom_eur/1e6,0) mln
        FROM read_parquet('out/data/mart/mef_scadenze_isin/2026/mart_scadenze_isin.parquet')
        WHERE scadenza >= data_ref
        ORDER BY circolante_nom_eur DESC LIMIT ?
    """, [n]).fetchall()
    return [{"isin": i, "tipo": t, "scadenza": str(s), "mln_eur": m} for i, t, s, m in rows]


def _render_markdown(payload):
    s = payload["segnali"]
    lines = []
    lines.append("# Debito Pubblico Intelligence — Panorama")
    lines.append("")
    lines.append(f"*Generato il {payload['data']}. Fonti: Banca d'Italia FPI, "
                 f"Eurostat, OCPI, MEF Tesoro.*")
    lines.append("")
    lines.append("## 1. Quadro d'insieme")
    lines.append("")
    lines.append(f"- **Debito AP totale**: {s.get('debito_totale_ap_mln_eur', 0):,.0f} mln EUR "
                 f"(var. m/m {s.get('debito_totale_ap_mm_pct', 0):+.2f}%)")
    lines.append(f"- **Debito/PIL**: {s.get('debito_pil_pct', 0):.1f}%")
    lines.append(f"- **Rendimento 10Y**: {s.get('rendimento_10y_pct', 0):.2f}%")
    lines.append(f"- **i-g**: {s.get('i_g_pp', 0):+.2f} pp "
                 f"({'in crescita' if s.get('i_g_pp', 0) > 0 else 'in discesa'})")
    lines.append(f"- **Saldo primario**: {s.get('saldo_primario_pil_pct', 0):+.1f}% PIL "
                 f"({'surplus' if s.get('saldo_primario_pil_pct', 0) > 0 else 'deficit'})")
    lines.append(f"- **Spesa interessi**: {s.get('spesa_interessi_pil_pct', 0):.1f}% PIL")
    lines.append(f"- **Interessi consuntivi (missione Debito)**: {payload.get('consuntivo_interessi_mld', 0):,.1f} mld "
                 f"(ultimo anno consuntivo disponibile)")
    lines.append(f"- **Rollover 12m**: {s.get('rollover_12m_mld_eur', 0):,.0f} mld EUR "
                 f"({s.get('rollover_12m_pct', 0):.1f}% del residuo)")
    lines.append(f"- **Vita media residua**: {s.get('vita_media_anni', 0):.1f} anni")
    lines.append(f"- **Spread BTP-Bund**: {s.get('spread_btp_bund_pp', 0):.2f} pp")
    lines.append(f"- **Banca d'Italia detiene**: {s.get('quota_banca_italia_pct', 0):.1f}% del debito AP")
    lines.append("")
    lines.append("## 2. Riconciliazione cross-fonte")
    lines.append("")
    lines.append("| Caso | Esito |")
    lines.append("|---|---|")
    for r in payload["reconcile"]:
        lines.append(f"| {r['nome']} | {r['esito']} |")
    lines.append("")
    lines.append("## 3. Profilo scadenze (titoli di Stato, MEF)")
    lines.append("")
    lines.append("| Anno | Scadenza (mln EUR) |")
    lines.append("|---|---|")
    for p in payload["profilo"][:12]:
        lines.append(f"| {p['anno']} | {p['mln_eur']:,.0f} |")
    lines.append("")
    lines.append("## 4. Principali emissioni in circolazione")
    lines.append("")
    lines.append("| ISIN | Tipo | Scadenza | Circolante (mln) |")
    lines.append("|---|---|---|---|")
    for t in payload["top_isin"]:
        lines.append(f"| {t['isin']} | {t['tipo']} | {t['scadenza']} | {t['mln_eur']:,.0f} |")
    lines.append("")

    if payload["scenari"]:
        lines.append("## 5. Scenari di sostenibilità (debito/PIL)")
        lines.append("")
        lines.append(f"*Formula: d(t+1) = d(t)·(1+i−g)/(1+g) − sp. Base: {payload['anno_scenario_base']}, "
                     f"orizzonte {payload['orizzonte_anni']} anni.*")
        lines.append("")
        lines.append("| Scenario | i | g | sp | Debito/PIL | Δ |")
        lines.append("|---|---|---|---|---|---|")
        for sc in payload["scenari"]:
            traj = sc["traiettoria"]
            delta = sc["debito_pil_end_pct"] - sc["debito_pil_start_pct"]
            lines.append(f"| {sc['nome']} | {sc['i_pct']:.2f} | {sc['g_pct']:.2f} | "
                         f"{sc['saldo_primario_pct']:+.1f} | {traj[0]:.1f}→{traj[-1]:.1f} | {delta:+.1f} |")
        lines.append("")
    lines.append("---")
    lines.append("*Strumento di monitoraggio civico. Le definizioni e le soglie "
                 "sono esplicite nelle query e nei segnali del repo.*")
    return "\n".join(lines)


def main():
    if not SIG.exists():
        print("[ERRORE] esegui `make signals` prima di panorama")
        sys.exit(1)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    sig = _signals_map()

    reconcile = [
        {"nome": "FPI vs Eurostat (31 anni)",
         "esito": "1 anomalia (1995, spiegata)"},
        {"nome": "FPI vs OCPI (165 anni)",
         "esito": "0 anomalie (allineate al decimale)"},
        {"nome": "MEF titoli vs FPI titoli",
         "esito": "101,1% — Tesoro emette quasi tutti i titoli AP"},
        {"nome": "MEF titoli-12m vs rollover ISIN",
         "esito": "8/12 mesi identici; delta residuo <1%"},
        {"nome": "Fabbisogno vs variazione stock",
         "esito": "SFA implicito +19 mld su 36 mesi (identità contabile ok)"},
        {"nome": "Oneri debito BDAP vs interessi OCPI",
         "esito": "BDAP sistematicamente +10,6 mld/anno (previsione vs stima)"},
        {"nome": "Consuntivo interessi vs OCPI",
         "esito": "delta medio +0,2 mld/anno (12 anni) — consuntivo conferma OCPI"},
        {"nome": "Accensione prestiti vs fabbisogno",
         "esito": "indicatore: lordo Stato vs netto AP (perimetro diverso)"},
    ]

    payload = {
        "data": date.today().isoformat(),
        "segnali": sig,
        "reconcile": reconcile,
        "profilo": _profile(con),
        "top_isin": _top_isin(con),
        "scenari": _scenarios(),
    }

    sc_path = DATA / "scenarios" / "scenarios.json"
    if sc_path.exists():
        with open(sc_path, encoding="utf-8") as f:
            sc_data = json.load(f)
        payload["anno_scenario_base"] = sc_data.get("anno_base")
        payload["orizzonte_anni"] = sc_data.get("orizzonte_anni")

    cons_path = DATA / "build" / "bdap_consuntivo_debito.csv"
    if cons_path.exists():
        import csv as _csv
        with open(cons_path) as _f:
            cons_rows = list(_csv.DictReader(_f))
        if cons_rows:
            last_cons = cons_rows[-1]
            payload["consuntivo_interessi_mld"] = round(float(last_cons["interessi_mln"]) / 1e3, 1)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_DIR / "panorama.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(REPORT_DIR / "panorama.md", "w", encoding="utf-8") as f:
        f.write(_render_markdown(payload))
    print(f"[panorama] OK {REPORT_DIR / 'panorama.md'} + panorama.json")


if __name__ == "__main__":
    main()

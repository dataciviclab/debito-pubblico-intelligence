#!/usr/bin/env python3
"""Step signals: segnali con soglie calibrate sullo storico."""

import csv
import duckdb
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datasets._shared.paths import (
    MART_EUROSTAT_DP, MART_EUROSTAT_R10, MART_FPI_AP, MART_FPI_DET,
    MART_MEF_SCAD, MART_MEF_VM, MART_OCPI, SIG_DIR,
)

# Path stringhe per le query SQL
A = str(MART_FPI_AP)
D = str(MART_FPI_DET)
EDP = str(MART_EUROSTAT_DP)
R10 = str(MART_EUROSTAT_R10)
OC = str(MART_OCPI)
SC = str(MART_MEF_SCAD)
VM = str(MART_MEF_VM)

SIGNAL_QUERIES = {
    "debito_totale_ap_mln_eur": (
        f"SELECT valore_mln_eur FROM read_parquet('{A}') "
        "WHERE tavola_nome='debito_ap_sottosettori' AND codice='S13.MGD' ORDER BY data DESC LIMIT 1"
    ),
    "debito_totale_ap_mm_pct": (
        f"WITH s AS (SELECT valore_mln_eur FROM read_parquet('{A}') "
        "WHERE tavola_nome='debito_ap_sottosettori' AND codice='S13.MGD' ORDER BY data DESC LIMIT 2) "
        "SELECT (max(valore_mln_eur) - min(valore_mln_eur)) / min(valore_mln_eur) * 100 FROM s"
    ),
    "rendimento_10y_pct": (
        f"SELECT rendimento_pct FROM read_parquet('{R10}') "
        "WHERE paese='IT' ORDER BY mese DESC LIMIT 1"
    ),
    "debito_pil_pct": (
        f"SELECT debito_pil_pct FROM read_parquet('{EDP}') "
        "WHERE settore='S13' ORDER BY anno DESC LIMIT 1"
    ),
    "i_g_pp": (
        f"SELECT valore FROM read_parquet('{OC}') "
        "WHERE serie='S' ORDER BY anno DESC LIMIT 1"
    ),
    "saldo_primario_pil_pct": (
        f"SELECT valore FROM read_parquet('{OC}') "
        "WHERE serie='G' ORDER BY anno DESC LIMIT 1"
    ),
    "spesa_interessi_pil_pct": (
        f"SELECT valore FROM read_parquet('{OC}') "
        "WHERE serie='I' ORDER BY anno DESC LIMIT 1"
    ),
    "rollover_12m_pct": (
        f"WITH t AS (SELECT sum(circolante_nom_eur) tot FROM read_parquet('{SC}') "
        "WHERE scadenza >= data_ref), "
        f"r AS (SELECT sum(circolante_nom_eur) r12 FROM read_parquet('{SC}') "
        "WHERE scadenza >= data_ref AND scadenza < date_add(data_ref, INTERVAL 12 MONTH)) "
        "SELECT round(r12 / tot * 100, 1) FROM t, r"
    ),
    "rollover_12m_mld_eur": (
        f"SELECT round(sum(circolante_nom_eur) / 1e9, 1) FROM read_parquet('{SC}') "
        "WHERE scadenza >= data_ref AND scadenza < date_add(data_ref, INTERVAL 12 MONTH)"
    ),
    "vita_media_anni": (
        f"SELECT round(max(vita_media_mesi) / 12.0, 2) FROM read_parquet('{VM}') "
        "WHERE tipologia = 'TOTALE'"
    ),
    "spread_btp_bund_pp": (
        f"WITH it AS (SELECT rendimento_pct r FROM read_parquet('{R10}') "
        "WHERE paese='IT' ORDER BY mese DESC LIMIT 1), "
        f"de AS (SELECT rendimento_pct r FROM read_parquet('{R10}') "
        "WHERE paese='DE' ORDER BY mese DESC LIMIT 1) "
        "SELECT round(it.r - de.r, 2) FROM it, de"
    ),
    "quota_banca_italia_pct": (
        f"SELECT round((SELECT valore_mln_eur FROM read_parquet('{D}') "
        "WHERE codice='S13.MGD.S121' AND data=(SELECT max(data) FROM read_parquet('" + D + "') WHERE codice='S13.MGD.S121')) "
        "/ (SELECT valore_mln_eur FROM read_parquet('" + A + "') "
        "WHERE tavola_nome='debito_ap_sottosettori' AND codice='S13.MGD' AND data=(SELECT max(data) FROM read_parquet('" + A + "') WHERE tavola_nome='debito_ap_sottosettori' AND codice='S13.MGD')) * 100, 1)"
    ),
}

SIGNAL_META = {
    "debito_totale_ap_mln_eur": ("debito totale AP (mln EUR)", "debito", None),
    "debito_totale_ap_mm_pct": ("variazione debito m/m (%)", "debito", None),
    "rendimento_10y_pct": ("rendimento 10Y (%)", "costo", None),
    "debito_pil_pct": ("debito/PIL (%)", "sostenibilita", ">130: alto"),
    "i_g_pp": ("i-g (pp)", "sostenibilita", ">0: debito cresce da solo"),
    "saldo_primario_pil_pct": ("saldo primario (% PIL)", "sostenibilita", "<0: nuovo debito per gestione"),
    "spesa_interessi_pil_pct": ("spesa interessi (% PIL)", "sostenibilita", None),
    "rollover_12m_pct": ("debito in scadenza prossimi 12m (%)", "rischio", ">15%: rollover elevato"),
    "rollover_12m_mld_eur": ("debito in scadenza prossimi 12m (mld EUR)", "rischio", None),
    "vita_media_anni": ("vita media residua titoli (anni)", "rischio", "<5: durata corta"),
    "spread_btp_bund_pp": ("spread BTP-Bund 10Y (pp)", "costo", ">2: pressione mercato"),
    "quota_banca_italia_pct": ("debito AP detenuto da Bd'Italia (%)", "detentori", None),
}


def run():
    SIG_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    with duckdb.connect() as con:
        for name, query in SIGNAL_QUERIES.items():
            try:
                val = con.execute(query).fetchone()
            except Exception as exc:
                print(f"[signals] skip {name}: {exc}")
                continue
            if val is None or val[0] is None:
                continue
            value = float(val[0])
            label, cat, soglia = SIGNAL_META[name]
            report.append({"segnale": name, "descrizione": label, "categoria": cat, "valore": round(value, 3)})
            msg = f"[signals] {label}: {value:.3f}"
            if soglia:
                msg += f"  ({soglia})"
            print(msg)
    out = SIG_DIR / "signals.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["segnale", "descrizione", "categoria", "valore"])
        w.writeheader()
        w.writerows(report)
    print(f"[signals] OK {out}: {len(report)} segnali")


if __name__ == "__main__":
    run()

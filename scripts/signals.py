"""Calcola i segnali del debito dai MART e scrive data/signals/signals.csv.

I segnali sono il contratto "macchina" del repo: la dashboard li mostra, un
eventuale consumatore esterno li legge senza rifare i conti. Per questo si
calcolano **solo dai mart** (non dal clean, non da GCS) e ogni riga porta la
propria data di riferimento.

Regola: un segnale che non si riesce a calcolare resta fuori dal file con un
warning. Meglio un KPI assente che un numero vecchio spacciato per attuale.

Uso: python scripts/signals.py [output.csv]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
MART = ROOT / "out" / "data" / "mart"
OUTPUT = ROOT / "data" / "signals" / "signals.csv"

FIELDS = ["segnale", "categoria", "descrizione", "valore", "unita", "data_riferimento"]


def p(slug: str, table: str) -> Path:
    return MART / slug / "2026" / f"{table}.parquet"


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    con = duckdb.connect()
    righe: list[dict] = []

    def segnale(nome, categoria, descrizione, unita, valore, data_ref):
        if valore is None:
            print(f"[signals] salto {nome}: valore non disponibile")
            return
        righe.append({
            "segnale": nome,
            "categoria": categoria,
            "descrizione": descrizione,
            "valore": round(float(valore), 3),
            "unita": unita,
            "data_riferimento": data_ref,
        })

    def query(path: Path, sql: str):
        if not path.exists():
            print(f"[signals] manca {path.relative_to(ROOT)}")
            return None
        return con.execute(sql.replace("{t}", str(path))).fetchall()

    # ── Debito e sostenibilità (FPI + OCPI + Eurostat) ────────────────
    r = query(p("fpi_debito_pa", "mart_debito_ap"), """
        SELECT round(valore_mln_eur, 1), data FROM read_parquet('{t}')
        WHERE tavola_nome = 'debito_ap_sottosettori' AND codice = 'S13.MGD'
        ORDER BY data DESC LIMIT 1
    """)
    if r:
        segnale("debito_totale_ap_mln_eur", "debito", "Debito lordo Amministrazioni Pubbliche",
                "mln EUR", r[0][0], r[0][1])

    r = query(p("fpi_debito_pa", "mart_variazione_mensile"), """
        SELECT delta_pct, data FROM read_parquet('{t}') ORDER BY data DESC LIMIT 1
    """)
    if r:
        segnale("debito_variazione_mensile_pct", "debito", "Variazione mensile del debito AP",
                "%", r[0][0], r[0][1])

    r = query(p("eurostat_debito_pil", "mart_debito_pil"), """
        SELECT debito_pil_pct, anno FROM read_parquet('{t}')
        WHERE settore = 'S13' ORDER BY anno DESC LIMIT 2
    """)
    if r:
        segnale("debito_pil_pct", "sostenibilita", "Debito/PIL Amministrazioni Pubbliche",
                "% PIL", r[0][0], r[0][1])
        if len(r) > 1:
            segnale("debito_pil_variazione_pp", "sostenibilita", "Variazione annua del debito/PIL",
                    "pp", float(r[0][0]) - float(r[1][0]), r[0][1])

    for serie, nome, descr, unita in (
        ("S", "i_g_pp", "Differenza tra interessi impliciti e crescita nominale", "pp"),
        ("G", "saldo_primario_pil_pct", "Saldo primario", "% PIL"),
        ("I", "spesa_interessi_pil_pct", "Spesa per interessi", "% PIL"),
        ("R", "tasso_implicito_pct", "Tasso di interesse implicito sul debito", "%"),
    ):
        r = query(p("ocpi_serie_storiche", "mart_serie_storiche"), f"""
            SELECT valore, anno FROM read_parquet('{{t}}')
            WHERE serie = '{serie}' ORDER BY anno DESC LIMIT 1
        """)
        if r:
            segnale(nome, "sostenibilita", descr, unita, r[0][0], r[0][1])

    # ── Costo (Eurostat rendimenti) ───────────────────────────────────
    r = query(p("eurostat_rendimento_10y", "mart_rendimento_10y"), """
        SELECT paese, mese, rendimento_pct FROM read_parquet('{t}')
        WHERE mese = (SELECT max(mese) FROM read_parquet('{t}'))
    """)
    if r:
        valore = {paese: (v, mese) for paese, mese, v in r}
        if "IT" in valore:
            segnale("rendimento_10y_pct", "costo", "Rendimento BTP a 10 anni",
                    "%", valore["IT"][0], valore["IT"][1])
            if "DE" in valore:
                segnale("spread_btp_bund_pp", "costo", "Spread BTP-Bund a 10 anni",
                        "pp", float(valore["IT"][0]) - float(valore["DE"][0]), valore["IT"][1])

    # ── Struttura del debito (MEF) ────────────────────────────────────
    r = query(p("mef_scadenze_isin", "mart_rollover_12m"), """
        SELECT round(sum(scadenza_12m_mln_eur) / sum(scadenza_mln_eur) * 100, 1),
               round(sum(scadenza_12m_mln_eur) / 1000, 1),
               max(data_ref)
        FROM read_parquet('{t}')
    """)
    if r:
        segnale("rollover_12m_pct", "rischio", "Quota di titoli in scadenza nei prossimi 12 mesi",
                "%", r[0][0], r[0][2])
        segnale("rollover_12m_mld_eur", "rischio", "Titoli in scadenza nei prossimi 12 mesi",
                "mld EUR", r[0][1], r[0][2])

    r = query(p("mef_vita_media", "mart_vita_media"), """
        SELECT round(vita_media_mesi / 12.0, 2), mese FROM read_parquet('{t}')
        WHERE tipologia = 'TOTALE' ORDER BY mese DESC LIMIT 1
    """)
    if r:
        segnale("vita_media_anni", "rischio", "Vita media residua dei titoli di Stato",
                "anni", r[0][0], r[0][1])

    # Detentori: si usa la data piu' recente in cui esistono TUTTE le voci
    # (i non residenti vengono pubblicati con un mese di ritardo).
    r = query(p("fpi_debito_pa", "mart_detentori"), """
        WITH ultima AS (
            SELECT max(data) AS d FROM read_parquet('{t}') WHERE codice = 'S13.MGD.S2'
        )
        SELECT codice, valore_mln_eur, data FROM read_parquet('{t}')
        WHERE data = (SELECT coalesce((SELECT d FROM ultima),
                                      (SELECT max(data) FROM read_parquet('{t}'))))
    """)
    if r:
        det = {codice: valore for codice, valore, _ in r}
        data_ref = r[0][2]
        debito = det.get("S13.MGD.SBI3")
        if debito:
            if det.get("S13.MGD.S121"):
                segnale("quota_banca_italia_pct", "detentori", "Quota del debito AP detenuta dalla Banca d'Italia",
                        "%", det["S13.MGD.S121"] / debito * 100, data_ref)
            if det.get("S13.MGD.S2"):
                segnale("quota_non_residenti_pct", "detentori", "Quota del debito AP detenuta da non residenti",
                        "%", det["S13.MGD.S2"] / debito * 100, data_ref)

    r = query(p("mef_composizione", "mart_composizione"), """
        SELECT round(max(CASE WHEN tipologia = 'Totale' THEN valore_mln_eur END) / 1000, 1),
               max(data_ref)
        FROM read_parquet('{t}')
        WHERE data_ref = (SELECT max(data_ref) FROM read_parquet('{t}'))
    """)
    if r and r[0][0]:
        segnale("titoli_in_circolazione_mld_eur", "debito", "Titoli di Stato in circolazione",
                "mld EUR", r[0][0], r[0][1])

    r = query(p("mef_scadenze_isin", "mart_scadenze_isin"), """
        SELECT round(sum(cedola_pct * circolante_nom_eur) / sum(circolante_nom_eur), 2),
               max(data_ref)
        FROM read_parquet('{t}')
        WHERE classe_strumento = 'Titoli di Stato'
          AND stato = 'in_circolazione'
          AND cedola_pct IS NOT NULL
    """)
    if r and r[0][0]:
        segnale("cedola_media_ponderata_pct", "costo", "Cedola media ponderata sullo stock (solo titoli con cedola fissa)",
                "%", r[0][0], r[0][1])

    # ── Costo del debito (compose debt_service) ───────────────────────
    r = query(p("debt_service", "mart_interessi_annui"), """
        SELECT round(sum(interessi_mln_eur) / 1000, 1), max(data_ref)
        FROM read_parquet('{t}')
    """)
    if r and r[0][0]:
        segnale("interessi_annui_titoli_mld_eur", "costo", "Interessi annui sui titoli di Stato in circolazione (stima: BOT a tasso 12m, CCTeu Euribor 6m + spread)",
                "mld EUR", r[0][0], r[0][1])

    r = query(p("debt_service", "mart_debt_service_12m"), """
        SELECT round(sum(delta_interessi_mln_eur) / 1000, 1),
               round(sum(rimborsi_mln_eur) / 1000, 1),
               max(data_ref)
        FROM read_parquet('{t}')
    """)
    if r and r[0][0] is not None:
        segnale("costo_rifinanziamento_12m_mld_eur", "costo", "Costo annuo aggiuntivo di rifinanziare i titoli in scadenza nei prossimi 12 mesi ai tassi correnti",
                "mld EUR", r[0][0], r[0][2])

    if not righe:
        print("[signals] nessun segnale calcolato: pipeline non eseguita?")
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(righe)
    print(f"[signals] OK {output.relative_to(ROOT)}: {len(righe)} segnali")


if __name__ == "__main__":
    main()

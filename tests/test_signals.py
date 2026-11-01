"""
Contratto degli artefatti `signals.csv`.

Il 2026-11-01 `data/signals/signals.csv` e `data/reporting/panorama.*` erano
orfani: nessun target li rigenerava, quindi mostravano numeri del 2026-09-01
spacciati per attuali. Ora `scripts/signals.py` li calcola dai mart e deve
restare allineato a loro: questi test verificano contratto, plausibilità e
coerenza con i mart.
"""

import csv
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
SIGNALS = ROOT / "data" / "signals" / "signals.csv"
MART = ROOT / "out" / "data" / "mart"

RICHIESTI = {
    "debito_totale_ap_mln_eur",
    "debito_pil_pct",
    "debito_pil_variazione_pp",
    "i_g_pp",
    "saldo_primario_pil_pct",
    "spesa_interessi_pil_pct",
    "rendimento_10y_pct",
    "spread_btp_bund_pp",
    "rollover_12m_pct",
    "rollover_12m_mld_eur",
    "vita_media_anni",
    "quota_banca_italia_pct",
    "titoli_in_circolazione_mld_eur",
}

# intervalli di plausibilità: se il calcolo si rompe, il numero esce da qui
RANGE = {
    "debito_totale_ap_mln_eur": (1_500_000, 5_000_000),
    "debito_pil_pct": (80, 200),
    "i_g_pp": (-15, 15),
    "saldo_primario_pil_pct": (-15, 10),
    "spesa_interessi_pil_pct": (1, 10),
    "rendimento_10y_pct": (-1, 15),
    "spread_btp_bund_pp": (-1, 10),
    "rollover_12m_pct": (5, 30),
    "rollover_12m_mld_eur": (100, 700),
    "vita_media_anni": (3, 10),
    "quota_banca_italia_pct": (0, 50),
    "titoli_in_circolazione_mld_eur": (1500, 4000),
}


def _load():
    if not SIGNALS.exists():
        pytest.skip(f"signals.csv non presente: {SIGNALS}")
    with open(SIGNALS, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.contract
class TestSignals:
    def test_contratto(self):
        righe = _load()
        assert righe, "signals.csv vuoto"
        assert set(righe[0].keys()) == {
            "segnale", "categoria", "descrizione", "valore", "unita", "data_riferimento"
        }, "schema cambiato"

    def test_segnali_chiave_presenti(self):
        mancanti = RICHIESTI - {r["segnale"] for r in _load()}
        assert not mancanti, f"segnali mancanti: {mancanti}"

    def test_nessun_valore_vuoto(self):
        for r in _load():
            assert r["valore"] not in ("", "None", "nan"), f"{r['segnale']} senza valore"
            assert r["data_riferimento"], f"{r['segnale']} senza data di riferimento"

    def test_valori_plausibili(self):
        for r in _load():
            limiti = RANGE.get(r["segnale"])
            if not limiti:
                continue
            v = float(r["valore"])
            assert limiti[0] <= v <= limiti[1], f"{r['segnale']} = {v} fuori da {limiti}"

    def test_rollover_coerente_col_mart(self):
        mart = MART / "mef_scadenze_isin" / "2026" / "mart_rollover_12m.parquet"
        if not mart.exists():
            pytest.skip(f"mart non presente: {mart}")
        con = duckdb.connect()
        atteso = con.execute(
            f"SELECT round(sum(scadenza_12m_mln_eur)/sum(scadenza_mln_eur)*100, 1) "
            f"FROM read_parquet('{mart}')"
        ).fetchone()[0]
        segnale = next(r for r in _load() if r["segnale"] == "rollover_12m_pct")
        assert float(segnale["valore"]) == pytest.approx(atteso, abs=0.05)

    def test_titoli_coerente_col_mart(self):
        mart = MART / "mef_composizione" / "2026" / "mart_composizione.parquet"
        if not mart.exists():
            pytest.skip(f"mart non presente: {mart}")
        con = duckdb.connect()
        atteso = con.execute(
            f"SELECT round(max(CASE WHEN tipologia='Totale' THEN valore_mln_eur END)/1000, 1) "
            f"FROM read_parquet('{mart}') "
            f"WHERE data_ref = (SELECT max(data_ref) FROM read_parquet('{mart}'))"
        ).fetchone()[0]
        segnale = next(r for r in _load() if r["segnale"] == "titoli_in_circolazione_mld_eur")
        assert float(segnale["valore"]) == pytest.approx(atteso, abs=0.1)

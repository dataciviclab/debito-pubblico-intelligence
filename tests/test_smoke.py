"""
Smoke test di integrità: verifica che i layer prodotti esistano e abbiano forma
attesa. Antidoto alle regressioni — run rapido dopo `make all`.

Migrato a pytest (Fase 0 allineamento Lab). I path puntano sia al legacy
(data/) che al toolkit (out/data/) per compatibilità transitoria.
"""

import json
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLKIT_OUT = ROOT / "out" / "data"

TOOLKIT_MART_DP = TOOLKIT_OUT / "mart" / "eurostat_debito_pil" / "2026" / "mart_debito_pil.parquet"
TOOLKIT_MART_R10 = TOOLKIT_OUT / "mart" / "eurostat_rendimento_10y" / "2026" / "mart_rendimento_10y.parquet"
TOOLKIT_MART_FPI_DP = TOOLKIT_OUT / "mart" / "fpi_debito_pa" / "2026" / "mart_debito_ap.parquet"
TOOLKIT_MART_FPI_FAB = TOOLKIT_OUT / "mart" / "fpi_debito_pa" / "2026" / "mart_fabbisogno.parquet"
TOOLKIT_MART_FPI_DET = TOOLKIT_OUT / "mart" / "fpi_debito_pa" / "2026" / "mart_detentori.parquet"
TOOLKIT_MART_OCPI = TOOLKIT_OUT / "mart" / "ocpi_serie_storiche" / "2026" / "mart_serie_storiche.parquet"
TOOLKIT_MART_MEF_SCAD = TOOLKIT_OUT / "mart" / "mef_scadenze_isin" / "2026" / "mart_scadenze_isin.parquet"

# Legacy output (reconcile) — still produced by scripts/
RECON_EURO = ROOT / "data" / "reconcile" / "reconcile_fpi_vs_eurostat.csv"
RECON_OCPI = ROOT / "data" / "reconcile" / "reconcile_fpi_vs_ocpi.csv"
RECON_MEF = ROOT / "data" / "reconcile" / "reconcile_mef_vs_fpi.csv"
RECON_T12 = ROOT / "data" / "reconcile" / "reconcile_titoli12m_vs_isin.csv"
RECON_FAB = ROOT / "data" / "reconcile" / "reconcile_fabbisogno_vs_stock.csv"
RECON_ONERI = ROOT / "data" / "reconcile" / "reconcile_oneri_bdap_vs_ocpi.csv"
RECON_CONS = ROOT / "data" / "reconcile" / "reconcile_consuntivo_vs_ocpi.csv"
RECON_ACC = ROOT / "data" / "reconcile" / "reconcile_accensione_vs_fabbisogno.csv"
RECON_SUMMARY = ROOT / "data" / "reconcile" / "summary.json"


# ---------------------------------------------------------------------------
# Toolkit layer tests
# ---------------------------------------------------------------------------

@pytest.mark.contract
class TestToolkitEurostatDebitoPil:
    def test_mart_exists(self):
        assert TOOLKIT_MART_DP.exists(), f"mart mancante: {TOOLKIT_MART_DP}"

    def test_mart_non_empty(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TOOLKIT_MART_DP}')").fetchone()[0]
        assert n > 0, "mart eurostat_debito_pil vuoto"

    def test_mart_schema(self):
        con = duckdb.connect()
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{TOOLKIT_MART_DP}')").fetchall()]
        required = {"anno", "settore", "debito_pil_pct", "stock_mln_eur"}
        assert required.issubset(set(cols)), f"colonne mancanti: {required - set(cols)}"


@pytest.mark.contract
class TestToolkitEurostatRendimento10y:
    def test_mart_exists(self):
        assert TOOLKIT_MART_R10.exists(), f"mart mancante: {TOOLKIT_MART_R10}"

    def test_mart_non_empty(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TOOLKIT_MART_R10}')").fetchone()[0]
        assert n > 0, "mart eurostat_rendimento_10y vuoto"

    def test_mart_schema(self):
        con = duckdb.connect()
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{TOOLKIT_MART_R10}')").fetchall()]
        required = {"mese", "paese", "rendimento_pct"}
        assert required.issubset(set(cols)), f"colonne mancanti: {required - set(cols)}"


# ---------------------------------------------------------------------------
# Toolkit FPI tests
# ---------------------------------------------------------------------------

@pytest.mark.contract
class TestToolkitFpiDebitoPa:
    def test_mart_debito_ap_exists(self):
        assert TOOLKIT_MART_FPI_DP.exists(), f"mart mancante: {TOOLKIT_MART_FPI_DP}"

    def test_mart_debito_ap_non_empty(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TOOLKIT_MART_FPI_DP}')").fetchone()[0]
        assert n > 10000, f"mart_debito_ap troppo piccolo: {n}"

    def test_mart_debito_ap_has_4_tavole(self):
        con = duckdb.connect()
        tavole = con.execute(f"SELECT count(DISTINCT tavola) FROM read_parquet('{TOOLKIT_MART_FPI_DP}')").fetchone()[0]
        assert tavole == 4, f"attese 4 tavole, trovate {tavole}"

    def test_mart_fabbisogno_exists(self):
        assert TOOLKIT_MART_FPI_FAB.exists(), f"mart mancante: {TOOLKIT_MART_FPI_FAB}"

    def test_mart_fabbisogno_non_empty(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TOOLKIT_MART_FPI_FAB}')").fetchone()[0]
        assert n > 1000, f"mart_fabbisogno troppo piccolo: {n}"

    def test_mart_detentori_exists(self):
        assert TOOLKIT_MART_FPI_DET.exists(), f"mart mancante: {TOOLKIT_MART_FPI_DET}"

    def test_mart_detentori_non_empty(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TOOLKIT_MART_FPI_DET}')").fetchone()[0]
        assert n > 500, f"mart_detentori troppo piccolo: {n}"


# ---------------------------------------------------------------------------
# Toolkit OCPI tests
# ---------------------------------------------------------------------------

@pytest.mark.contract
class TestToolkitOcpiSerieStoriche:
    def test_mart_exists(self):
        assert TOOLKIT_MART_OCPI.exists(), f"mart mancante: {TOOLKIT_MART_OCPI}"

    def test_mart_non_empty(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{TOOLKIT_MART_OCPI}')").fetchone()[0]
        assert n > 3000, f"mart ocpi troppo piccolo: {n}"

    def test_mart_has_all_series(self):
        con = duckdb.connect()
        n = con.execute(f"SELECT count(DISTINCT serie) FROM read_parquet('{TOOLKIT_MART_OCPI}')").fetchone()[0]
        assert n >= 25, f"meno di 25 serie: {n}"

    def test_mart_covers_history(self):
        con = duckdb.connect()
        min_y, max_y = con.execute(f"SELECT min(anno), max(anno) FROM read_parquet('{TOOLKIT_MART_OCPI}')").fetchone()
        assert min_y <= 1870, f"serie non inizia prima del 1870: {min_y}"
        assert max_y >= 2024, f"serie non arriva al 2024: {max_y}"


# ---------------------------------------------------------------------------
# Legacy output tests (reconcile/signals/scenarios/panorama)
# These files are still produced by the legacy scripts/ pipeline.
# Tests skip gracefully if files are not present.
# ---------------------------------------------------------------------------


def _skip_if_missing(path):
    """Return True if file should be skipped (not found)."""
    return not path.exists()


@pytest.mark.contract
class TestLegacyReconcile:
    @pytest.mark.parametrize("name,path,min_rows", [
        ("eurostat", RECON_EURO, 10),
        ("ocpi", RECON_OCPI, 50),
        ("mef", RECON_MEF, 1),
        ("titoli12m", RECON_T12, 6),
        ("fabbisogno", RECON_FAB, 0),
        ("oneri", RECON_ONERI, 5),
        ("consuntivo", RECON_CONS, 5),
        ("accensione", RECON_ACC, 5),
    ])
    def test_reconcile_populated(self, name, path, min_rows):
        if _skip_if_missing(path):
            pytest.skip(f"legacy reconcile {name} non presente (pipeline non eseguita)")
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_csv('{path}')").fetchone()[0]
        assert n >= min_rows, f"reconcile {name}: {n} righe < minimo {min_rows}"


@pytest.mark.contract
class TestReconcileSummary:
    def test_json_exists(self):
        if _skip_if_missing(RECON_SUMMARY):
            pytest.skip("summary.json non presente (make reconcile non eseguito)")
        assert RECON_SUMMARY.exists()

    def test_has_enough_cases(self):
        if _skip_if_missing(RECON_SUMMARY):
            pytest.skip("summary.json non presente")
        with open(RECON_SUMMARY, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) >= 4, f"meno di 4 casi: {len(data)}"

    def test_cases_have_required_fields(self):
        if _skip_if_missing(RECON_SUMMARY):
            pytest.skip("summary.json non presente")
        with open(RECON_SUMMARY, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            assert "id" in item, f"caso senza id: {item}"
            assert "nome" in item, f"caso senza nome: {item}"
            assert "n_anomalie" in item, f"caso senza n_anomalie: {item}"

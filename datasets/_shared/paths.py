"""Shared path constants for all analytical scripts.

Points to the toolkit parquet output in out/data/mart/.
Import this module instead of hardcoding paths.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "out" / "data"

# --- Toolkit mart paths (per anno 2026) ---
MART_FPI_AP = OUT / "mart" / "fpi_debito_pa" / "2026" / "mart_debito_ap.parquet"
MART_FPI_FAB = OUT / "mart" / "fpi_debito_pa" / "2026" / "mart_fabbisogno.parquet"
MART_FPI_DET = OUT / "mart" / "fpi_debito_pa" / "2026" / "mart_detentori.parquet"
MART_EUROSTAT_DP = OUT / "mart" / "eurostat_debito_pil" / "2026" / "mart_debito_pil.parquet"
MART_EUROSTAT_R10 = OUT / "mart" / "eurostat_rendimento_10y" / "2026" / "mart_rendimento_10y.parquet"
MART_OCPI = OUT / "mart" / "ocpi_serie_storiche" / "2026" / "mart_serie_storiche.parquet"
MART_MEF_SCAD = OUT / "mart" / "mef_scadenze_isin" / "2026" / "mart_scadenze_isin.parquet"
MART_MEF_T12 = OUT / "mart" / "mef_titoli_12m" / "2026" / "mart_titoli_12m.parquet"
MART_MEF_VM = OUT / "mart" / "mef_vita_media" / "2026" / "mart_vita_media.parquet"
MART_MEF_COMP = OUT / "mart" / "mef_composizione" / "2026" / "mart_composizione.parquet"

# --- Legacy output paths (reconcile/signals still write here) ---
DATA = ROOT / "data"
RECON_DIR = DATA / "reconcile"
SIG_DIR = DATA / "signals"
SCEN_DIR = DATA / "scenarios"
REPORT_DIR = DATA / "reporting"

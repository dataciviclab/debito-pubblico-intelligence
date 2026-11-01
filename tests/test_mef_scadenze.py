"""
Regressioni sul dataset `mef_scadenze_isin`.

Proteggono i tre difetti trovati il 2026-11-01:
- la cedola del MEF arriva con l'etichetta nella stessa cella ("0,550 Cedola
  reale", '3,250 "step up"') e finiva NULL su ~364 mld di titoli;
- il file elenca anche prestiti UE (SURE/NGEU) e scadenze gia' passate: senza
  `classe_strumento` / `stato` lo stock risultava +18%;
- il simbolo € arriva come 0x80 e spaccava la famiglia in 'BTP\x80i' / 'BTP\x80I'.
"""

import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
MART = ROOT / "out" / "data" / "mart" / "mef_scadenze_isin" / "2026" / "mart_scadenze_isin.parquet"
ROLLOVER = ROOT / "out" / "data" / "mart" / "mef_scadenze_isin" / "2026" / "mart_rollover_12m.parquet"
COMPOSIZIONE = ROOT / "out" / "data" / "mart" / "mef_composizione" / "2026" / "mart_composizione.parquet"

sys.path.insert(0, str(ROOT / "datasets" / "_shared"))
from mef_common import parse_amount_leading


class TestParseAmountLeading:
    @pytest.mark.parametrize("raw,expected", [
        ("0,550  Cedola reale", 0.55),
        (" 1,300  Cedola reale", 1.3),
        ('3,250 "step up"', 3.25),
        ('0,350 "step-up"', 0.35),
        ("2,000", 2.0),
        ("-", None),
        ("n/d", None),
        ("", None),
    ])
    def test_coupon_cells(self, raw, expected):
        assert parse_amount_leading(raw) == expected


@pytest.mark.contract
class TestMartScadenzeIsin:
    def _con(self):
        if not MART.exists():
            pytest.skip(f"mart non presente: {MART}")
        return duckdb.connect()

    def test_contract_columns(self):
        con = self._con()
        cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{MART}')").fetchall()}
        required = {"isin", "tipo", "tipo_famiglia", "scadenza", "cedola_pct", "data_ref",
                    "classe_strumento", "stato"}
        assert required.issubset(cols), f"colonne mancanti: {required - cols}"

    def test_classificazione_completa(self):
        con = self._con()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{MART}') "
            "WHERE classe_strumento IS NULL OR stato IS NULL OR tipo_famiglia IS NULL"
        ).fetchone()[0]
        assert n == 0, f"{n} righe senza classe/stato/famiglia"

    def test_prestiti_ue_non_sono_titoli(self):
        con = self._con()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{MART}') "
            "WHERE (starts_with(isin, 'NGEU') OR starts_with(isin, 'SURE')) "
            "AND classe_strumento = 'Titoli di Stato'"
        ).fetchone()[0]
        assert n == 0, f"{n} prestiti UE classificati come titoli di Stato"

    def test_tipo_pulito_sui_titoli(self):
        con = self._con()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{MART}') "
            "WHERE classe_strumento = 'Titoli di Stato' "
            "AND regexp_matches(tipo, '^[0-9]+\\^ (rimborso|tranche)')"
        ).fetchone()[0]
        assert n == 0, f"{n} titoli con tipo tranche/rimborso"

    def test_famiglia_senza_mojibake(self):
        con = self._con()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{MART}') "
            "WHERE tipo_famiglia LIKE 'BTP' || chr(128) || '%'"
        ).fetchone()[0]
        assert n == 0, f"{n} righe con € non normalizzato nella famiglia"

    def test_copertura_cedole(self):
        """Non-BOT in circolazione senza cedola: solo il residuo Ispa (<3% dello stock)."""
        con = self._con()
        senza, stock = con.execute(
            f"SELECT round(sum(CASE WHEN cedola_pct IS NULL THEN circolante_nom_eur ELSE 0 END)/1e9, 2), "
            f"round(sum(circolante_nom_eur)/1e9, 2) FROM read_parquet('{MART}') "
            "WHERE classe_strumento = 'Titoli di Stato' AND stato = 'in_circolazione' "
            "AND NOT starts_with(tipo, 'BOT')"
        ).fetchone()
        assert senza / stock < 0.03, f"cedole mancanti {senza} mld su {stock} ({senza / stock:.1%})"

    def test_stock_riconcilia_con_composizione(self):
        """Stock ISIN in circolazione vs composizione MEF: entro il 3%.

        Le due fonti misurano lo stesso aggregato con valutazioni diverse (BTP€i
        rivalutato vs nominale, emissioni in valuta), quindi non e' un'identita'.
        Serve a intercettare il ritorno del +18% da prestiti UE e scadenze passate.
        """
        if not COMPOSIZIONE.exists():
            pytest.skip(f"mart non presente: {COMPOSIZIONE}")
        con = self._con()
        stock_isin = con.execute(
            f"SELECT round(sum(circolante_nom_eur)/1e9, 1) FROM read_parquet('{MART}') "
            "WHERE classe_strumento = 'Titoli di Stato' AND stato = 'in_circolazione'"
        ).fetchone()[0]
        stock_mef = con.execute(
            f"SELECT round(sum(valore_mln_eur)/1e3, 1) FROM read_parquet('{COMPOSIZIONE}') "
            "WHERE tipologia = 'Totale' "
            f"AND data_ref = (SELECT max(data_ref) FROM read_parquet('{COMPOSIZIONE}'))"
        ).fetchone()[0]
        delta = (stock_isin - stock_mef) / stock_mef
        assert abs(delta) < 0.03, f"stock ISIN {stock_isin} vs composizione {stock_mef} ({delta:+.1%})"


@pytest.mark.contract
class TestMartRollover:
    def test_rollover_12m_coerente(self):
        if not ROLLOVER.exists():
            pytest.skip(f"mart non presente: {ROLLOVER}")
        con = duckdb.connect()
        tot = con.execute(
            f"SELECT round(sum(scadenza_12m_mln_eur)/1000, 1) FROM read_parquet('{ROLLOVER}')"
        ).fetchone()[0]
        # 12 mesi mobili su ~2.700 mld di titoli: la finestra vale ~13-14%
        assert 300 <= tot <= 450, f"rollover 12m fuori scala: {tot} mld"

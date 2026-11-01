"""
Contratto del compose `debt_service`.

Il compose incrocia titoli in circolazione e tassi correnti. Le ipotesi sono
colonne (`ipotesi`, `tasso_usato_pct`): il test verifica che ci siano e che i
totali restino in scala. Se un domani cambia una fonte, il numero esce dai
range e il test lo dice.
"""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "out" / "data" / "mart" / "debt_service" / "2026"
INTERESSI = BASE / "mart_interessi_annui.parquet"
SERVICE = BASE / "mart_debt_service_12m.parquet"


def _con(path):
    if not path.exists():
        pytest.skip(f"mart non presente: {path}")
    return duckdb.connect()


@pytest.mark.contract
class TestInteressiAnnui:
    def test_contratto(self):
        con = _con(INTERESSI)
        cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{INTERESSI}')").fetchall()}
        assert {"famiglia", "stock_mln_eur", "tasso_usato_pct", "interessi_mln_eur", "ipotesi"}.issubset(cols)

    def test_ipotesi_sempre_presente(self):
        con = _con(INTERESSI)
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{INTERESSI}') WHERE ipotesi IS NULL OR ipotesi = ''"
        ).fetchone()[0]
        assert n == 0, f"{n} righe senza dichiarazione dell'ipotesi"

    def test_totale_in_scala(self):
        con = _con(INTERESSI)
        tot = con.execute(f"SELECT round(sum(interessi_mln_eur)/1000, 1) FROM read_parquet('{INTERESSI}')").fetchone()[0]
        assert 60 <= tot <= 120, f"interessi annui {tot} mld fuori scala"


@pytest.mark.contract
class TestDebtService12m:
    def test_chiave_unica(self):
        con = _con(SERVICE)
        dup = con.execute(
            f"SELECT count(*) FROM (SELECT famiglia FROM read_parquet('{SERVICE}') GROUP BY 1 HAVING count(*) > 1)"
        ).fetchone()[0]
        assert dup == 0

    def test_rimborsi_e_delta(self):
        con = _con(SERVICE)
        rimborsi, delta = con.execute(
            f"SELECT round(sum(rimborsi_mln_eur)/1000, 1), round(sum(delta_interessi_mln_eur)/1000, 1) "
            f"FROM read_parquet('{SERVICE}')"
        ).fetchone()
        assert 300 <= rimborsi <= 450, f"rimborsi 12m {rimborsi} mld fuori scala"
        assert 5 <= delta <= 15, f"costo di rifinanziamento {delta} mld fuori scala"

    def test_tassi_correnti_coerenti(self):
        """Il tasso corrente non può essere sotto la cedola storica per i BOT (erano a zero)."""
        con = _con(SERVICE)
        bot = con.execute(
            f"SELECT cedola_media_pct, tasso_corrente_pct FROM read_parquet('{SERVICE}') WHERE famiglia = 'BOT'"
        ).fetchone()
        if bot:
            assert bot[0] == 0 and bot[1] > 2, f"BOT: cedola {bot[0]}, corrente {bot[1]}"

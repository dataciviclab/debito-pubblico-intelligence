"""
Regressioni sul dataset `mef_composizione` (serie mensile).

Proteggono i difetti trovati il 2026-11-01:
- si scaricava solo l'ultimo CSV: nessuna storia, nessuna data di riferimento;
- le voci "di cui ..." e gli aggregati ("Totale", "Estero", "Altri programmi")
  venivano sommati alle foglie, gonfiando il totale di ~50 mld;
- i file in inglese (es. 30/06/2023) e le tabelle con intestazione spostata
  producevano zero righe;
- il simbolo € arrivava come 0x80 e spezzava la famiglia BTP€i dentro BTP.
"""

import importlib.util
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
MART = ROOT / "out" / "data" / "mart" / "mef_composizione" / "2026" / "mart_composizione.parquet"

_spec = importlib.util.spec_from_file_location(
    "mef_composizione_preprocess", ROOT / "datasets" / "mef-composizione" / "preprocess.py"
)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestFamiglie:
    @pytest.mark.parametrize("tip,fam", [
        ("BTP", "BTP"),
        ("BTP €i (rivalutato)", "BTP€i"),
        ("BTP€i (rivalutato)", "BTP€i"),
        ("BTP ?i (rivalutato)", "BTP€i"),
        ("BTP Italia (rivalutato)", "BTP Italia"),
        ("BTP Green", "BTP Green"),
        ("BTP Valore", "BTP Valore"),
        ("BTP Più", "BTP Più"),
        ("BOT", "BOT"),
        ("CCTeu", "CCTeu"),
        ("Estero in Euro", "Estero"),
        ("Emissioni in euro", "Estero"),
        ("Altri programmi di emissione (1)", "Estero"),
        ("di cui BTP Più", "sottoinsieme"),
    ])
    def test_famiglia(self, tip, fam):
        assert mod.famiglia(tip) == fam

    @pytest.mark.parametrize("tip,atteso", [
        ("Totale", True),
        ("Estero", True),
        ("Altri programmi di emissione (1)", True),
        ("Estero in Euro", False),
        ("BTP", False),
        ("di cui Titoli Ispa", False),
    ])
    def test_aggregato(self, tip, atteso):
        assert mod.is_aggregato(tip) is atteso

    def test_mojibake(self):
        assert mod.normalizza_tipologia("BTP" + chr(128) + "i (rivalutato)") == "BTP€i (rivalutato)"
        assert mod.normalizza_tipologia("BTP ?i (rivalutato)") == "BTP €i (rivalutato)"

    def test_famiglia_case_insensitive(self):
        assert mod.famiglia("Estero in euro") == "Estero"
        assert mod.famiglia("Estero in Euro") == "Estero"

    def test_etichette_inglesi(self):
        assert mod.normalizza_tipologia("BTPi (indexed)") == "BTP €i (rivalutato)"
        assert mod.normalizza_tipologia("of which  ISPA  Bonds") == "di cui Titoli Ispa"


class TestParseFile:
    ITALIANO = (
        "COMPOSIZIONE DEI TITOLI DI STATO;;;\n"
        "Tipologia titolo;mln. Euro;%;\n"
        "BTP;1.901.406,45;72,30%;\n"
        "BTP Green;73.055,57;1,87%;\n"
        "Totale;2.705.585,47;100%;\n"
        "Vita Media del Debito;6,96;;\n"
    )

    INGLESE = (
        "Government securities:;;\n"
        "breakdown by instrument as of June 30, 2023;;\n"
        ";;\n"
        "Bonds;Amount (mln. );%\n"
        "BOT;120,559.11;5.04%\n"
        "CCTeu;149,109.21;6.23%\n"
        "BTP;1,724,137.61;72.05%\n"
        "BTP Green;33,900.00;1.42%\n"
        "BTPi (indexed);193,728.95;8.10%\n"
        "BTP Italia (indexed);84,322.73;3.52%\n"
        "BTP Futura;20,588.89;0.86%\n"
        "BTP Valore;18,191.09;0.76%\n"
        "Atypical BTP;64.27;0.00%\n"
        "Foreign Debt Euro;45,998.00;1.92%\n"
        "of which  ISPA  Bonds;7,700.00;0.32%\n"
        "Foreign Debt Currencies (1);2,364.08;0.10%\n"
        "Total;2,392,963.95;100.00%\n"
        "Average Life (years);;\n"
        "6.96;;\n"
    )

    SPOSTATO = (
        ";;;;;;;;\n"
        ";Tipologia titolo;mln. Euro;%;\n"
        ";BTP;100,00;\n"
        ";Totale;100,00;\n"
    )

    def test_italiano(self):
        rec = mod.parse_file(self.ITALIANO, "2026-09-30")
        assert [r["tipologia"] for r in rec] == ["BTP", "BTP Green", "Totale"]
        assert rec[0]["valore_mln_eur"] == pytest.approx(1901406.45)
        assert rec[-1]["aggregato"] == "S"
        assert mod.quadra(rec) is False  # il totale sintetico non torna: righe finte

    def test_inglese(self):
        rec = mod.parse_file(self.INGLESE, "2023-06-30")
        per_tip = {r["tipologia"]: r for r in rec}
        assert per_tip["BTP"]["valore_mln_eur"] == pytest.approx(1724137.61)
        assert per_tip["BTP €i (rivalutato)"]["famiglia"] == "BTP€i"
        assert per_tip["Totale"]["aggregato"] == "S"
        assert per_tip["di cui Titoli Ispa"]["sottoinsieme"] == "S"
        assert mod.quadra(rec)

    def test_intestazione_spostata(self):
        rec = mod.parse_file(self.SPOSTATO, "2020-12-31")
        assert [r["tipologia"] for r in rec] == ["BTP", "Totale"]
        assert rec[0]["valore_mln_eur"] == pytest.approx(100.0)

    def test_file_senza_tabella(self):
        assert mod.parse_file(";;Totale 2.523.349 mln ;;\n", "2025-01-31") == []

    def test_quadratura_esclude_sottoinsiemi_e_aggregati(self):
        testo = (
            "Tipologia titolo;mln. Euro;\n"
            "BTP;100,00;\n"
            "Estero in euro;10,00;\n"
            "Estero;10,00;\n"
            "di cui Ispa;5,00;\n"
            "Totale;110,00;\n"
        )
        rec = mod.parse_file(testo, "2026-09-30")
        assert mod.quadra(rec)


@pytest.mark.contract
class TestMartComposizione:
    def _con(self):
        if not MART.exists():
            pytest.skip(f"mart non presente: {MART}")
        return duckdb.connect()

    def test_serie_pluriennale(self):
        con = self._con()
        n, d0, d1 = con.execute(
            f"SELECT count(DISTINCT data_ref), min(data_ref), max(data_ref) FROM read_parquet('{MART}')"
        ).fetchone()
        assert n >= 60, f"serie troppo corta: {n} mesi"
        assert d0.year <= 2021 and d1.year >= 2026

    def test_chiave_unica(self):
        con = self._con()
        dup = con.execute(
            f"SELECT count(*) FROM (SELECT data_ref, tipologia FROM read_parquet('{MART}') "
            "GROUP BY 1,2 HAVING count(*) > 1)"
        ).fetchone()[0]
        assert dup == 0, f"{dup} chiavi duplicate"

    def test_quadratura_ogni_mese(self):
        con = self._con()
        bad = con.execute(f"""
            SELECT data_ref,
                   round(sum(CASE WHEN NOT sottoinsieme AND NOT aggregato THEN valore_mln_eur ELSE 0 END)/1e3, 1) foglie,
                   round(max(CASE WHEN tipologia = 'Totale' THEN valore_mln_eur END)/1e3, 1) tot
            FROM read_parquet('{MART}')
            GROUP BY 1
            HAVING abs(foglie - tot) > 1
        """).fetchall()
        assert not bad, f"mesi che non quadrano: {bad[:5]}"

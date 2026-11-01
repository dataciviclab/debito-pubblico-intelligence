"""
Regressioni sul dataset `mef_riepilogo_emissioni_scadenze`.

Il 2026-11-01 il dataset mentiva su due cose:
- la colonna si chiamava `importo_mld` ma i valori erano in **milioni** (2020 BOT
  leggeva 181.815 "mld" invece di 181,8);
- il segno delle SCADENZE era positivo negli anni aggregati (2020-2024) e
  negativo dal 2025, quindi la somma delle sezioni non dava l'emissione netta.

Inoltre `n_isin` contava la riga `AGGREGATO` come se fosse un titolo.
"""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "out" / "data" / "mart" / "mef_riepilogo_emissioni_scadenze" / "2026"
PER_ANNO = BASE / "mart_per_anno_tipologia.parquet"
SCADENZE = BASE / "mart_scadenze_per_anno.parquet"


@pytest.mark.contract
class TestMartPerAnnoTipologia:
    def _con(self):
        if not PER_ANNO.exists():
            pytest.skip(f"mart non presente: {PER_ANNO}")
        return duckdb.connect()

    def test_colonne(self):
        con = self._con()
        cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{PER_ANNO}')").fetchall()}
        required = {"anno", "tipologia", "sezione", "grano", "n_isin",
                    "totale_mln_segnato", "totale_mln"}
        assert required.issubset(cols), f"colonne mancanti: {required - cols}"

    def test_scadenze_negative(self):
        con = self._con()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{PER_ANNO}') "
            "WHERE sezione = 'SCADENZE' AND totale_mln_segnato > 0"
        ).fetchone()[0]
        assert n == 0, f"{n} righe SCADENZE con segno positivo"

    def test_unita_milioni(self):
        """Nessuna singola riga annuale oltre 400 mld: se fosse in euro sarebbe 10^6."""
        con = self._con()
        massimo = con.execute(
            f"SELECT max(totale_mln) FROM read_parquet('{PER_ANNO}')"
        ).fetchone()[0]
        assert massimo < 400_000, f"valore fuori scala ({massimo}): unità sbagliata?"

    def test_grano_coerente(self):
        con = self._con()
        rows = con.execute(
            f"SELECT anno, min(grano), max(grano) FROM read_parquet('{PER_ANNO}') GROUP BY 1 ORDER BY 1"
        ).fetchall()
        for anno, g1, g2 in rows:
            atteso = "aggregato" if anno <= 2024 else "isin"
            assert g1 == g2 == atteso, f"{anno}: grano {g1}/{g2}, atteso {atteso}"

    def test_n_isin_non_conta_aggregato(self):
        con = self._con()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{PER_ANNO}') "
            "WHERE grano = 'aggregato' AND n_isin <> 0"
        ).fetchone()[0]
        assert n == 0, f"{n} righe aggregate con n_isin > 0"

    def test_emissione_netta_plausibile(self):
        con = self._con()
        rows = con.execute(
            f"SELECT anno, round(sum(totale_mln_segnato)/1000, 1) FROM read_parquet('{PER_ANNO}') "
            "GROUP BY 1 ORDER BY 1"
        ).fetchall()
        assert rows, "nessun anno"
        for anno, netto in rows:
            assert -200 <= netto <= 300, f"{anno}: emissione netta {netto} mld fuori scala"


@pytest.mark.contract
class TestMartScadenze:
    def test_solo_isin(self):
        if not SCADENZE.exists():
            pytest.skip(f"mart non presente: {SCADENZE}")
        con = duckdb.connect()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{SCADENZE}') WHERE isin = 'AGGREGATO'"
        ).fetchone()[0]
        assert n == 0, f"{n} righe aggregate nel dettaglio ISIN"

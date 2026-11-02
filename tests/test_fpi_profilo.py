"""
Contratto dei mart FPI del profilo del debito (vita residua, valuta, liquidità).

Il 2026-11-02 è emerso che il preprocess buttava via la **controparte** del
codice FPI (`parts[5]`): la stessa voce esisteva in più versioni (SBI3 = totale,
S13BI1 = detro le altre PA, ...) e finiva nello stesso codice, producendo righe
apparentemente duplicate con valori diversi. I test qui sotto tengono ferme le
due cose che contano: la controparte c'è, e le fasce di vita residua sommano al
debito AP.
"""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
MART = ROOT / "out" / "data" / "mart" / "fpi_debito_pa" / "2026"


def _con(table: str):
    path = MART / f"{table}.parquet"
    if not path.exists():
        pytest.skip(f"mart non presente: {path}")
    return duckdb.connect(), path


@pytest.mark.contract
class TestVitaResidua:
    def test_fasce_sommano_al_debito_ap(self):
        con, vita = _con("mart_vita_residua")
        con2, debito = _con("mart_debito_ap")
        data = con.execute(f"SELECT max(data) FROM read_parquet('{vita}')").fetchone()[0]
        fasce = con.execute(
            f"SELECT sum(valore) FROM read_parquet('{vita}') "
            "WHERE data = ? AND codice IN ('S13.MGD05','S13.MGD06','S13.MGD07')",
            [data],
        ).fetchone()[0]
        totale = con2.execute(
            f"SELECT valore_mln_eur FROM read_parquet('{debito}') "
            "WHERE data = ? AND tavola = 'TCCE0225' AND codice = 'S13.MGD'",
            [data],
        ).fetchone()[0]
        assert fasce == pytest.approx(totale, rel=0.001), f"{fasce} vs {totale}"

    def test_vita_media_in_anni(self):
        con, vita = _con("mart_vita_residua")
        unita = con.execute(
            f"SELECT unita FROM read_parquet('{vita}') WHERE codice = 'S13.MGD10' LIMIT 1"
        ).fetchone()[0]
        assert unita == "anni", f"MGD10 marcato come {unita}"

    def test_altre_fasce_in_euro(self):
        con, vita = _con("mart_vita_residua")
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{vita}') "
            "WHERE codice <> 'S13.MGD10' AND unita <> 'mln_eur'"
        ).fetchone()[0]
        assert n == 0, f"{n} righe in euro con unità sbagliata"


@pytest.mark.contract
class TestControparte:
    def test_controparte_presente(self):
        con, debito = _con("mart_debito_ap")
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{debito}') WHERE controparte IS NULL OR controparte = ''"
        ).fetchone()[0]
        assert n == 0, f"{n} righe senza controparte"

    def test_nessun_duplicato_dopo_controparte(self):
        """(tavola, codice, controparte, data) deve essere unico: se ricompaiono
        duplicati, il preprocess sta di nuovo perdendo una dimensione."""
        con, debito = _con("mart_debito_ap")
        dup = con.execute(f"""
            SELECT count(*) FROM (
                SELECT tavola, codice, controparte, data
                FROM read_parquet('{debito}') GROUP BY 1,2,3,4 HAVING count(*) > 1
            )
        """).fetchone()[0]
        assert dup == 0, f"{dup} chiavi duplicate"

    def test_sottosettori_distinguibili(self):
        """S1311.MGD esiste in tre versioni: totale, detro altre PA, ..."""
        con, debito = _con("mart_debito_ap")
        n = con.execute(
            f"SELECT count(DISTINCT controparte) FROM read_parquet('{debito}') "
            "WHERE tavola = 'TCCE0225' AND codice = 'S1311.MGD'"
        ).fetchone()[0]
        assert n >= 3, f"attese almeno 3 controparti per S1311.MGD, trovate {n}"


@pytest.mark.contract
class TestValuta:
    def test_euro_piu_estero_pari_al_totale(self):
        con, valuta = _con("mart_valuta")
        con2, debito = _con("mart_debito_ap")
        data = con.execute(f"SELECT max(data) FROM read_parquet('{valuta}')").fetchone()[0]
        euro, estero = con.execute(
            f"SELECT sum(CASE WHEN codice='S13.MGD11' THEN valore ELSE 0 END), "
            "sum(CASE WHEN codice='S13.MGD04' THEN valore ELSE 0 END) "
            f"FROM read_parquet('{valuta}') WHERE data = ?", [data]
        ).fetchone()
        totale = con2.execute(
            f"SELECT valore_mln_eur FROM read_parquet('{debito}') "
            "WHERE data = ? AND tavola = 'TCCE0225' AND codice = 'S13.MGD'", [data]
        ).fetchone()[0]
        assert euro + estero == pytest.approx(totale, rel=0.001)
        assert estero / totale < 0.01, "valuta estera oltre l'1%: controllo da rifare"


@pytest.mark.contract
class TestLiquidita:
    def test_natura_dichiarata(self):
        con, liq = _con("mart_liquidita")
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{liq}') WHERE natura NOT IN ('flusso','consistenza')"
        ).fetchone()[0]
        assert n == 0

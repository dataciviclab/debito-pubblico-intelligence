"""Contract OCPI — l'href della pagina va percent-encoded prima del download.

pure_unit: la pagina dell'Osservatorio CPI serve link con spazi letterali e
caratteri accentati (``... OCPI - Serie Storiche marzo 2026.xlsx``). Passare
l'href così com'è a ``urlopen`` fallisce con ``InvalidURL: URL can't contain
control characters``; il dataset va in errore e la pipeline mensile si ferma.
Il contratto è che ogni forma di href (relativa, assoluta, protocol-relative)
diventi un URL assoluto codificato e scaricabile.
"""
from __future__ import annotations

import importlib.util
import urllib.parse
from pathlib import Path

DATASET = (
    Path(__file__).resolve().parent.parent / "datasets" / "ocpi-serie-storiche"
)

HREF_CON_SPAZI = (
    "/content/dam/siti-web/ricerca/osservatorio_cpi/risorse/"
    "ocpi-OCPI - Serie Storiche marzo 2026.xlsx"
)


def _load_preprocess():
    spec = importlib.util.spec_from_file_location(
        "ocpi_preprocess", DATASET / "preprocess.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_href_con_spazi_diventa_scaricabile():
    url = _load_preprocess()._absolute_url(HREF_CON_SPAZI)

    assert " " not in url
    assert url.startswith("https://osservatoriocpi.unicatt.it/content/dam/")
    assert url.endswith("ocpi-OCPI%20-%20Serie%20Storiche%20marzo%202026.xlsx")


def test_url_prodotto_non_solleva_invalid_url():
    """``urlopen`` rifiuta i control characters: la richiesta deve costruirsi."""
    import urllib.request

    url = _load_preprocess()._absolute_url(HREF_CON_SPAZI)
    # Richiesta costruita ma non inviata: valida se urlopen non solleva.
    urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})


def test_forme_di_href_equivalenti():
    mod = _load_preprocess()

    atteso = (
        "https://osservatoriocpi.unicatt.it/content/dam/"
        "ocpi-OCPI%20-%20Serie%20Storiche%20marzo%202026.xlsx"
    )
    relativo = "/content/dam/ocpi-OCPI - Serie Storiche marzo 2026.xlsx"
    protocol_relative = "//osservatoriocpi.unicatt.it" + relativo
    assoluto = "https://osservatoriocpi.unicatt.it" + relativo

    assert mod._absolute_url(relativo) == atteso
    assert mod._absolute_url(protocol_relative) == atteso
    assert mod._absolute_url(assoluto) == atteso


def test_escape_gia_presenti_non_vengono_ricodificati():
    mod = _load_preprocess()

    url = mod._absolute_url("/content/dam/serie%20storiche.xlsx")

    assert url.endswith("/content/dam/serie%20storiche.xlsx")
    assert urllib.parse.unquote(url).endswith("/content/dam/serie storiche.xlsx")

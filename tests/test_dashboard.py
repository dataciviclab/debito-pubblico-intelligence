"""Smoke test — verifica che tutti i moduli della dashboard siano importabili."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke

DASHBOARD = Path(__file__).parent.parent / "dashboard"


def test_import_sources():
    sys.path.insert(0, str(DASHBOARD))
    import sources
    assert hasattr(sources, "query_ocpi")
    assert hasattr(sources, "query_fpi")
    assert hasattr(sources, "query_rendimento")


@pytest.mark.parametrize(
    "page",
    [
        "01_Panoramica",
        "02_Spread",
        "03_Composizione",
        "04_Scadenze",
        "05_Trend_Storico",
        "06_FPI",
        "07_SQL",
    ],
)
def test_page_importable(page: str) -> None:
    """Verifica che ogni pagina sia syntatticamente valida."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        page, DASHBOARD / "pages" / f"{page}.py"
    )
    assert spec is not None, f"{page}.py non trovato"
    # Non eseguiamo (servono env vars), solo verify syntax
    import ast

    source = (DASHBOARD / "pages" / f"{page}.py").read_text()
    ast.parse(source, filename=f"{page}.py")

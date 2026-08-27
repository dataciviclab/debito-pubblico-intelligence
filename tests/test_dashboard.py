"""Smoke test — verifica che tutti i moduli della dashboard siano validi."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke

DASHBOARD = Path(__file__).parent.parent / "dashboard"


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
def test_page_syntax(page: str) -> None:
    """Verifica che ogni pagina sia syntatticamente valida."""
    source = (DASHBOARD / "pages" / f"{page}.py").read_text()
    ast.parse(source, filename=f"{page}.py")

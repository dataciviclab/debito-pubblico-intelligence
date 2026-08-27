"""Query SQL — Interroga direttamente i dati del Debito Pubblico."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lab_connectors.registry import load_registry
from sql_page_flat import render_sql_query_flat

registry = load_registry(Path(__file__).parent.parent.parent / "registry" / "registry.json")

render_sql_query_flat(
    registry=registry,
    prefix="debito_pubblico_intelligence/",
    default_slug="ocpi_serie_storiche",
    title="🧪 Query SQL",
    description="Interroga direttamente i dati del Debito Pubblico. Scrivi SQL su ``clean_input``.",
)

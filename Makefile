# Debito Pubblico Intelligence — Makefile
# Pipeline toolkit (dataset.yml) + script analitici legacy.
# Convenzione Lab: toolkit gestisce fetch→clean→mart; gli script
# Python gestiscono reconcile, signals, scenarios, panorama.
TOOLKIT = toolkit

# --- Dataset del repo -------------------------------------------------------
DATASETS := $(shell find datasets -name dataset.yml 2>/dev/null | sort)

# --- Run toolkit ------------------------------------------------------------

.PHONY: run
run:
	$(TOOLKIT) run --batch batch.txt

.PHONY: run-all
run-all:
	@find datasets -name dataset.yml | sort > batch.txt; \
	$(TOOLKIT) run --batch batch.txt

# --- Validazione config ------------------------------------------------------

.PHONY: check
check:
	@for f in $(DATASETS); do \
		echo "→ $$f"; \
		$(TOOLKIT) run preflight --config "$$f" > /dev/null 2>&1 || exit 1; \
	done
	@echo "✅ All configs valid"

# --- Script analitici (legacy) -----------------------------------------------
# reconcile.py produce CSV + summary.json per la dashboard.
# bdap.py produce data/build/bdap_*.csv da GCS.

.PHONY: bdap reconcile
bdap:
	python3 scripts/bdap.py

reconcile: bdap
	python3 scripts/reconcile.py

# --- Pipeline completa: toolkit + analitici + test ----------------------------

.PHONY: all
all: run-all reconcile test

# --- Test --------------------------------------------------------------------

.PHONY: test
test:
	python3 -m pytest tests/ -v

# --- Registry ----------------------------------------------------------------

.PHONY: registry registry-write
registry:
	$(TOOLKIT) registry build --prefix debito_pubblico_intelligence --flat

registry-write:
	$(TOOLKIT) registry build --prefix debito_pubblico_intelligence --flat --write

# --- Pulizia -----------------------------------------------------------------

.PHONY: clean
clean:
	rm -rf out/data/_runs out/data/probe out/data/raw out/data/clean out/data/mart

.PHONY: clean-legacy
clean-legacy:
	rm -rf data/raw data/build data/mart data/reconcile data/signals data/reporting

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:' Makefile | sort

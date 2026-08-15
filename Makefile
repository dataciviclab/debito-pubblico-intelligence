# Debito Pubblico Intelligence — Makefile
.PHONY: all fetch fpi eurostat ocpi normalize mart reconcile signals clean test

# Pipeline completa: fonti -> normalize -> mart -> segnali
all: fetch normalize mart reconcile signals test

# Step 1: scarica le fonti ufficiali (Banca d'Italia FPI, Eurostat, OCPI)
fetch:
	python3 pipeline.py --step fetch

# Sotto-step singoli (utili durante bootstrap/debug)
fpi:
	python3 pipeline.py --step fetch --source fpi
eurostat:
	python3 pipeline.py --step fetch --source eurostat
ocpi:
	python3 pipeline.py --step fetch --source ocpi

# Step 2: normalizza source-level -> long/tidy
normalize:
	python3 pipeline.py --step normalize
# Step 3: mart queryabile (debito per sottosettore/strumento/detentore)
mart:
	python3 pipeline.py --step mart

# Step 4: fusion layer — riconciliazione cross-fonte
reconcile:
	python3 pipeline.py --step reconcile

# Step 5: segnali e alert con soglie
signals:
	python3 pipeline.py --step signals

# Test di integrità
test:
	python3 test_smoke.py

clean:
	rm -rf data/raw data/build data/mart data/reconcile data/signals

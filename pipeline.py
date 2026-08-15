#!/usr/bin/env python3
"""
Debito Pubblico Intelligence — entry point.

Pipeline in 5 step:
  fetch     -> scarica le fonti ufficiali (Banca d'Italia FPI, Eurostat, OCPI)
  normalize -> source-level -> long/tidy
  mart      -> dataset queryabile (debito per sottosettore/strumento/detentore)
  reconcile -> fusion layer: riconciliazione cross-fonte (il cuore dell'intelligence)
  signals   -> segnali con soglie calibrate sullo storico

Uso: python pipeline.py --step <step> [--source <fonte>]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", required=True,
                        choices=["fetch", "normalize", "mart", "reconcile", "signals", "scenario"])
    parser.add_argument("--source", default=None,
                        choices=["fpi", "eurostat", "ocpi"])
    args = parser.parse_args()

    if args.step == "fetch":
        from scripts import fetch
        fetch.run(args.source)
    elif args.step == "normalize":
        from scripts import normalize
        normalize.run()
        from scripts import normalize_mef
        normalize_mef.run()
    elif args.step == "mart":
        from scripts import mart
        mart.run()
    elif args.step == "reconcile":
        from scripts import bdap
        bdap.build_summary()
        bdap.build_consuntivo()
        from scripts import reconcile
        reconcile.run()
    elif args.step == "signals":
        from scripts import signals
        signals.run()
    elif args.step == "scenario":
        from scripts import scenarios
        scenarios.run()
    else:
        print(f"[ERRORE] step sconosciuto: {args.step}")
        sys.exit(1)


if __name__ == "__main__":
    main()

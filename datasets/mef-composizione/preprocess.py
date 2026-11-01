"""Preprocess MEF Composizione Titoli di Stato — serie mensile.

Il portale DT pubblica un CSV per mese (tabella `Tipologia titolo | mln. Euro | %`).
Qui si scarica l'archivio disponibile (default 2021..anno corrente) e si produce
una serie lunga con `data_ref`: lo snapshot di un solo mese non permette di
vedere come cambia la composizione.

Usage: python preprocess.py raw_input.csv [anno_min] [anno_max]

Output: data_ref, tipologia, famiglia, colonna, valore_mln_eur, sottoinsieme, aggregato

Note sul formato (tutte viste sui file veri):
- l'intestazione si individua cercando la cella con "mln": l'indice della colonna
  etichette e' quello precedente. Funziona per `Tipologia titolo;mln. Euro`,
  per `Bonds;Amount (mln. )` (file in inglese) e per le tabelle spostate;
- i file in inglese usano il separatore decimale anglosassone (120,559.11);
- la tabella finisce alla riga Totale: sotto ci sono sezioni diverse
  ("Vita Media del Debito") che non vanno lette come tipologie;
- le righe "di cui ..." sono SOTTOINSIEMI del totale;
- "Totale", "Estero" e "Altri programmi di emissione" sono AGGREGATI: contengono
  righe presenti anche separatamente, quindi non vanno mai sommati alle foglie;
- il simbolo € arriva come byte 0x80 (cp1252 letto come latin-1);
- alcuni mesi non hanno tabella (es. 31/01/2025: solo "Totale ... mln") oppure
  sono in inglese: si scartano con log, ma la quadratura viene comunque
  verificata e un mese che non quadra viene scartato.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

from mef_common import download_csv, file_date, mef_csv_links, parse_amount

PAGE = "composizione_titoli_stato"
ANNO_MIN_DEFAULT = 2021

# Etichette inglesi -> italiane (i CSV del 2023 sono pubblicati in inglese).
ETICHETTE_EN = {
    "total": "Totale",
    "atypical btp": "BTP atipici",
    "btpi (indexed)": "BTP €i (rivalutato)",
    "btp italia (indexed)": "BTP Italia (rivalutato)",
    "foreign debt euro": "Estero in Euro",
    "foreign debt currencies": "Estero in valuta",
    "of which ispa bonds": "di cui Titoli Ispa",
}

# Prefissi che identificano una famiglia stabile nel tempo.
FAMIGLIE = (
    ("BOT", "BOT"),
    ("CCTeu", "CCTeu"),
    ("CTZ", "CTZ"),
    ("BTP€i", "BTP€i"),
    ("BTP €i", "BTP€i"),
    ("BTP Italia", "BTP Italia"),
    ("BTP Green", "BTP Green"),
    ("BTP Valore", "BTP Valore"),
    ("BTP Futura", "BTP Futura"),
    ("BTP Più", "BTP Più"),
    ("BTP atipici", "BTP"),
    ("BTP", "BTP"),
    ("Estero in Euro", "Estero"),
    ("Emissioni in euro", "Estero"),
    ("Estero in valuta", "Estero"),
    ("Emissioni in valuta", "Estero"),
    ("Altri programmi di emissione", "Estero"),
    ("Titoli Ispa", "Ispa"),
)


def normalizza_tipologia(tip: str) -> str:
    """Ripara il simbolo € (0x80 da cp1252 o '?' nel 2021), gli spazi doppi e le etichette inglesi."""
    t = " ".join((tip or "").replace(chr(128), "€").split())
    t = re.sub(r"BTP\s*\?i", "BTP €i", t)
    basso = t.lower()
    for en, it in ETICHETTE_EN.items():
        if basso.startswith(en):
            return it
    return t


def famiglia(tip: str) -> str:
    """Famiglia stabile per aggregare la serie (le voci cambiano nome e maiuscole)."""
    t = normalizza_tipologia(tip)
    if t.lower().startswith("di cui"):
        return "sottoinsieme"
    basso = t.lower()
    for prefisso, fam in FAMIGLIE:
        if basso.startswith(prefisso.lower()):
            return fam
    return t


def is_aggregato(tip: str) -> bool:
    """Riga che contiene altre righe della stessa tabella (non sommabile alle foglie)."""
    t = normalizza_tipologia(tip)
    return t == "Estero" or t.startswith(("Totale", "Altri programmi"))


def _numero(cella: str, inglese: bool):
    if not inglese:
        return parse_amount(cella)
    cella = (cella or "").strip().replace(",", "")
    try:
        return float(cella)
    except ValueError:
        return None


def parse_file(text: str, data_ref: str) -> list[dict]:
    """Righe lunghe di un singolo CSV: una riga per tipologia (colonna in mln di euro)."""
    rows = list(csv.reader(text.splitlines(), delimiter=";"))

    header_idx = None
    offset = 0
    col_idx = 0
    inglese = False
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            if "mln" in (c or "").lower():
                header_idx, offset, col_idx = i, max(j - 1, 0), j
                inglese = "amount" in (c or "").lower()
                break
        if header_idx is not None:
            break
    if header_idx is None:
        return []

    records: list[dict] = []
    for r in rows[header_idx + 1:]:
        if len(r) <= offset:
            continue
        tipologia = normalizza_tipologia(r[offset])
        if not tipologia:
            continue
        valore = _numero(r[col_idx], inglese) if col_idx < len(r) else None
        if valore is None:  # celle in % o vuote
            continue
        records.append({
            "data_ref": data_ref,
            "tipologia": tipologia,
            "famiglia": famiglia(tipologia),
            "colonna": "mln. Euro",
            "valore_mln_eur": valore,
            "sottoinsieme": "S" if tipologia.lower().startswith("di cui") else "N",
            "aggregato": "S" if is_aggregato(tipologia) else "N",
        })
        if tipologia == "Totale":
            break  # sotto iniziano altre sezioni (es. "Vita Media del Debito")
    return records


def quadra(records: list[dict], tolleranza: float = 0.005) -> bool:
    """Le foglie devono sommare al Totale dichiarato (tolleranza relativa)."""
    foglie = sum(
        r["valore_mln_eur"] for r in records
        if r["sottoinsieme"] == "N" and r["aggregato"] == "N"
    )
    totale = next(
        (r["valore_mln_eur"] for r in records if r["tipologia"] == "Totale" and r["aggregato"] == "S"),
        None,
    )
    if totale is None or totale <= 0:
        return False
    return abs(foglie - totale) <= tolleranza * totale


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"
    anno_min = int(sys.argv[2]) if len(sys.argv) > 2 else ANNO_MIN_DEFAULT
    anno_max = int(sys.argv[3]) if len(sys.argv) > 3 else 2026

    records: list[dict] = []
    mesi: list[str] = []
    scartati: list[str] = []
    for anno in range(anno_min, anno_max + 1):
        links = mef_csv_links(PAGE, year=anno)
        if not links:
            print(f"[composizione] {anno}: nessun CSV pubblicato")
            continue
        ok = 0
        for link in links:
            data = file_date(Path(link).name)
            if data is None:
                scartati.append(f"{Path(link).name} (data non riconosciuta)")
                continue
            data_ref = f"{data[0]}-{data[1]:02d}-{data[2]:02d}"
            try:
                raw = download_csv(link)
            except Exception as exc:  # singolo file KO non ferma la serie
                scartati.append(f"{Path(link).name} (download: {exc})")
                continue
            testo = raw.decode("utf-8", "ignore") if _is_utf8(raw) else raw.decode("latin-1")
            righe = parse_file(testo, data_ref)
            if not righe:
                scartati.append(f"{data_ref} (nessuna tabella nel file)")
                continue
            if not quadra(righe):
                scartati.append(f"{data_ref} (foglie != totale)")
                continue
            records.extend(righe)
            mesi.append(data_ref)
            ok += 1
        print(f"[composizione] {anno}: {ok}/{len(links)} file")

    if not records:
        print("[ERRORE] nessun dato raccolto")
        sys.exit(1)

    fieldnames = [
        "data_ref", "tipologia", "famiglia", "colonna",
        "valore_mln_eur", "sottoinsieme", "aggregato",
    ]
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)

    mesi.sort()
    print(f"[composizione] OK {output}: {len(records)} righe, {len(mesi)} mesi ({mesi[0]} → {mesi[-1]})")
    if scartati:
        print(f"[composizione] scartati {len(scartati)}: {', '.join(scartati)}")


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


if __name__ == "__main__":
    main()

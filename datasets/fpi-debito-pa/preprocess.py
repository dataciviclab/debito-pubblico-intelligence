"""
Preprocess FPI - Banca d'Italia BDS Finanza Pubblica.

Scarica il ZIP della pubblicazione FPI, estrae le 9 tavole (TCCE*),
converte da wide a long e produce raw_input.csv per il toolkit.

Usage: python preprocess.py raw_input.csv

Output: CSV con colonne:
    data, tavola, tavola_nome, codice, descrizione, valore_mln_eur, fonte

Fonte: https://www.bancaditalia.it/statistiche/tematiche/conti-pubblici/dp-pa/
"""

import csv
import io
import sys
import urllib.request
import zipfile

USER_AGENT = "DataCivicLab pipeline/1.0"

FPI_URL = (
    "https://a2a.bancaditalia.it/infostat/dataservices/export/IT/CSV/ALL/"
    "PUBLICATION/BANKITALIA/DIFF/FPI"
)

ALL_TABLES = {
    "TCCE0125": "Fabbisogno AP per strumenti",
    "TCCE0175": "Debito AP per strumenti",
    "TCCE0200": "Debito AP per detentori",
    "TCCE0225": "Debito AP per sottosettori",
    "TCCE0250": "Debito Amm.locali per comparti",
    "TCCE0275": "Debito Amm.locali per aree",
    "TCCE0300": "Depositi e liquidita AP",
    "TCCE0325": "Debito AP per vita residua",
    "TCCE0350": "Debito AP per scadenza/valuta",
}

FPI_TABLE_NAMES = {
    "TCCE0125": "fabbisogno_ap_strumenti",
    "TCCE0175": "debito_ap_strumenti",
    "TCCE0200": "debito_ap_detentori",
    "TCCE0225": "debito_ap_sottosettori",
    "TCCE0250": "debito_amm_locali_comparti",
    "TCCE0275": "debito_amm_locali_aree",
    "TCCE0300": "depositi_liquidita_ap",
    "TCCE0325": "debito_ap_vita_residua",
    "TCCE0350": "debito_ap_scadenza_valuta",
}

GEO_LABELS = {
    "ITC": "Nord-ovest",
    "ITH": "Nord-est",
    "ITI": "Centro",
    "ITF": "Sud",
    "ITG": "Isole",
}


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _read_legend(zip_bytes: bytes) -> dict:
    legend = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if "LEGEND" in name.upper():
                text = zf.read(name).decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(text), delimiter=";")
                for row in reader:
                    codice = str(row.get("Codice") or "").strip()
                    desc = str(row.get("Descrizione") or "").strip()
                    if codice and desc:
                        parts = codice.split(".")
                        if len(parts) >= 8:
                            legend[f"{parts[3]}.{parts[4]}"] = desc
                        if len(parts) >= 6:
                            legend[f"{parts[3]}.{parts[4]}.{parts[5]}"] = desc
                        legend[codice] = desc
    return legend


def _decode_code(column: str, table_code: str | None = None) -> tuple[str, str]:
    """Ritorna (codice, controparte).

    Il nome colonna FPI e' `FPI_FP.{freq}.{geo}.{settore}.{voce}.{controparte}....`
    La controparte (parts[5]) NON va buttata: per i sotto-settori la stessa voce
    esiste in piu' versioni (SBI3 = totale, S13BI1 = detro le altre PA, ...) e
    scartarla produce righe apparentemente duplicate con valori diversi.
    Per il totale S13 c'e' una sola colonna (SBI3), quindi i numeri aggregati
    non cambiano.
    """
    if not column.startswith("FPI_FP."):
        return "", ""
    parts = column.split(".")
    if len(parts) < 8:
        return "", ""
    controparte = parts[5] if len(parts) > 5 else ""
    geo = parts[2]
    if geo != "IT":
        return f"{geo}.{parts[4]}", controparte
    if table_code == "TCCE0200" and controparte:
        # detentori: la controparte e' gia' parte del codice (S13.F3.S121)
        return f"{parts[3]}.{parts[4]}.{controparte}", controparte
    return f"{parts[3]}.{parts[4]}", controparte


def _wide_to_long(csv_bytes: bytes, table_code: str, legend: dict) -> list[dict]:
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = []
    for row in reader:
        data_oss = (row.get("DATA_OSS") or "").strip()
        if not data_oss:
            continue
        for colname, value in row.items():
            if colname == "DATA_OSS" or not value:
                continue
            if table_code == "TCCE0200" and ".FAV.EUR." not in colname:
                continue
            try:
                valore = float(value.replace(",", "."))
            except (ValueError, AttributeError):
                continue
            codice, controparte = _decode_code(colname, table_code)
            if not codice:
                continue
            rows.append({
                "data": data_oss,
                "tavola": table_code,
                "codice": codice,
                "controparte": controparte,
                "descrizione": legend.get(codice, ""),
                "valore_mln_eur": valore,
            })
    return rows


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "raw_input.csv"

    print("[fpi] download ZIP ...")
    zip_bytes = _download(FPI_URL)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        data_zip = zipfile.ZipFile(io.BytesIO(zf.read("FPI_DATA.zip")))
        legend = _read_legend(zf.read("FPI_LEGEND.zip"))
        for geo, label in GEO_LABELS.items():
            for strumento in ["MGD", "F3", "F4"]:
                legend[f"{geo}.{strumento}"] = f"Amm. locali ({label}): debito lordo"

    all_rows = []
    for code, table_name in ALL_TABLES.items():
        member = f"{code}_IT.zip"
        if member not in data_zip.namelist():
            print(f"[fpi] skip {code}: non presente nel ZIP")
            continue
        with zipfile.ZipFile(io.BytesIO(data_zip.read(member))) as tz:
            csvs = [n for n in tz.namelist() if n.endswith(".csv")]
            if not csvs:
                continue
            rows = _wide_to_long(tz.read(csvs[0]), code, legend)
            all_rows.extend(rows)
            print(f"[fpi] {code} ({table_name}): {len(rows)} righe")

    if not all_rows:
        print("[ERRORE] fpi: nessuna riga prodotta")
        sys.exit(1)

    for row in all_rows:
        row["tavola_nome"] = FPI_TABLE_NAMES.get(row["tavola"], row["tavola"])
        row["fonte"] = "banca_ditalia_fpi"

    fieldnames = [
        "data", "tavola", "tavola_nome", "codice", "controparte",
        "descrizione", "valore_mln_eur", "fonte",
    ]
    with open(output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        w.writeheader()
        w.writerows(all_rows)

    print(f"[fpi] OK {output}: {len(all_rows)} righe totali")


if __name__ == "__main__":
    main()

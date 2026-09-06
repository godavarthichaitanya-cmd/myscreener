"""
storage/manual_data.py — persistence for the two fields that can't be
pulled from yfinance and have to be manually copied over from Screener.in:
promoter pledge % and 5-year EPS CAGR %. Stored as a simple CSV, one row
per symbol, so they survive both a page refresh and a full app restart —
unlike the current session-only number_input fields in ui/single_stock.py.

File format (manual_data.csv), created automatically on first save:
    symbol,pledge,eps_cagr_5yr
    TCS,0.0,11.2
    RELIANCE,0.0,9.8
"""

import csv
import os

MANUAL_DATA_PATH = "manual_data.csv"


def load_manual_data() -> dict:
    """
    Reads the whole CSV into a dict keyed by uppercase symbol:
        {"TCS": {"pledge": 0.0, "eps_cagr_5yr": 11.2}, ...}
    Returns an empty dict if the file doesn't exist yet (first run, before
    anything's been saved) — callers should treat a missing symbol the
    same way as a missing file: just no manual data entered yet.
    """
    if not os.path.exists(MANUAL_DATA_PATH):
        return {}

    data = {}
    with open(MANUAL_DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row["symbol"].strip().upper()
            data[symbol] = {
                "pledge": float(row["pledge"]) if row["pledge"] else 0.0,
                "eps_cagr_5yr": float(row["eps_cagr_5yr"]) if row["eps_cagr_5yr"] else 0.0,
            }
    return data


def save_manual_entry(symbol: str, pledge: float, eps_cagr_5yr: float) -> None:
    """
    Updates (or creates) the manual entry for one symbol and rewrites the
    whole CSV. Rewriting the entire file on every save is simple and fine
    at this scale (a few hundred symbols at most) — no need for a real
    database for a personal tool with this data volume.
    """
    data = load_manual_data()
    data[symbol.upper()] = {"pledge": pledge, "eps_cagr_5yr": eps_cagr_5yr}

    with open(MANUAL_DATA_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "pledge", "eps_cagr_5yr"])
        for sym, values in sorted(data.items()):
            writer.writerow([sym, values["pledge"], values["eps_cagr_5yr"]])
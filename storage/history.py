"""
storage/history.py — persists every stock evaluation (score, verdict, price,
timestamp) to a CSV log, so a stock's PP score can be tracked over repeated
evaluations rather than only ever seeing a single snapshot. Returns a
pandas DataFrame from load_history() (not a plain list) since this data is
naturally suited to a trend chart later (Plotly, same as the old app) and
to sorting/filtering in Batch mode.

File format (score_history.csv), created automatically on first log:
    date,symbol,score_pct,cmp,verdict
    2026-08-24 15:55,TCS,50,2303.0,Fundamentally sound, wait for entry
"""

import csv
import os
from datetime import datetime

import pandas as pd

HISTORY_PATH = "score_history.csv"
_FIELDNAMES = ["date", "symbol", "score_pct", "cmp", "verdict"]


def log_evaluation(symbol: str, passed: int, total: int, cmp: float, verdict_text: str) -> None:
    """
    Appends one row to the history log — called every time a stock is
    fetched and evaluated (Single Stock and, later, Batch mode). Appending
    a single row is cheap even as the file grows, unlike manual_data.py's
    full-file rewrite (which only ever holds one row per symbol, so it
    doesn't need this distinction).
    """
    score_pct = round((passed / total) * 100) if total else 0
    file_exists = os.path.exists(HISTORY_PATH)

    with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol.upper(),
            "score_pct": score_pct,
            "cmp": cmp,
            "verdict": verdict_text,
        })


def load_history(symbol: str) -> pd.DataFrame:
    """
    Returns every logged evaluation for one symbol, oldest first, as a
    DataFrame with columns [date, symbol, score_pct, cmp, verdict]. Returns
    an empty DataFrame (same columns, zero rows) if the log file doesn't
    exist yet or the symbol has no entries — callers should check
    `.empty` rather than expecting None.
    """
    if not os.path.exists(HISTORY_PATH):
        return pd.DataFrame(columns=_FIELDNAMES)

    df = pd.read_csv(HISTORY_PATH)
    df = df[df["symbol"] == symbol.upper()].reset_index(drop=True)
    return df


def days_since_last_check(symbol: str):
    """
    Returns how many whole days ago a symbol was last evaluated, or None
    if it's never been evaluated. Used by Batch mode to flag stale entries
    (e.g. "⚠️ 14d ago") without needing a full history chart just to answer
    "when did I last look at this?"
    """
    hist = load_history(symbol)
    if hist.empty:
        return None
    last_date_str = hist["date"].iloc[-1]
    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M")
        return (datetime.now() - last_date).days
    except Exception:
        return None
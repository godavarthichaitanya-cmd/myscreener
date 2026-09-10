"""
storage/history.py — logs every Evaluate click to score_history.csv and
loads it back.

SCHEMA (positional, no header row):
  timestamp, symbol, score_pct, price, verdict_text, checks_json

checks_json is new — a JSON-serialized list of (label, True/False/None)
tuples for that evaluation, letting later sessions diff two evaluations
check-by-check instead of only comparing the rolled-up score_pct. Older
rows written before this column existed simply won't have a 6th field;
load_history() handles that by returning checks=None for those rows.
"""

import csv
import json
import os
from datetime import datetime

import pandas as pd

HISTORY_CSV = "score_history.csv"
COLUMNS = ["timestamp", "symbol", "score_pct", "price", "verdict_text", "checks_json"]


def _normalize_checks(checks):
    """
    Converts any numpy.bool_ (or other numpy scalar) statuses to plain
    Python True/False/None before JSON serialization. json.dumps() can't
    serialize numpy.bool_ even though it behaves like a normal bool
    everywhere else — same underlying quirk as the identity-check bug
    documented in core/checks.py, just hitting serialization instead of
    an `is True`/`is False` comparison this time.
    """
    normalized = []
    for label, status in checks:
        if status is None:
            normalized.append((label, None))
        else:
            normalized.append((label, bool(status)))
    return normalized


def log_evaluation(symbol, passed, total, price, verdict_text, checks=None):
    score_pct = round((passed / total) * 100) if total else 0
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    checks_json = json.dumps(_normalize_checks(checks)) if checks else ""

    file_exists = os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, symbol, score_pct, price, verdict_text, checks_json])


def load_history(symbol):
    """
    Returns a DataFrame of this symbol's history, oldest first, with
    columns: timestamp, symbol, score_pct, price, verdict_text, checks
    (checks is the parsed Python list, or None if that row predates this
    column or failed to parse). Returns an empty DataFrame if the file
    doesn't exist or has no rows for this symbol.
    """
    if not os.path.exists(HISTORY_CSV):
        return pd.DataFrame(columns=["timestamp", "symbol", "score_pct", "price", "verdict_text", "checks"])

    rows = []
    with open(HISTORY_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 5:
                continue  # malformed row, skip
            if row[1] != symbol:
                continue

            checks_json = row[5] if len(row) >= 6 else ""
            try:
                checks = json.loads(checks_json) if checks_json else None
            except (json.JSONDecodeError, TypeError):
                checks = None

            rows.append({
                "timestamp": row[0],
                "symbol": row[1],
                "score_pct": int(row[2]),
                "price": float(row[3]),
                "verdict_text": row[4],
                "checks": checks,
            })

    return pd.DataFrame(rows)


def days_since_last_check(symbol):
    """Used by Batch mode. Unchanged behavior — kept here for compatibility."""
    hist = load_history(symbol)
    if hist.empty:
        return None
    last_ts = datetime.strptime(hist.iloc[-1]["timestamp"], "%Y-%m-%d %H:%M")
    return (datetime.now() - last_ts).days
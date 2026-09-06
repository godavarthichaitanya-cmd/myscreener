"""
storage/reject_log.py — lets you explicitly mark a stock as "rejected"
after an Avoid verdict, and later surfaces whether its score has improved
enough to be worth a second look. One row per symbol (most recent
rejection only) — re-rejecting a symbol overwrites its previous entry,
same rationale as storage/manual_data.py: there's no need for a full
history of every rejection, just the most recent one to compare against.
"""

import csv
import os
from datetime import datetime

REJECT_LOG_PATH = "reject_log.csv"
_FIELDNAMES = ["symbol", "date", "score_pct", "verdict_text"]

# How many percentage points a re-evaluation's score needs to improve by
# (over the score at rejection time) to be flagged "worth a second look."
IMPROVEMENT_THRESHOLD_PTS = 15


def log_rejection(symbol: str, score_pct: int, verdict_text: str) -> None:
    rows = _load_all()
    rows[symbol.upper()] = {
        "symbol": symbol.upper(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score_pct": score_pct,
        "verdict_text": verdict_text,
    }
    with open(REJECT_LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows.values())


def _load_all() -> dict:
    if not os.path.exists(REJECT_LOG_PATH):
        return {}
    with open(REJECT_LOG_PATH, newline="", encoding="utf-8") as f:
        return {row["symbol"]: row for row in csv.DictReader(f)}


def get_last_rejection(symbol: str):
    """Returns {"date", "score_pct", "verdict_text"} for a symbol's most
    recent rejection, or None if it's never been rejected."""
    row = _load_all().get(symbol.upper())
    if row is None:
        return None
    return {"date": row["date"], "score_pct": int(row["score_pct"]), "verdict_text": row["verdict_text"]}


def days_since_rejection(symbol: str):
    """Returns whole days since the last rejection, or None if never rejected."""
    row = get_last_rejection(symbol)
    if row is None:
        return None
    try:
        last_date = datetime.strptime(row["date"], "%Y-%m-%d %H:%M")
        return (datetime.now() - last_date).days
    except Exception:
        return None


def has_improved(symbol: str, current_score_pct: int, current_verdict_text: str) -> bool:
    """
    True if a re-evaluation is worth flagging as improved — either the
    verdict is no longer "Avoid" at all, or the score has climbed by at
    least IMPROVEMENT_THRESHOLD_PTS points since the logged rejection.
    Returns False if the symbol was never rejected (nothing to compare
    against).
    """
    past = get_last_rejection(symbol)
    if past is None:
        return False
    no_longer_avoid = not current_verdict_text.startswith("Avoid")
    improved_score = (current_score_pct - past["score_pct"]) >= IMPROVEMENT_THRESHOLD_PTS
    return no_longer_avoid or improved_score
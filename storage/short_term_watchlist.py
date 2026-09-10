"""
storage/short_term_watchlist.py — a symbol list for short-term/swing
candidates, kept separate from config/queue.py's CORE_V13_QUEUE.

V13's queue is long-term deploy-ready names. This watchlist is whatever
you're tracking for a swing setup this week/month — likely a different,
faster-changing set of symbols. CSV-backed (short_term_watchlist.csv),
same simple add/remove pattern as storage/watchlist.py's star toggle.
"""

import os
import csv

WATCHLIST_CSV = "short_term_watchlist.csv"


def get_watchlist():
    if not os.path.exists(WATCHLIST_CSV):
        return []
    with open(WATCHLIST_CSV, newline="") as f:
        reader = csv.reader(f)
        return [row[0].strip().upper() for row in reader if row and row[0].strip()]


def add_symbol(symbol):
    symbol = symbol.strip().upper()
    current = get_watchlist()
    if symbol and symbol not in current:
        current.append(symbol)
        _save(current)


def remove_symbol(symbol):
    symbol = symbol.strip().upper()
    current = [s for s in get_watchlist() if s != symbol]
    _save(current)


def _save(symbols):
    with open(WATCHLIST_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        for s in symbols:
            writer.writerow([s])
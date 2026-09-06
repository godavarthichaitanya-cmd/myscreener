"""
storage/watchlist.py — a lightweight "revisit later" flag, deliberately
separate from storage/manual_data.py. Manual data means you've actually
gone and pulled promoter pledge/EPS CAGR from Screener.in — a real
research commitment. The watchlist is just a star: "this looked
interesting, come back to it," with zero data entry required.
"""

import csv
import os

WATCHLIST_PATH = "watchlist.csv"


def _load_symbols() -> set:
    if not os.path.exists(WATCHLIST_PATH):
        return set()
    with open(WATCHLIST_PATH, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        return {row[0] for row in reader if row}


def _save_symbols(symbols: set) -> None:
    with open(WATCHLIST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol"])
        for sym in sorted(symbols):
            writer.writerow([sym])


def is_watchlisted(symbol: str) -> bool:
    return symbol.upper() in _load_symbols()


def toggle_watchlist(symbol: str) -> bool:
    """Adds the symbol if it's not on the list, removes it if it is.
    Returns the new state (True = now watchlisted, False = now removed)."""
    symbols = _load_symbols()
    symbol = symbol.upper()
    if symbol in symbols:
        symbols.remove(symbol)
        now_watchlisted = False
    else:
        symbols.add(symbol)
        now_watchlisted = True
    _save_symbols(symbols)
    return now_watchlisted


def get_watchlist() -> list:
    """Returns all watchlisted symbols, sorted — useful later for a
    dedicated Watchlist tab or as a Batch-mode preset."""
    return sorted(_load_symbols())
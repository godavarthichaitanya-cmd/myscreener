"""
storage/notes.py — a free-text note per stock ("why I like this," "watch
for Q3 results," etc.) — distinct from storage/watchlist.py (which is
just a yes/no flag) and storage/manual_data.py (which is specific
Screener.in-sourced numbers). One row per symbol, most recent note only —
this is a running note you overwrite as your thinking evolves, not a
dated journal.
"""

import csv
import os

NOTES_PATH = "notes.csv"


def _load_all() -> dict:
    if not os.path.exists(NOTES_PATH):
        return {}
    with open(NOTES_PATH, newline="", encoding="utf-8") as f:
        return {row["symbol"]: row["note"] for row in csv.DictReader(f)}


def load_note(symbol: str) -> str:
    return _load_all().get(symbol.upper(), "")


def save_note(symbol: str, note: str) -> None:
    notes = _load_all()
    symbol = symbol.upper()
    if note.strip():
        notes[symbol] = note
    else:
        notes.pop(symbol, None)  # an emptied note is removed, not stored as a blank row

    with open(NOTES_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "note"])
        for sym, text in sorted(notes.items()):
            writer.writerow([sym, text])
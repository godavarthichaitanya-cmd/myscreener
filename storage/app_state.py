"""
storage/app_state.py — tiny persistence for tool-level state that isn't
"data about a stock" (that's storage/manual_data.py) or "a logged
evaluation" (storage/history.py) — just tool state like "what symbol was
I last looking at." Deliberately a single small JSON file rather than a
CSV, since this holds a handful of scalar settings, not repeated rows.
"""

import json
import os

STATE_PATH = "app_state.json"


def _load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}  # a corrupted/unreadable state file shouldn't crash the app


def _save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def load_last_symbol():
    """Returns the last successfully fetched symbol, or None if there
    isn't one yet (first run, or the file doesn't exist)."""
    return _load_state().get("last_symbol")


def save_last_symbol(symbol: str) -> None:
    state = _load_state()
    state["last_symbol"] = symbol.upper()
    _save_state(state)
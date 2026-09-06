"""
storage/gtt_levels.py — user-editable GTT levels, added/edited/removed from
the UI. Persisted separately from config/gtt_levels.py, which stays a
hand-maintained code file for whatever you've already set up there (TCS,
BLS, etc). core/gtt.py merges both sources when resolving a symbol's
levels, so nothing already in config/gtt_levels.py is lost or shadowed —
UI-added levels just add to the ladder.
"""

import pandas as pd
import os

GTT_LEVELS_CSV = "gtt_levels.csv"
_COLUMNS = ["symbol", "level"]


def _load_df():
    if not os.path.isfile(GTT_LEVELS_CSV):
        return pd.DataFrame(columns=_COLUMNS)
    return pd.read_csv(GTT_LEVELS_CSV)


def get_levels(symbol: str):
    """UI-added levels only for this symbol (config/gtt_levels.py levels
    are not stored here — see core/gtt.py for the merged view)."""
    df = _load_df()
    rows = df[df["symbol"] == symbol.upper()]
    return sorted(rows["level"].tolist())


def add_level(symbol: str, level: float):
    symbol = symbol.upper()
    df = _load_df()
    already_there = ((df["symbol"] == symbol) & (df["level"] == level)).any()
    if not already_there:
        df = pd.concat([df, pd.DataFrame([{"symbol": symbol, "level": level}])], ignore_index=True)
        df.to_csv(GTT_LEVELS_CSV, index=False)


def remove_level(symbol: str, level: float):
    symbol = symbol.upper()
    df = _load_df()
    df = df[~((df["symbol"] == symbol) & (df["level"] == level))]
    df.to_csv(GTT_LEVELS_CSV, index=False)
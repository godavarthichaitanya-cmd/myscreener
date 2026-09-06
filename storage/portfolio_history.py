"""
storage/portfolio_history.py — append-only log of portfolio-level
snapshots (total invested, total current value, P&L, holding count)
taken each time the Portfolio tab is refreshed. Same CSV-backed
pattern as storage/history.py, but at the whole-portfolio level
instead of per-stock, so the new Value Trend chart on the Portfolio
tab has something to plot over time.

Drop this file into storage/ alongside history.py / portfolio.py.
"""

import os
import pandas as pd
from datetime import datetime

_HISTORY_CSV = "portfolio_history.csv"
_COLUMNS = [
    "timestamp", "total_invested", "total_current",
    "total_pnl", "total_pnl_pct", "num_holdings",
]


def log_portfolio_snapshot(total_invested, total_current, total_pnl, total_pnl_pct, num_holdings):
    """Append one snapshot row. Called once per Refresh click from the
    Portfolio tab — not on every rerun — so the trend reflects actual
    refresh events rather than every Streamlit re-render."""
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "total_invested": round(total_invested, 2),
        "total_current": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "num_holdings": num_holdings,
    }
    if os.path.exists(_HISTORY_CSV):
        df = pd.read_csv(_HISTORY_CSV)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row], columns=_COLUMNS)
    df.to_csv(_HISTORY_CSV, index=False)


def load_portfolio_history():
    """Returns the full snapshot history as a DataFrame with a proper
    datetime timestamp column. Empty (but correctly columned) DataFrame
    if nothing has been logged yet."""
    if not os.path.exists(_HISTORY_CSV):
        return pd.DataFrame(columns=_COLUMNS)
    df = pd.read_csv(_HISTORY_CSV)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df
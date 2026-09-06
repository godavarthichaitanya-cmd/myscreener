"""
storage/alerts_history.py — a log of every Alerts scan result, so
recurring vs. one-off signals are distinguishable. Alerts itself stays
snapshot-only (not live monitoring) per its original design — this just
remembers past snapshots so ui/alerts.py can show "this has fired in N
scans" next to a card instead of every alert looking equally fresh.

CSV columns: timestamp, symbol, alert_label, tone
One row per (scan, symbol, alert) — a scan that fires 2 alerts for one
symbol writes 2 rows sharing the same timestamp. Quiet symbols (no
alerts that scan) write nothing, same as the main Alerts view already
only showing symbols with something to say.
"""

import os
import pandas as pd
from datetime import datetime

ALERTS_HISTORY_CSV = "alerts_history.csv"
_COLUMNS = ["timestamp", "symbol", "alert_label", "tone"]


def log_alerts(symbol, alerts):
    """alerts: list of {"label": ..., "tone": ...} dicts, the same shape
    ui/alerts.py's _scan_alerts() builds per symbol. No-op if empty."""
    if not alerts:
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    rows = [
        {"timestamp": timestamp, "symbol": symbol, "alert_label": a["label"], "tone": a["tone"]}
        for a in alerts
    ]
    new_df = pd.DataFrame(rows, columns=_COLUMNS)
    if os.path.exists(ALERTS_HISTORY_CSV):
        new_df.to_csv(ALERTS_HISTORY_CSV, mode="a", header=False, index=False)
    else:
        new_df.to_csv(ALERTS_HISTORY_CSV, index=False)


def load_alerts_history(symbol=None):
    if not os.path.exists(ALERTS_HISTORY_CSV):
        return pd.DataFrame(columns=_COLUMNS)
    df = pd.read_csv(ALERTS_HISTORY_CSV)
    if symbol:
        df = df[df["symbol"] == symbol]
    return df


def alert_scan_count(symbol):
    """How many distinct past scans logged at least one alert for this
    symbol — a rough 'is this recurring or a one-off' signal. Deliberately
    not framed as 'N of last M scans' (that would imply comparing against
    total scans run, which this doesn't track) — just a plain count of
    times it's shown up with something to say."""
    df = load_alerts_history(symbol)
    if df.empty:
        return 0
    return df["timestamp"].nunique()
"""
storage/short_term_capital.py — persists the short-term trading capital
pool and risk settings, separate from V13's long-term capital.

Three numbers, one CSV row (short_term_capital.csv):
  - capital: total ₹ pool set aside for short-term/swing trades
  - risk_pct: % of that pool you're willing to risk on a single trade
  - atr_multiplier: how many ATRs below entry the stop-loss sits

Defaults match what was agreed: ₹10,000 capital, 2% risk/trade, 1.5x ATR
stop. Change via save_settings() (e.g. a small settings expander in the
Short Term View tab) rather than editing the CSV by hand.
"""

import os
import csv

CAPITAL_CSV = "short_term_capital.csv"
_FIELDS = ["capital", "risk_pct", "atr_multiplier"]

_DEFAULTS = {
    "capital": 10000.0,
    "risk_pct": 2.0,
    "atr_multiplier": 1.5,
}


def get_settings():
    """Returns a dict with capital, risk_pct, atr_multiplier. Falls back
    to defaults if the file doesn't exist yet or a row is missing."""
    if not os.path.exists(CAPITAL_CSV):
        return dict(_DEFAULTS)
    with open(CAPITAL_CSV, newline="") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
    if not row:
        return dict(_DEFAULTS)
    try:
        return {
            "capital": float(row["capital"]),
            "risk_pct": float(row["risk_pct"]),
            "atr_multiplier": float(row["atr_multiplier"]),
        }
    except (KeyError, ValueError):
        return dict(_DEFAULTS)


def save_settings(capital, risk_pct, atr_multiplier):
    """Overwrites the single settings row. Called from a Save button in
    the Short Term View settings expander."""
    with open(CAPITAL_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerow({
            "capital": capital,
            "risk_pct": risk_pct,
            "atr_multiplier": atr_multiplier,
        })


def risk_amount(settings=None):
    """Convenience: ₹ amount at risk per trade given current settings."""
    s = settings or get_settings()
    return round(s["capital"] * s["risk_pct"] / 100.0, 2)
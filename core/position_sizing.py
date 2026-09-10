"""
core/position_sizing.py — ATR-based stop-loss and position-size
suggestion for the Short Term View tab.

Given an entry price and the stock's current ATR, this answers two
questions:
  1. Where would a sensible stop-loss sit? (entry - atr_multiplier * ATR)
  2. How many shares can you buy without risking more than risk_pct of
     your short-term capital pool if that stop gets hit?

Deliberately separate from core/checks.py and core/verdict.py (PP
scoring) — this has nothing to do with fundamentals or the 18-check
framework, it's pure trade-sizing math that only makes sense once
you've already decided a stock is worth a short-term trade (via
Signals/Alerts).

Also caps the suggested quantity so the position's total ₹ value never
exceeds the capital pool itself — a very tight stop on a volatile stock
could otherwise math its way to a quantity that costs more than the
whole pool, which isn't restricted by the risk-based calc alone.
"""

import math


def suggest_stop_and_size(entry_price, atr, capital, risk_pct, atr_multiplier=1.5):
    """Returns a dict:
      stop_price       — suggested stop-loss price
      stop_distance     — ₹ distance from entry to stop (per share)
      risk_amount       — ₹ you're risking on this trade (capital * risk_pct%)
      qty               — suggested share quantity (0 if inputs invalid)
      position_value    — qty * entry_price
      capped_by_capital — True if qty was reduced to fit the capital pool
                           rather than the risk-based number

    Returns None if atr is missing/zero or entry_price is invalid — the
    caller (ui/short_term_view.py) should show "Not enough data for a
    sizing suggestion" in that case rather than a misleading zero.
    """
    if not entry_price or entry_price <= 0:
        return None
    if not atr or atr <= 0:
        return None
    if not capital or capital <= 0:
        return None

    stop_distance = round(atr * atr_multiplier, 2)
    if stop_distance <= 0:
        return None

    stop_price = round(entry_price - stop_distance, 2)
    risk_amt = round(capital * risk_pct / 100.0, 2)

    raw_qty = math.floor(risk_amt / stop_distance)

    capped_by_capital = False
    max_qty_by_capital = math.floor(capital / entry_price)
    qty = raw_qty
    if qty > max_qty_by_capital:
        qty = max_qty_by_capital
        capped_by_capital = True

    qty = max(qty, 0)
    position_value = round(qty * entry_price, 2)

    return {
        "stop_price": stop_price,
        "stop_distance": stop_distance,
        "risk_amount": risk_amt,
        "qty": qty,
        "position_value": position_value,
        "capped_by_capital": capped_by_capital,
    }
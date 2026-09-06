"""
config/gtt_levels.py — your own GTT (Good Till Triggered) buy-order price
levels, per symbol. Purely a lookup table you maintain by hand as you set
up real GTT orders with your broker — this file has no connection to your
actual broker account, it just lets the app show "how far is the current
price from my nearest planned entry level."

Add symbols as you go. A symbol with no entry here simply shows no GTT
context — that's expected and fine, not an error.
"""

GTT_LEVELS = {
    "TCS": [3100, 2950, 2800],
    "BLS": [230, 250],
}
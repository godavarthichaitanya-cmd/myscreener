"""
config/stock_universe.py — wraps sector_universe.load_universe() (project
root — reads stock_universe.csv, built by running build_universe.py from
the project root) into the shape the rest of the app expects: a searchable
symbol picker for ui/single_stock.py, and Sector/CapCategory lookups for
peer-alternative matching in core/suggestions.py.

SETUP: download NSE's EQUITY_L.csv (nseindia.com > Market Data > Equity >
Securities available for Trading) into the project root, then run
`python build_universe.py` once (~20-30 min for the full ~2,000-symbol
list). Until that's done, sector_universe.load_universe() already
degrades gracefully to bare-symbol entries with Sector/Industry/
CapCategory all "Unknown" — the symbol picker still works (just without
company names), but peer suggestions in core/suggestions.py won't find
anything until real Sector data exists.

Cached with st.cache_data since load_universe() re-reads a ~2,000-row CSV
from disk — without caching, every Streamlit rerun (which happens on
basically every widget interaction) would re-read the whole file.
"""

import streamlit as st
from sector_universe import load_universe as _load_universe_raw


@st.cache_data(ttl=3600)
def _load_universe_cached():
    return _load_universe_raw()


def get_universe_options():
    """
    Builds the "SYMBOL — Company Name" label list for the searchable
    picker, plus a lookup back from label to bare symbol. Falls back to
    plain "SYMBOL" (no dash/name) for rows with no CompanyName yet — which
    will be every row until build_universe.py has actually been run.
    """
    universe = _load_universe_cached()
    label_to_symbol = {}
    for row in universe:
        symbol = row["Symbol"]
        name = row.get("CompanyName", "")
        label = f"{symbol} — {name}" if name else symbol
        label_to_symbol[label] = symbol
    return sorted(label_to_symbol.keys()), label_to_symbol


def get_universe_rows():
    """Returns the full list of universe row dicts — used by
    core/suggestions.py to filter by Sector/CapCategory directly rather
    than re-deriving them one symbol at a time."""
    return _load_universe_cached()


def search_universe(query: str, limit: int = 15):
    """
    Ranked search over the universe, replacing st.selectbox's native
    filtering — that default behavior is a plain substring match anywhere
    in the label, so searching "TATA" returns every Tata-group company at
    once (TCS, TATAMOTORS, TATASTEEL, TATAPOWER...) with no ordering by
    relevance, which gets noisy fast across ~2,000 symbols.

    Ranks matches (lower = better):
        0 — exact symbol match
        1 — symbol starts with the query
        2 — any word in the company name starts with the query
        3 — plain substring match anywhere in symbol or name
    Ties within a rank are broken alphabetically by symbol. Returns a list
    of (label, symbol) tuples, capped to `limit`. Returns an empty list
    for an empty/whitespace query — callers should treat that as "nothing
    typed yet," not "no matches."
    """
    query = query.strip().upper()
    if not query:
        return []

    ranked = []
    for row in _load_universe_cached():
        symbol = row["Symbol"]
        name = row.get("CompanyName", "")
        name_upper = name.upper()

        if symbol == query:
            rank = 0
        elif symbol.startswith(query):
            rank = 1
        elif any(word.startswith(query) for word in name_upper.split()):
            rank = 2
        elif query in symbol or query in name_upper:
            rank = 3
        else:
            continue

        label = f"{symbol} — {name}" if name else symbol
        ranked.append((rank, symbol, label))

    ranked.sort(key=lambda r: (r[0], r[1]))
    return [(label, symbol) for _, symbol, label in ranked[:limit]]


def get_sector(symbol: str):
    """
    Returns the Sector string for a symbol, or None if it's not in the
    universe at all. Note this is distinct from the literal string
    "Unknown" (a symbol that IS in the universe but hasn't had
    build_universe.py run for it yet, or whose yfinance data genuinely
    has no sector) — callers that care about that distinction should
    check for "Unknown" explicitly.
    """
    for row in _load_universe_cached():
        if row["Symbol"] == symbol.upper():
            return row.get("Sector")
    return None


def get_cap_category(symbol: str):
    """Returns the CapCategory string ("Large Cap"/"Mid Cap"/"Small
    Cap"/"Unknown") for a symbol, or None if it's not in the universe."""
    for row in _load_universe_cached():
        if row["Symbol"] == symbol.upper():
            return row.get("CapCategory")
    return None
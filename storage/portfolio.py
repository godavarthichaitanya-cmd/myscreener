"""
storage/portfolio.py — portfolio holdings, persisted to CSV.

Replaces the earlier config/portfolio.py (a hardcoded HOLDINGS dict that
required a code edit to update) so holdings match every other piece of
user-entered data in this app: manual_data.py, watchlist.py, notes.py,
reject_log.py are all small CSV-backed storage/ modules, editable at
runtime. config/portfolio.py can be deleted once this is wired in —
batch.py's "Full Portfolio" preset now imports get_portfolio_symbols()
from here instead.

CSV columns: symbol, quantity, avg_price
"""

import os
import pandas as pd

HOLDINGS_CSV = "portfolio_holdings.csv"
_COLUMNS = ["symbol", "quantity", "avg_price"]


def _ensure_seed():
    """First-run seed — carries over the one real entry that was in the
    old config/portfolio.py (HDFCBANK, avg_price 791.39). Quantity was
    never actually filled in there either; now that holdings are editable
    in the Portfolio tab itself, that's the place to fix it rather than a
    code edit."""
    if os.path.exists(HOLDINGS_CSV):
        return
    seed = pd.DataFrame([{"symbol": "HDFCBANK", "quantity": 0, "avg_price": 791.39}])
    seed.to_csv(HOLDINGS_CSV, index=False)


def load_holdings():
    """Returns {symbol: {"quantity": int, "avg_price": float or None}}."""
    _ensure_seed()
    df = pd.read_csv(HOLDINGS_CSV)
    holdings = {}
    for _, row in df.iterrows():
        symbol = str(row["symbol"]).strip().upper()
        if not symbol or symbol == "NAN":
            continue
        avg_price = row.get("avg_price")
        quantity = row.get("quantity")
        holdings[symbol] = {
            "quantity": int(quantity) if pd.notna(quantity) else 0,
            "avg_price": float(avg_price) if pd.notna(avg_price) else None,
        }
    return holdings


def load_holdings_df():
    """Same data as load_holdings(), but as a DataFrame — what the
    Portfolio tab's st.data_editor expects as its starting value."""
    _ensure_seed()
    df = pd.read_csv(HOLDINGS_CSV)
    for col in _COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[_COLUMNS]


def save_holdings_df(df: pd.DataFrame):
    """Overwrites the whole CSV from a DataFrame — used directly with the
    Portfolio tab's edited st.data_editor output."""
    clean = df.copy()
    clean["symbol"] = clean["symbol"].astype(str).str.strip().str.upper()
    clean = clean[(clean["symbol"] != "") & (clean["symbol"] != "NAN")]
    clean = clean.drop_duplicates(subset="symbol", keep="last")
    clean.to_csv(HOLDINGS_CSV, index=False)


def get_portfolio_symbols():
    """Symbols with a real avg_price set — same filter batch.py's "Full
    Portfolio" preset already relied on from the old config/portfolio.py
    (quantity isn't required here; Batch only needs the symbol list, P&L
    math is the Portfolio tab's job)."""
    holdings = load_holdings()
    return [symbol for symbol, values in holdings.items() if values.get("avg_price") is not None]

def get_held_qty(symbol):
    if not os.path.isfile(HOLDINGS_CSV):
        return 0
    df = pd.read_csv(HOLDINGS_CSV)
    row = df[df["symbol"] == symbol]
    if row.empty:
        return 0
    return int(row.iloc[0]["quantity"])
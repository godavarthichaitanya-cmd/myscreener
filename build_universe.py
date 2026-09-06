"""
Builder: fetches live Sector, Industry, and Market Cap for every symbol in
CANDIDATE_UNIVERSE via yfinance, and writes a structured stock_universe.csv
that sector_universe.py loads from.

Run manually when you want to refresh the universe:
    python build_universe.py            # skip symbols already in the CSV
    python build_universe.py --refresh  # re-fetch every symbol from scratch

CANDIDATE_UNIVERSE now comes from NSE's official EQUITY_L.csv when present
(~2,000+ mainboard symbols) instead of the original curated 300 — see
sector_universe.py. A FULL first run at that size takes roughly 20-30
minutes (yfinance rate limits), so this checkpoints progress to disk every
50 symbols: if it crashes or you Ctrl+C partway through, re-running picks
up only the symbols still missing rather than starting over.
"""
import csv
import os
import sys
import time
import yfinance as yf
from sector_universe import CANDIDATE_UNIVERSE

OUTPUT_FILE = "stock_universe.csv"
FIELDNAMES = ["Symbol", "CompanyName", "Sector", "Industry", "MarketCapCr", "CapCategory"]
CHECKPOINT_EVERY = 50

# Cap tier thresholds in INR crore — approximate, matches commonly used
# SEBI-adjacent buckets. Edit these if your own definition differs.
LARGE_CAP_CR = 50000
MID_CAP_CR = 15000


def cap_category(market_cap_inr):
    if market_cap_inr is None:
        return "Unknown"
    cr = market_cap_inr / 1e7  # INR to crore
    if cr >= LARGE_CAP_CR:
        return "Large Cap"
    elif cr >= MID_CAP_CR:
        return "Mid Cap"
    else:
        return "Small Cap"


def load_existing_rows():
    """Returns {symbol: row_dict} for whatever's already in stock_universe.csv,
    so a re-run can skip symbols that were already successfully fetched."""
    if not os.path.exists(OUTPUT_FILE):
        return {}
    with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
        return {row["Symbol"]: row for row in csv.DictReader(f)}


def write_rows(rows_by_symbol):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_by_symbol.values())


def build(force_refresh=False):
    existing = {} if force_refresh else load_existing_rows()
    rows = dict(existing)

    to_fetch = [s for s in CANDIDATE_UNIVERSE if force_refresh or s not in existing]
    total = len(to_fetch)

    print(f"{len(CANDIDATE_UNIVERSE)} total symbols in universe.")
    print(f"{len(existing)} already cached, fetching {total} new/refreshed symbols...")
    if total == 0:
        print("Nothing to do — everything's already cached. Use --refresh to re-fetch all.")
        return

    for i, symbol in enumerate(to_fetch):
        print(f"[{i+1}/{total}] {symbol}...")
        try:
            info = yf.Ticker(f"{symbol}.NS").info
            market_cap = info.get("marketCap")
            rows[symbol] = {
                "Symbol": symbol,
                "CompanyName": info.get("longName", ""),
                "Sector": info.get("sector", "Unknown"),
                "Industry": info.get("industry", "Unknown"),
                "MarketCapCr": round(market_cap / 1e7, 0) if market_cap else "",
                "CapCategory": cap_category(market_cap),
            }
        except Exception as e:
            print(f"  ⚠️ failed: {e}")
            rows[symbol] = {
                "Symbol": symbol, "CompanyName": "", "Sector": "Unknown",
                "Industry": "Unknown", "MarketCapCr": "", "CapCategory": "Unknown",
            }

        if (i + 1) % CHECKPOINT_EVERY == 0:
            write_rows(rows)
            print(f"  💾 checkpoint saved ({i+1}/{total} fetched this run, {len(rows)} total in file)")

        time.sleep(0.3)  # gentle on rate limits

    write_rows(rows)
    print(f"\n✅ Wrote {len(rows)} total rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    build(force_refresh="--refresh" in sys.argv)
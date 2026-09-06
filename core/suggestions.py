"""
core/suggestions.py — when a stock evaluates to "Avoid," this scans other
stocks in the same sector (from the real universe in
config/stock_universe.py, once you've run build_universe.py) and surfaces
any that score better, so you're not left with just "don't buy this" and
nothing else to look at.

Peers are evaluated WITHOUT manual pledge/EPS CAGR data (that's specific
to stocks you've personally researched via storage/manual_data.py) — so a
peer's score reflects only what's auto-fetchable. This means a peer's
score is not perfectly apples-to-apples with a stock you've fully
evaluated yourself, but it's still a reasonable first filter for "worth a
closer look."

At full universe size (~2,000 symbols), a sector can easily have 100+
peers — MAX_PEERS_TO_SCAN caps how many are actually fetched and evaluated
per suggestion request, since each one is a live yfinance call. Peers are
scanned in the order the universe file lists them; consider sorting the
universe by market cap in build_universe.py later if you want the biggest
names checked first.
"""

from config.stock_universe import get_universe_rows, get_sector, get_cap_category
from core.bundle import fetch_stock_bundle
from core.checks import build_checks, score_checks
from core.verdict import build_verdict
from config.sectors import is_bank_or_nbfc

MAX_PEERS_TO_SCAN = 25


def get_peer_suggestions(symbol: str, limit: int = 5):
    """
    Returns a list of dicts, best-first, for same-sector peers that score
    at least as well as a middling stock (fundamentals AND technicals both
    above 40%, deliberately looser than the "Deploy ready" bar since the
    point here is "worth investigating," not a final verdict). Returns an
    empty list if the stock's sector isn't known, no peers exist, or no
    peer clears the bar.
    """
    sector = get_sector(symbol)
    if sector is None or sector == "Unknown":
        return []

    own_cap = get_cap_category(symbol)
    universe = get_universe_rows()
    peers = [row for row in universe if row.get("Sector") == sector and row["Symbol"] != symbol.upper()]
    peers = peers[:MAX_PEERS_TO_SCAN]

    results = []
    for peer in peers:
        peer_symbol = peer["Symbol"]
        try:
            d = fetch_stock_bundle(peer_symbol)
            bank_flag = is_bank_or_nbfc(peer_symbol)
            checks = build_checks(
                d["fund"], d["interest_coverage"], d["current_price"], d["ema200"],
                d["rsi14"], d["macd_bull"], pledge=None, eps_cagr_5yr=None,
                roce=d["roce"], margin_trend=d["margin_trend"],
                volume_ratio=d["volume_ratio"], rel_strength=d["rel_strength"],
                is_bank=bank_flag, piotroski=d["piotroski"], golden_cross=d["golden_cross"],
            )
            passed, total = score_checks(checks)
            icon, verdict_text, color, fund_rate, tech_rate = build_verdict(checks, gtt=None, current_price=d["current_price"])

            if fund_rate >= 0.40 and tech_rate >= 0.40:
                results.append({
                    "symbol": peer_symbol,
                    "name": peer.get("CompanyName", ""),
                    "verdict": verdict_text,
                    "icon": icon,
                    "color": color,
                    "fund_pct": round(fund_rate * 100),
                    "tech_pct": round(tech_rate * 100),
                    "score_pct": round((passed / total) * 100) if total else 0,
                    "current_price": d["current_price"],
                    "cap_category": peer.get("CapCategory", "Unknown"),
                    "same_cap_tier": own_cap is not None and peer.get("CapCategory") == own_cap,
                })
        except Exception:
            continue  # a single peer failing to fetch shouldn't break the whole suggestion list

    results.sort(key=lambda r: r["fund_pct"] + r["tech_pct"], reverse=True)
    return results[:limit]
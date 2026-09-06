"""
core/graham.py — Benjamin Graham's classic Fair Value formula:
    Fair Value = EPS x (8.5 + 2 x growth_rate)
where growth_rate is expected annual EPS growth (%). This is a
conservative intrinsic-value estimate — high-quality compounders often
trade above it, so treat it as directional context, not a pass/fail gate
(it's intentionally NOT one of the scored PP/Sampat checks).

EPS ISN'T DIRECTLY AVAILABLE from data.fetch's fundamentals bundle, so
it's derived here as current_price / PE — this is why Graham Fair Value
can't be computed at all when PE is None (loss-making companies, etc).

GROWTH RATE PRIORITY: your manually entered 5yr EPS CAGR (from
Screener.in, via storage/manual_data.py) is used whenever it's set,
because it correctly accounts for corporate actions (splits, bonus
issues, mergers) that a naive year-over-year share-count comparison
can't detect. The auto-fetched 3yr CAGR from data.fetch.fetch_eps_cagr()
is only a fallback for stocks you haven't manually entered yet — this
was a real, confirmed problem for HDFC Bank, whose 2023 merger with
HDFC Ltd added ~311 crore new shares non-organically and made the
auto-fetched growth figure meaningless.
"""


def compute_graham_fair_value(current_price: float, pe: float, manual_eps_cagr_5yr, auto_eps_cagr_3yr):
    """
    Returns a dict:
        {
            "fair_value": float or None,
            "margin_pct": float or None,   # how far below/above fair value the current price sits
            "growth_used": float or None,  # the growth rate actually used in the formula
            "growth_source": "manual (5yr)" | "auto (3yr)" | None,
        }
    Returns all-None fields if PE is missing (can't derive EPS) or no
    growth rate is available from either source.
    """
    empty = {"fair_value": None, "margin_pct": None, "growth_used": None, "growth_source": None}

    if pe is None or pe <= 0:
        return empty

    eps = current_price / pe

    if manual_eps_cagr_5yr is not None and manual_eps_cagr_5yr != 0:
        growth = manual_eps_cagr_5yr
        source = "manual (5yr)"
    elif auto_eps_cagr_3yr is not None:
        growth = auto_eps_cagr_3yr
        source = "auto (3yr) — no manual entry set"
    else:
        return empty

    fair_value = eps * (8.5 + 2 * growth)
    if fair_value <= 0:
        return empty

    margin_pct = round(((fair_value - current_price) / fair_value) * 100, 1)

    return {
        "fair_value": round(fair_value, 2),
        "margin_pct": margin_pct,
        "growth_used": round(growth, 2),
        "growth_source": source,
    }
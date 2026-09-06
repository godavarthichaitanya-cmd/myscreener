"""
core/bundle.py — the single place that pulls together everything needed to
evaluate one stock: price history, fundamentals, and technical indicators.
This is the "glue" layer between data/ (raw fetching/math) and core/checks.py
+ core/verdict.py (pure scoring logic) — nothing in here talks to Streamlit.

DATA-SUFFICIENCY POLICY FOR TECHNICALS:
This is the part that was ambiguous in the old app and caused the EMMVEE
confusion. The rule here is explicit and tunable via the constants below:

  - RSI needs at least RSI_MIN_ROWS rows of history to be considered
    trustworthy (its 14-day rolling average needs to have "warmed up").
  - MACD needs at least MACD_MIN_ROWS rows (its slowest EMA is 26-day, plus
    a 9-day signal line smoothing on top).
  - EMA200 is trickier: mathematically, ewm() never produces NaN even with
    very little history (unlike a rolling SMA), so it will always return
    SOME number. But a "200 EMA" computed off only, say, 40 days of data
    isn't really a meaningful long-term trend line yet — it's just an
    early average dressed up with a 200-day label. EMA200_MIN_ROWS is set
    to require the full 200 rows before trusting it, matching the same bar
    Golden Cross already uses in data/indicators.py — so both checks
    switch from N/A to real together as a stock accumulates history.

Adjust these constants if you decide a looser or stricter bar makes more
sense once you've run this against a few real stocks.
"""

from data.fetch import (
    fetch_price_history, get_current_price, fetch_fundamentals,
    fetch_interest_coverage, fetch_roce, fetch_margin_trend,
    fetch_volume_confirmation, fetch_relative_strength, fetch_piotroski_score,
    fetch_eps_cagr,
)
from data.indicators import (
    calculate_ema, calculate_rsi, calculate_macd, get_golden_cross,
    calculate_atr, get_52wk_range,
)

RSI_MIN_ROWS = 15
MACD_MIN_ROWS = 35
EMA200_MIN_ROWS = 200


def fetch_stock_bundle(symbol: str) -> dict:
    """
    Fetches and computes everything needed for one stock evaluation.
    Returns a dict consumed directly by core.checks.build_checks() (via
    the keys ema200/rsi14/macd_bull etc.) and by the UI layer for display.

    ema200 / rsi14 / macd_bull are explicitly set to None below when there
    isn't enough price history to trust them — see the module docstring —
    rather than always computing and returning a number regardless of how
    little history backs it.
    """
    df = fetch_price_history(symbol)
    current_price = get_current_price(symbol)
    fund = fetch_fundamentals(symbol)

    rows = len(df)

    ema200 = None
    if rows >= EMA200_MIN_ROWS:
        ema200 = round(calculate_ema(df, 200).iloc[-1], 2)

    rsi14 = None
    if rows >= RSI_MIN_ROWS:
        rsi_series = calculate_rsi(df, 14)
        if not rsi_series.empty and rsi_series.iloc[-1] == rsi_series.iloc[-1]:  # NaN-safe check
            rsi14 = round(rsi_series.iloc[-1], 2)

    macd_bull = None
    if rows >= MACD_MIN_ROWS:
        macd_line, signal_line, _ = calculate_macd(df)
        macd_bull = bool(macd_line.iloc[-1] > signal_line.iloc[-1])

    golden_cross = get_golden_cross(df)  # already returns None under 200 rows, see data/indicators.py

    # ---- Context-only extras (not scored, used for the Fetch display) ----
    range_52wk = get_52wk_range(df)
    pct_below_high = round(((range_52wk["high_52wk"] - current_price) / range_52wk["high_52wk"]) * 100, 2)

    atr_series = calculate_atr(df, 14)
    atr_val = round(atr_series.iloc[-1], 2) if atr_series.iloc[-1] == atr_series.iloc[-1] else None  # NaN-safe
    atr_pct = round((atr_val / current_price) * 100, 2) if atr_val else None

    eps_cagr_3yr_auto = fetch_eps_cagr(symbol)  # fallback for core.graham when no manual entry exists yet

    data_warning = None
    if rows < EMA200_MIN_ROWS:
        data_warning = (
            f"⚠️ Only {rows} trading days of history — 200 EMA, Golden Cross, "
            f"and possibly RSI/MACD are unavailable or excluded from scoring "
            f"until more history builds up."
        )

    return {
        "symbol": symbol.upper(),
        "current_price": current_price,
        "fund": fund,
        "interest_coverage": fetch_interest_coverage(symbol),
        "roce": fetch_roce(symbol),
        "margin_trend": fetch_margin_trend(symbol),
        "volume_ratio": fetch_volume_confirmation(df),
        "rel_strength": fetch_relative_strength(symbol),
        "piotroski": fetch_piotroski_score(symbol),
        "ema200": ema200,
        "rsi14": rsi14,
        "macd_bull": macd_bull,
        "golden_cross": golden_cross,
        "rows_of_history": rows,
        "data_warning": data_warning,
        "range_52wk": range_52wk,
        "pct_below_high": pct_below_high,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "eps_cagr_3yr_auto": eps_cagr_3yr_auto,
        "price_history": df,  # kept for the chart — see ui/single_stock.py
    }
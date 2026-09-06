import yfinance as yf
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# CACHE-POISONING PATTERN USED THROUGHOUT THIS FILE
# ---------------------------------------------------------------------------
# Every yfinance-backed fetcher below is split into two functions:
#   1. A cached "_raw" function that does the actual network call. If
#      something goes wrong (rate limit, network blip, bad symbol), it lets
#      the exception propagate UNCAUGHT. st.cache_data only ever caches a
#      successful return value, never an exception — so a transient failure
#      is retried on the very next call instead of being locked in as a
#      false "no data" result for the full 1hr cache TTL.
#   2. An uncached public wrapper that calls the _raw function and catches
#      the exception, returning a safe fallback (None or an all-None dict)
#      ONLY at this outer, uncached layer.
# This split matters: if the fallback were built and returned *inside* the
# cached function, a single bad fetch (e.g. a mid-run rate limit) would get
# cached as if it were a genuine "no data" result for a real, healthy stock
# for up to an hour. Keep this pattern for any new fetcher added here.
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def fetch_price_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """
    Pulls daily OHLCV price history for a stock from yfinance (NSE, via the
    .NS suffix). This is the base dataset that EMA/RSI/MACD/Golden Cross
    and the price chart are all computed from. Raises ValueError on an
    unrecognized symbol so callers can show a clear "not found" message
    instead of a confusing downstream crash.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    if df.empty:
        raise ValueError(f"Symbol '{symbol.upper()}' not found on NSE. Check the spelling.")
    return df


@st.cache_data(ttl=3600)
def get_current_price(symbol: str) -> float:
    """
    Latest close price for a symbol — used everywhere the app needs "the
    current price" (hero banner, GTT distance, PE display, portfolio P&L).
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    todays_data = stock.history(period="1d")
    if todays_data.empty:
        raise ValueError(f"Symbol '{symbol.upper()}' not found on NSE. Check the spelling.")
    return round(todays_data["Close"].iloc[-1], 2)


@st.cache_data(ttl=3600)
def _fetch_fundamentals_raw(symbol: str) -> dict:
    """
    Pulls the core fundamentals bundle from yfinance's `.info` payload:
    PE, ROE, D/E, PEG (falling back to a manually estimated PEG from PE
    and earnings growth if yfinance doesn't supply one directly), revenue
    growth, free cash flow (and whether it's positive), dividend yield,
    sector/industry classification, and business summary text.
    See the module docstring above for why exceptions propagate uncaught
    here rather than being swallowed inside this cached function.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    info = stock.info
    if not info:
        raise ValueError(f"No info returned for {symbol}")

    de_raw = info.get("debtToEquity")
    de_ratio = round(de_raw / 100, 2) if de_raw is not None else None

    fcf = info.get("freeCashflow")
    ocf = info.get("operatingCashflow")

    peg = info.get("pegRatio")
    peg_estimated = False
    if peg is None:
        pe = info.get("trailingPE")
        growth = info.get("earningsGrowth")
        if pe is not None and growth is not None and growth > 0:
            peg = round(pe / (growth * 100), 2)
            peg_estimated = True
    elif peg is not None:
        peg = round(peg, 2)

    div_yield_raw = info.get("dividendYield")
    div_yield = round(div_yield_raw, 2) if div_yield_raw is not None else None

    return {
        "pe": round(info.get("trailingPE"), 2) if info.get("trailingPE") else None,
        "roe": round(info.get("returnOnEquity") * 100, 2) if info.get("returnOnEquity") else None,
        "de": de_ratio,
        "peg": peg,
        "peg_estimated": peg_estimated,
        "revenue_growth_yoy": round(info.get("revenueGrowth") * 100, 2) if info.get("revenueGrowth") else None,
        "fcf": fcf,
        "ocf": ocf,
        "fcf_positive": fcf is not None and fcf > 0,
        "insider_holding_proxy": round(info.get("heldPercentInsiders") * 100, 2) if info.get("heldPercentInsiders") else None,
        "dividend_yield": div_yield,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "business_summary": info.get("longBusinessSummary"),
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website"),
    }


def fetch_fundamentals(symbol: str) -> dict:
    """
    Public, uncached entry point for the fundamentals bundle above. Catches
    fetch failures here (not inside the cached _raw function — see module
    docstring) and returns an all-None dict shaped identically to a real
    result, so downstream code can treat "genuinely no data" and "failed
    to fetch" the same way without special-casing.
    """
    empty_result = {
        "pe": None, "roe": None, "de": None, "peg": None, "peg_estimated": False,
        "revenue_growth_yoy": None, "fcf": None, "ocf": None,
        "fcf_positive": False, "insider_holding_proxy": None,
        "dividend_yield": None, "sector": None, "industry": None,
        "business_summary": None, "employees": None, "website": None,
    }
    try:
        return _fetch_fundamentals_raw(symbol)
    except Exception:
        return empty_result


@st.cache_data(ttl=3600)
def _fetch_interest_coverage_raw(symbol: str):
    """
    Interest Coverage = EBIT / interest expense — how many times over a
    company's operating profit could cover its interest payments. Tries
    a couple of possible yfinance row-name variants since financial
    statement labeling isn't perfectly standardized across companies.
    Returns None when the rows genuinely aren't present (e.g. banks
    report this differently) — that's a legitimate result, not a failure.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    financials = stock.financials
    ebit = None
    interest_expense = None
    for row_name in ["EBIT", "Operating Income"]:
        if row_name in financials.index:
            ebit = financials.loc[row_name].iloc[0]
            break
    for row_name in ["Interest Expense", "Interest Expense Non Operating"]:
        if row_name in financials.index:
            interest_expense = abs(financials.loc[row_name].iloc[0])
            break
    if ebit is not None and interest_expense not in (None, 0):
        return round(ebit / interest_expense, 2)
    return None


def fetch_interest_coverage(symbol: str):
    """Uncached wrapper — see module docstring for the cache-poisoning fix pattern."""
    try:
        return _fetch_interest_coverage_raw(symbol)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _fetch_roce_raw(symbol: str):
    """
    ROCE = EBIT / Capital Employed, where Capital Employed = Total Assets
    minus Current Liabilities. A truer efficiency measure than ROE alone
    since it accounts for the total capital base (debt + equity), so it
    can't be flattered purely by leverage the way ROE sometimes can.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    financials = stock.financials
    balance_sheet = stock.balance_sheet

    ebit = None
    for row_name in ["EBIT", "Operating Income"]:
        if row_name in financials.index:
            ebit = financials.loc[row_name].iloc[0]
            break

    total_assets = None
    current_liabilities = None
    for row_name in ["Total Assets"]:
        if row_name in balance_sheet.index:
            total_assets = balance_sheet.loc[row_name].iloc[0]
            break
    for row_name in ["Current Liabilities", "Total Current Liabilities"]:
        if row_name in balance_sheet.index:
            current_liabilities = balance_sheet.loc[row_name].iloc[0]
            break

    if ebit is not None and total_assets is not None and current_liabilities is not None:
        capital_employed = total_assets - current_liabilities
        if capital_employed > 0:
            return round((ebit / capital_employed) * 100, 2)
    return None


def fetch_roce(symbol: str):
    """Uncached wrapper — see module docstring for the cache-poisoning fix pattern."""
    try:
        return _fetch_roce_raw(symbol)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _fetch_margin_trend_raw(symbol: str):
    """
    Compares operating margin (Operating Income / Revenue) today against
    the same figure 3 annual periods ago, to see whether profitability
    per rupee of sales is expanding or eroding over time — revenue can
    grow while margins quietly shrink from competition or rising costs.
    Needs at least 4 annual periods of data (yfinance's typical depth);
    returns None for newer listings that don't have that history yet.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    financials = stock.financials
    op_income_row = None
    for row_name in ["Operating Income"]:
        if row_name in financials.index:
            op_income_row = financials.loc[row_name]
            break
    revenue_row = None
    for row_name in ["Total Revenue", "Operating Revenue"]:
        if row_name in financials.index:
            revenue_row = financials.loc[row_name]
            break

    if op_income_row is None or revenue_row is None:
        return None
    if len(op_income_row) < 4 or len(revenue_row) < 4:
        return None

    margin_now = op_income_row.iloc[0] / revenue_row.iloc[0]
    margin_3yr_ago = op_income_row.iloc[3] / revenue_row.iloc[3]

    if pd.isna(margin_now) or pd.isna(margin_3yr_ago):
        return None

    change = round((margin_now - margin_3yr_ago) * 100, 2)
    return {
        "margin_now": round(margin_now * 100, 2),
        "margin_3yr_ago": round(margin_3yr_ago * 100, 2),
        "change_pts": change,
    }


def fetch_margin_trend(symbol: str):
    """Uncached wrapper — see module docstring for the cache-poisoning fix pattern."""
    try:
        return _fetch_margin_trend_raw(symbol)
    except Exception:
        return None


def fetch_volume_confirmation(df: pd.DataFrame):
    """
    Compares today's trading volume against the trailing 20-day average
    volume (excluding today itself) to check whether a price move is
    backed by real conviction or happening on thin, unconvincing volume.
    Operates on an already-fetched price DataFrame — no network call of
    its own, so there's no cache-poisoning risk here; left uncached.
    """
    try:
        if len(df) < 21:
            return None
        recent_volume = df["Volume"].iloc[-1]
        avg_volume_20d = df["Volume"].iloc[-21:-1].mean()
        if avg_volume_20d == 0:
            return None
        return round(recent_volume / avg_volume_20d, 2)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _fetch_relative_strength_raw(symbol: str, period: str = "3mo"):
    """
    Compares a stock's own price return over `period` against the Nifty
    50's (^NSEI) return over the same window, isolating genuine stock-
    specific outperformance from the stock simply drifting up because the
    whole market is up.
    """
    ticker = f"{symbol.upper()}.NS"
    stock_df = yf.Ticker(ticker).history(period=period)
    nifty_df = yf.Ticker("^NSEI").history(period=period)

    if stock_df.empty or nifty_df.empty:
        return None

    stock_return = ((stock_df["Close"].iloc[-1] - stock_df["Close"].iloc[0]) / stock_df["Close"].iloc[0]) * 100
    nifty_return = ((nifty_df["Close"].iloc[-1] - nifty_df["Close"].iloc[0]) / nifty_df["Close"].iloc[0]) * 100

    return {
        "stock_return": round(stock_return, 2),
        "nifty_return": round(nifty_return, 2),
        "outperformance": round(stock_return - nifty_return, 2),
    }


def fetch_relative_strength(symbol: str, period: str = "3mo"):
    """Uncached wrapper — see module docstring for the cache-poisoning fix pattern."""
    try:
        return _fetch_relative_strength_raw(symbol, period)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _fetch_piotroski_score_raw(symbol: str):
    """
    Simplified 9-point Piotroski F-Score — a balance-sheet and earnings-
    quality checklist covering profitability (positive/improving ROA,
    cash-backed earnings), leverage (decreasing debt, improving current
    ratio), and operating efficiency (no dilution, improving gross margin
    and asset turnover). Each of the 9 criteria only counts toward the
    score if its underlying data is actually available for this stock —
    the returned score is out of however many criteria could be computed
    (max_score), not always a fixed 9, so a newer/thinly-covered stock
    naturally gets a smaller denominator rather than a misleading fail.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    financials = stock.financials
    balance_sheet = stock.balance_sheet
    cashflow = stock.cashflow

    if financials.empty or balance_sheet.empty:
        return None

    points = 0
    max_points = 0
    breakdown = []

    def get_row(df, names):
        for n in names:
            if n in df.index:
                return df.loc[n]
        return None

    net_income = get_row(financials, ["Net Income"])
    total_assets = get_row(balance_sheet, ["Total Assets"])
    ocf = get_row(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
    current_assets = get_row(balance_sheet, ["Current Assets", "Total Current Assets"])
    current_liab = get_row(balance_sheet, ["Current Liabilities", "Total Current Liabilities"])
    long_term_debt = get_row(balance_sheet, ["Long Term Debt", "Total Debt"])
    shares = get_row(financials, ["Diluted Average Shares", "Basic Average Shares"])
    revenue = get_row(financials, ["Total Revenue", "Operating Revenue"])
    gross_profit = get_row(financials, ["Gross Profit"])

    # 1. Positive ROA (Net Income / Total Assets > 0) — is the company profitable at all, per rupee of assets?
    if net_income is not None and total_assets is not None and len(net_income) > 0 and len(total_assets) > 0:
        max_points += 1
        roa = net_income.iloc[0] / total_assets.iloc[0]
        if roa > 0:
            points += 1
        breakdown.append(("Positive ROA", roa > 0))

    # 2. Positive Operating Cash Flow — is the core business actually generating cash, not just accounting profit?
    if ocf is not None and len(ocf) > 0:
        max_points += 1
        ok = ocf.iloc[0] > 0
        if ok:
            points += 1
        breakdown.append(("Positive operating cash flow", ok))

    # 3. ROA improving YoY — is profitability-per-asset getting better, not just positive?
    if net_income is not None and total_assets is not None and len(net_income) > 1 and len(total_assets) > 1:
        max_points += 1
        roa_now = net_income.iloc[0] / total_assets.iloc[0]
        roa_prev = net_income.iloc[1] / total_assets.iloc[1]
        ok = roa_now > roa_prev
        if ok:
            points += 1
        breakdown.append(("ROA improving YoY", ok))

    # 4. OCF > Net Income — earnings quality check: is reported profit backed by real cash, or inflated by non-cash items?
    if ocf is not None and net_income is not None and len(ocf) > 0 and len(net_income) > 0:
        max_points += 1
        ok = ocf.iloc[0] > net_income.iloc[0]
        if ok:
            points += 1
        breakdown.append(("OCF exceeds net income (quality)", ok))

    # 5. Leverage decreasing — is long-term debt shrinking relative to total assets?
    if long_term_debt is not None and total_assets is not None and len(long_term_debt) > 1 and len(total_assets) > 1:
        max_points += 1
        lev_now = long_term_debt.iloc[0] / total_assets.iloc[0]
        lev_prev = long_term_debt.iloc[1] / total_assets.iloc[1]
        ok = lev_now < lev_prev
        if ok:
            points += 1
        breakdown.append(("Leverage decreasing YoY", ok))

    # 6. Current ratio improving — is short-term liquidity (ability to cover near-term liabilities) getting healthier?
    if current_assets is not None and current_liab is not None and len(current_assets) > 1 and len(current_liab) > 1:
        max_points += 1
        cr_now = current_assets.iloc[0] / current_liab.iloc[0]
        cr_prev = current_assets.iloc[1] / current_liab.iloc[1]
        ok = cr_now > cr_prev
        if ok:
            points += 1
        breakdown.append(("Current ratio improving", ok))

    # 7. No significant share dilution — has the company avoided issuing a meaningful number of new shares (1% tolerance)?
    if shares is not None and len(shares) > 1:
        max_points += 1
        ok = shares.iloc[0] <= shares.iloc[1] * 1.01
        if ok:
            points += 1
        breakdown.append(("No significant share dilution", ok))

    # 8. Gross margin improving — is per-unit profitability before overhead getting better?
    if gross_profit is not None and revenue is not None and len(gross_profit) > 1 and len(revenue) > 1:
        max_points += 1
        gm_now = gross_profit.iloc[0] / revenue.iloc[0]
        gm_prev = gross_profit.iloc[1] / revenue.iloc[1]
        ok = gm_now > gm_prev
        if ok:
            points += 1
        breakdown.append(("Gross margin improving", ok))

    # 9. Asset turnover improving — is the company generating more revenue per rupee of assets over time (operating efficiency)?
    if revenue is not None and total_assets is not None and len(revenue) > 1 and len(total_assets) > 1:
        max_points += 1
        at_now = revenue.iloc[0] / total_assets.iloc[0]
        at_prev = revenue.iloc[1] / total_assets.iloc[1]
        ok = at_now > at_prev
        if ok:
            points += 1
        breakdown.append(("Asset turnover improving", ok))

    if max_points == 0:
        return None

    return {"score": points, "max_score": max_points, "breakdown": breakdown}


def fetch_piotroski_score(symbol: str):
    """Uncached wrapper — see module docstring for the cache-poisoning fix pattern."""
    try:
        return _fetch_piotroski_score_raw(symbol)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _fetch_eps_cagr_raw(symbol: str):
    """
    Auto-fetched EPS CAGR, computed as a 3-year compound annual growth
    rate (yfinance's annual financials only cover ~4 periods, so this is
    iloc[0] vs iloc[3] — a 3yr figure, NOT a true 5yr CAGR). EPS itself
    isn't reported directly by yfinance's financials — it's derived per
    period as Net Income / (Diluted or Basic) Average Shares.

    This is a FALLBACK ONLY: your manually entered 5yr EPS CAGR (sourced
    from Screener.in) always takes priority over this when set, because
    this auto-fetched version has no way to detect corporate actions
    (stock splits, bonus issues, mergers) that distort a naive period-
    over-period share-count comparison — confirmed concretely on HDFC
    Bank, whose 2023 merger with HDFC Ltd added ~311 crore new shares
    non-organically and produced a misleadingly negative growth reading
    despite the underlying business being healthy.

    Returns None if data is insufficient, or if the base-year EPS was
    <= 0 (CAGR isn't meaningful off a loss-making or zero base) — both
    are legitimate computed results worth caching, not fetch failures.
    """
    ticker = f"{symbol.upper()}.NS"
    stock = yf.Ticker(ticker)
    financials = stock.financials
    if financials.empty:
        return None

    def get_row(df, names):
        for n in names:
            if n in df.index:
                return df.loc[n]
        return None

    net_income = get_row(financials, ["Net Income"])
    shares = get_row(financials, ["Diluted Average Shares", "Basic Average Shares"])

    if net_income is None or shares is None:
        return None
    if len(net_income) < 4 or len(shares) < 4:
        return None

    eps_now_shares = shares.iloc[0]
    eps_base_shares = shares.iloc[3]
    if pd.isna(eps_now_shares) or pd.isna(eps_base_shares) or eps_now_shares == 0 or eps_base_shares == 0:
        return None

    eps_now = net_income.iloc[0] / eps_now_shares
    eps_base = net_income.iloc[3] / eps_base_shares

    if pd.isna(eps_now) or pd.isna(eps_base) or eps_base <= 0:
        return None

    cagr = ((eps_now / eps_base) ** (1 / 3) - 1) * 100
    return round(cagr, 2)


def fetch_eps_cagr(symbol: str):
    """Uncached wrapper — see module docstring for the cache-poisoning fix pattern."""
    try:
        return _fetch_eps_cagr_raw(symbol)
    except Exception:
        return None
"""
core/checks.py — turns fetched data into the PP framework's pass/fail list.

THE THREE-STATE CONVENTION USED THROUGHOUT:
Every check below evaluates to one of three states — this is the exact
distinction that caused confusion during the EMMVEE debugging session, so
it's worth being explicit about it here:

  - True  -> check PASSED
  - False -> check genuinely FAILED (we have real data, and it didn't meet the bar)
  - None  -> check is NOT APPLICABLE / NO DATA (missing data, a bank/NBFC
             exclusion, insufficient price history, etc.)

None is NOT a fail. score_checks() below only counts True/False checks toward
the denominator — a None check doesn't hurt the score, it's simply excluded.
Keep this convention consistent in every new check you add here.

CHANGES IN THIS VERSION (vs. the first draft):
  1. FCF positive now genuinely returns None when fcf data is missing,
     instead of always defaulting to False — so a real data gap no longer
     looks identical to a confirmed negative FCF on the departures board.
  2. PEG is auto-suppressed (returns None) when revenue growth is above
     PEG_GROWTH_SUPPRESS_THRESHOLD, since PEG becomes meaningless/wildly
     skewed for hyper-growth stocks off a tiny base (confirmed on EMMVEE
     in the earlier evaluation session).
  3. ema200 / rsi14 / macd_bull are now allowed to be None (in addition to
     real values) — the caller (whatever builds the stock bundle) can pass
     None for any of these when there isn't enough price history to trust
     the computed value, and the corresponding check will correctly show
     as N/A instead of forcing a True/False off a shaky number.
"""

# Revenue growth (%) above which PEG is considered unreliable and suppressed
# to None rather than shown as a misleading pass/fail. Tune this if you find
# it's too aggressive/conservative once you've run it against a few stocks.
PEG_GROWTH_SUPPRESS_THRESHOLD = 50


def build_checks(
    fund,                # dict from data.fetch.fetch_fundamentals()
    interest_coverage,   # float or None, from data.fetch.fetch_interest_coverage()
    current_price,       # float, from data.fetch.get_current_price()
    ema200,               # float OR None — pass None if there's insufficient price history to trust it
    rsi14,                # float OR None — pass None if there's insufficient price history to trust it
    macd_bull,            # bool OR None — pass None if there's insufficient price history to trust it
    pledge=None,           # float or None — manually entered promoter pledge %
    eps_cagr_5yr=None,      # float or None — manually entered 5yr EPS CAGR %
    roce=None,               # float or None, from data.fetch.fetch_roce()
    margin_trend=None,        # dict or None, from data.fetch.fetch_margin_trend()
    volume_ratio=None,         # float or None, from data.fetch.fetch_volume_confirmation()
    rel_strength=None,          # dict or None, from data.fetch.fetch_relative_strength()
    is_bank=False,                # bool — from config.sectors.is_bank_or_nbfc(symbol)
    piotroski=None,                # dict or None, from data.fetch.fetch_piotroski_score()
    golden_cross=None,              # bool or None, from data.indicators.get_golden_cross()
):
    """
    Builds the full list of (label, result) tuples for one stock, where
    result is True / False / None as described above. Order here is the
    order checks are logged and rendered everywhere downstream, so the
    grouping below (valuation -> profitability -> balance sheet -> quality
    -> technicals -> manual) is intentional, not incidental.
    """
    checks = []

    # ---- VALUATION ----
    # Is the price reasonable relative to earnings?
    checks.append(("PE under 25x", None if fund["pe"] is None else fund["pe"] < 25))

    # ---- PROFITABILITY ----
    # ROE applies to every company, including banks (unlike ROCE/D/E/interest
    # coverage below, which specifically don't make sense for how banks report).
    checks.append(("ROE above 15%", None if fund["roe"] is None else fund["roe"] > 15))

    # ---- BALANCE SHEET (excluded entirely for banks/NBFCs — see is_bank) ----
    if not is_bank:
        # ROCE: profit relative to TOTAL capital (debt + equity) — can't be
        # flattered by leverage alone the way ROE sometimes can.
        checks.append(("ROCE above 15%", None if roce is None else roce > 15))
        # D/E: how much of the company's capital is borrowed vs shareholder-owned.
        checks.append(("D/E under 0.5x", None if fund["de"] is None else fund["de"] < 0.5))
        # Interest coverage: does operating profit comfortably cover loan interest?
        checks.append(("Interest coverage above 5x", None if interest_coverage is None else interest_coverage > 5))

    # ---- VALUATION (continued) ----
    # PEG: PE adjusted for growth rate — is a higher PE justified by faster
    # growth? Auto-suppressed to None for hyper-growth stocks where the
    # ratio becomes meaningless (see PEG_GROWTH_SUPPRESS_THRESHOLD above).
    revenue_growth = fund.get("revenue_growth_yoy")
    peg_suppressed = revenue_growth is not None and revenue_growth > PEG_GROWTH_SUPPRESS_THRESHOLD
    if fund["peg"] is None or peg_suppressed:
        checks.append(("PEG under 1.0x", None))
    else:
        checks.append(("PEG under 1.0x", fund["peg"] < 1.0))

    # ---- PROFITABILITY (continued) ----
    # Revenue growth: is the business genuinely getting bigger year over year?
    checks.append(("Revenue growth above 10%", None if revenue_growth is None else revenue_growth > 10))

    if not is_bank:
        # Margin trend: is profitability per rupee of sales expanding or eroding
        # over 3 years? Revenue can grow while margins quietly shrink.
        checks.append(("Operating margin expanding (3yr)", None if margin_trend is None else margin_trend["change_pts"] > 0))
        # FCF: real spendable cash left after running the business. Now checks
        # the underlying fcf value directly (not just fcf_positive), so a
        # genuine data gap correctly shows N/A instead of masquerading as a fail.
        fcf = fund.get("fcf")
        checks.append(("FCF positive", None if fcf is None else fcf > 0))

    # ---- QUALITY ----
    # Piotroski F-Score: 9-point balance-sheet/earnings-quality checklist.
    checks.append(("Piotroski F-Score >= 7", None if piotroski is None else piotroski["score"] >= 7))

    # ---- TECHNICALS / ENTRY TIMING ----
    # ema200 / rsi14 / macd_bull can now genuinely be None (insufficient price
    # history) — the caller decides that upstream and passes None through,
    # rather than these checks blindly assuming a real number always exists.
    # NOTE: comparisons against pandas/numpy values (ema200, rsi14, etc.)
    # return numpy.bool_, not Python's built-in bool. They're wrapped in
    # bool() below to normalize to a plain Python True/False — otherwise
    # downstream code that does an identity check (`is True` / `is False`,
    # as ui/single_stock.py's departures board originally did) silently
    # fails, since `numpy.bool_(False) is False` is False in Python. This
    # bug was confirmed on TCS: every technical check here came back as
    # numpy.bool_ and rendered as N/A until this normalization was added.
    checks.append(("Price above 200 EMA", None if ema200 is None else bool(current_price > ema200)))
    checks.append(("RSI in 40-60 zone", None if rsi14 is None else bool(40 <= rsi14 <= 60)))
    checks.append(("MACD bullish", None if macd_bull is None else bool(macd_bull)))

    # Volume confirmation and relative strength — already None-checked, since
    # their fetchers can genuinely return None on insufficient data.
    checks.append(("Volume confirms move (>1.2x avg)", None if volume_ratio is None else bool(volume_ratio > 1.2)))
    checks.append(("Outperforming Nifty (3mo)", None if rel_strength is None else bool(rel_strength["outperformance"] > 0)))

    # Golden cross: True/False/None comes straight from
    # data.indicators.get_golden_cross(), which already returns None when
    # there's under 200 days of price history. Also numpy.bool_ under the
    # hood (a pandas Series comparison) when not None — normalized here
    # for the same reason as the technical checks above.
    checks.append(("Golden cross (50DMA > 200DMA)", None if golden_cross is None else bool(golden_cross)))

    # ---- MANUAL-ENTRY CHECKS ----
    # These two only appear in the list at all if a manual value has been
    # entered for this stock (pledge/eps_cagr_5yr default to None). A stock
    # with no manual entry yet simply won't show these checks, rather than
    # showing a False/N/A — so an un-filled-in stock isn't punished with a
    # lower score for data you just haven't entered yet.
    if pledge is not None:
        checks.append(("Promoter pledge 0%", pledge == 0))
    if eps_cagr_5yr is not None:
        checks.append(("EPS CAGR above 12%", eps_cagr_5yr > 12))

    return checks


def score_checks(checks):
    """
    Reduces a checks list down to (passed, total). Only True/False checks
    count toward the denominator — None (not-applicable/no-data) checks are
    excluded entirely, not counted as failures. This is why a bank's score
    is out of fewer total checks than a non-bank's, and why a recent IPO
    with several genuine data gaps still gets a fair score based only on
    what could actually be evaluated.
    """
    applicable = [ok for _, ok in checks if ok is not None]
    passed = sum(1 for ok in applicable if ok)
    total = len(applicable)
    return passed, total
"""
core/verdict.py — turns a checks list into a one-line "what to actually do"
verdict. Two verdict styles live here:

  - build_verdict()          -> the standard PP Framework verdict
  - build_sampat_verdict()   -> a stricter, fundamentals-only "Sampat Mode"
                                 verdict with a tighter D/E bar and FCF
                                 weighted more heavily

Both consume the (label, True/False/None) tuples produced by
core.checks.build_checks() — see that file's docstring for the three-state
convention (True=pass, False=fail, None=not-applicable/no-data).
"""

from core.checks import score_checks


# Which check labels belong to "fundamentals + quality" vs "technicals" —
# these must match the exact label strings used in core.checks.build_checks().
# Splitting into two buckets is the core idea behind the PP verdict: a great
# company bought at the wrong technical moment is still a timing mistake, and
# a technically hot stock with weak fundamentals is a trap, not an opportunity.
FUNDAMENTAL_LABELS = {
    "PE under 25x", "ROE above 15%", "ROCE above 15%", "D/E under 0.5x",
    "Interest coverage above 5x", "PEG under 1.0x", "Revenue growth above 10%",
    "Operating margin expanding (3yr)", "FCF positive", "Piotroski F-Score >= 7",
    "Promoter pledge 0%", "EPS CAGR above 12%",
}
TECHNICAL_LABELS = {
    "Price above 200 EMA", "RSI in 40-60 zone", "MACD bullish",
    "Volume confirms move (>1.2x avg)", "Outperforming Nifty (3mo)",
    "Golden cross (50DMA > 200DMA)",
}

# Pass-rate thresholds for a green "Deploy ready" verdict.
FUND_PASS_THRESHOLD = 0.75   # fundamentals need >=75% of applicable checks passed
TECH_PASS_THRESHOLD = 0.60   # technicals need >=60% of applicable checks passed


def _bucket_pass_rate(checks, label_set):
    """
    Filters a checks list down to just the labels in label_set, then returns
    (passed, total, rate) using the same None-excluded scoring as
    score_checks() — a bucket with zero applicable checks (e.g. all-bank
    exclusions) returns a rate of 0.0 rather than dividing by zero.
    """
    bucket = [(label, ok) for label, ok in checks if label in label_set]
    passed, total = score_checks(bucket)
    rate = (passed / total) if total else 0.0
    return passed, total, rate


def build_verdict(checks, gtt, current_price):
    """
    The standard PP Framework verdict. Splits checks into fundamentals+
    quality vs technicals, requires both buckets to clear their own
    threshold for a green light:

      Deploy ready                          — fundamentals >=75% AND technicals >=60%
      Fundamentally sound, wait for entry    — fundamentals strong, technicals not confirming yet
      Technically attractive, fundamentals weak — verify quality before entry
      Avoid                                  — both buckets weak

    Returns (icon, verdict_text, color, fund_rate, tech_rate) — the last two
    are exposed so callers (e.g. a UI panel) can show the underlying split
    without recomputing it.
    """
    _, _, fund_rate = _bucket_pass_rate(checks, FUNDAMENTAL_LABELS)
    _, _, tech_rate = _bucket_pass_rate(checks, TECHNICAL_LABELS)

    fund_ok = fund_rate >= FUND_PASS_THRESHOLD
    tech_ok = tech_rate >= TECH_PASS_THRESHOLD

    if fund_ok and tech_ok:
        icon, text, color = "🟢", "Deploy ready — fundamentals and technicals both confirm", "#22c55e"
    elif fund_ok and not tech_ok:
        icon, text, color = "🟡", "Fundamentally sound, wait for entry — technicals not confirming yet", "#eab308"
    elif not fund_ok and tech_ok:
        icon, text, color = "🟡", "Technically attractive, fundamentals weak — verify quality before entry", "#eab308"
    else:
        icon, text, color = "🔴", "Avoid — both fundamentals and technicals are weak", "#ef4444"

    return icon, text, color, fund_rate, tech_rate


# ---------------------------------------------------------------------------
# SAMPAT MODE — a stricter, fundamentals-only lens
# ---------------------------------------------------------------------------
# Differences from the standard PP framework, deliberately:
#   - D/E bar tightened to <=0.1x (near-zero debt) instead of <0.5x — this
#     is why Sampat needs its own check list rather than reusing the PP
#     D/E check verbatim.
#   - Technicals are excluded entirely — Sampat Mode is a pure quality/
#     business-fundamentals filter, indifferent to short-term price action.
#   - FCF is effectively weighted more heavily in practice, since with
#     technicals removed from the denominator, one FCF fail has a bigger
#     proportional impact on the score than it does in the full PP verdict.
SAMPAT_DE_THRESHOLD = 0.1


def build_sampat_verdict(checks, fund, is_bank):
    """
    Rebuilds a stricter fundamentals-only check list from `fund` directly
    (needed because the D/E threshold differs from the PP framework's, so
    the existing "D/E under 0.5x" check from `checks` can't just be reused),
    reusing every other applicable fundamental+quality check verbatim from
    the `checks` list already computed by core.checks.build_checks().

    Returns a dict: {icon, text, color, passed, total, pct, checks} — where
    `checks` is Sampat's own (label, True/False/None) list, for rendering
    a separate Sampat departures board the same way the PP one is rendered.
    """
    sampat_checks = []

    # Carry over every fundamental+quality check AS-IS except D/E, which
    # gets its own stricter version below.
    for label, ok in checks:
        if label == "D/E under 0.5x":
            continue  # replaced below with the stricter Sampat version
        if label in FUNDAMENTAL_LABELS:
            sampat_checks.append((label, ok))

    # Stricter D/E check, built directly from fund (not from the PP checks list).
    de = fund.get("de")
    sampat_checks.append((
        f"D/E \u2264 {SAMPAT_DE_THRESHOLD}x (Sampat Strict)",
        None if de is None or is_bank else de <= SAMPAT_DE_THRESHOLD
    ))

    passed, total = score_checks(sampat_checks)
    pct = round((passed / total) * 100) if total else 0

    if total == 0:
        icon, text, color = "⚪", "Sampat: insufficient data", "#6e7284"
    elif pct >= 85:
        icon, text, color = "🟢", "Sampat Approved", "#22c55e"
    elif pct >= 70:
        icon, text, color = "🟡", "Sampat Watch", "#eab308"
    else:
        icon, text, color = "🔴", "Sampat Reject", "#ef4444"

    return {
        "icon": icon, "text": text, "color": color,
        "passed": passed, "total": total, "pct": pct,
        "checks": sampat_checks,
    }
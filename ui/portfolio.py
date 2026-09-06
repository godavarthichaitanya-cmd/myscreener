"""
ui/portfolio.py — Portfolio tab: your actual holdings, P&L, allocation,
and a PP verdict per stock (reusing the same scoring pipeline as Batch
and Compare, since the price bundle is fetched anyway to compute P&L —
the verdict is close to free once that's done).

Structure:
  Editable holdings table (symbol/quantity/avg_price) — st.data_editor,
    persisted via storage/portfolio.py (CSV-backed, same pattern as
    manual_data.py/watchlist.py/notes.py). Add/remove rows freely.
  "Refresh prices & compute" button — fetches current prices + PP verdict
    for every holding with both a quantity and an avg_price set (rows
    missing either are shown in the editor but silently excluded from
    P&L/charts). Also logs one portfolio-level snapshot (storage/
    portfolio_history.py) each time it's clicked, feeding the Value
    Trend chart below.
  Totals — invested, current value, P&L (₹ and %), plus best/worst
    holding by P&L%.
  Portfolio health — a headline value-weighted health gauge (0-100) with
    a plain-English explanation of why it landed there; a verdict
    breakdown naming which actual stocks are Deploy-ready/Watch/Avoid
    (not just counts); side-by-side Fundamentals/Technicals gauges with
    the real PP Deploy-ready thresholds (75%/60%) marked on each; and a
    concentration panel with a per-holding weight bar chart plus the
    Herfindahl Index translated into a plain-language reading
    (Well diversified / Moderately concentrated / Concentrated).
  Value Trend — invested vs current value over time, from every past
    Refresh (storage/portfolio_history.py). Only renders once at least
    two snapshots exist.
  "Log all to history" — writes every real holding's PP verdict to
    score_history.csv (storage/history.py, same log Batch/Compare/Single
    Stock write to).
  Allocation treemap (by current value, colored by P&L%) + sector donut
    + sector-level P&L bar + top gainers/losers cards, all Plotly/native,
    same dark theme as the rest of the app.
  ETFs/funds (e.g. a gold ETF) are priced and included in P&L, allocation,
    and concentration like any other holding, but are excluded from the
    PP fundamentals/technicals scoring entirely (no P/E, ROE, ROCE, etc.
    exists to check) — shown in the table with a neutral "not applicable"
    verdict instead of a real Deploy/Watch/Avoid call. Detected via
    config.sectors.is_etf() if the app defines one, else a small built-in
    fallback list/pattern for common NSE ETF tickers.
  Holdings table (with a Weight % column, P&L color-coded) + CSV export.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.checks import build_checks, score_checks
from core.verdict import build_verdict
from storage.manual_data import load_manual_data
from storage.portfolio import load_holdings_df, save_holdings_df
from storage.history import log_evaluation
from storage.portfolio_history import log_portfolio_snapshot, load_portfolio_history
from config.sectors import is_bank_or_nbfc, get_sector_icon


def _load_is_etf():
    """Prefer an is_etf() classifier from config.sectors if the app
    defines one (matching the is_bank_or_nbfc pattern already used
    below), so ETF detection stays in sync with however the rest of the
    app already classifies symbols. Falls back to a small built-in
    list/suffix match for common NSE ETF tickers if config.sectors
    doesn't have one yet — add is_etf() there later and this switches
    over automatically with no change needed here."""
    try:
        from config.sectors import is_etf as _configured_is_etf
        return _configured_is_etf
    except ImportError:
        _KNOWN_ETF_SYMBOLS = {
            "SETFGOLD", "GOLDBEES", "SILVERBEES", "NIFTYBEES", "JUNIORBEES",
            "BANKBEES", "ITBEES", "PSUBNKBEES", "LIQUIDBEES", "MON100",
            "MOM50", "ICICINIFTY", "HDFCNIFETF", "KOTAKGOLD", "AXISGOLD",
        }
        _ETF_SUFFIXES = ("BEES", "IETF")

        def _fallback_is_etf(symbol):
            s = (symbol or "").upper()
            return s in _KNOWN_ETF_SYMBOLS or s.endswith(_ETF_SUFFIXES) or "ETF" in s

        return _fallback_is_etf


_is_etf = _load_is_etf()

_OVERLAY_COLORS = ["#5a8aff", "#fb923c", "#4ade80", "#f472b6", "#c084fc", "#60a5fa", "#fbbf24", "#f87171"]
_GREEN = "#4ade80"
_RED = "#f87171"
_AMBER = "#fbbf24"
_MUTED = "#9ca3af"
_TEXT = "#c4c8d6"
_GRID = "#2d2d44"


def render_portfolio_tab():
    st.subheader("💼 Portfolio")

    st.caption("Edit quantity / avg price directly below, add rows for new holdings, or delete a row to remove one. Click Save when done.")
    holdings_df = load_holdings_df()
    edited_df = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="portfolio_editor",
        column_config={
            "symbol": st.column_config.TextColumn("Symbol", required=True),
            "quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1),
            "avg_price": st.column_config.NumberColumn("Avg Price (₹)", min_value=0.0, format="%.2f"),
        },
    )
    if st.button("💾 Save holdings"):
        save_holdings_df(edited_df)
        st.success("Saved.")
        st.rerun()

    st.write("")
    refresh_clicked = st.button("🔄 Refresh prices & compute", type="primary")
    if refresh_clicked:
        computed = _compute_holdings(edited_df)
        st.session_state["portfolio_computed"] = computed
        _maybe_log_snapshot(computed)

    computed = st.session_state.get("portfolio_computed")
    if not computed:
        st.caption("Click Refresh to fetch current prices and compute P&L.")
        return

    ok_rows = [r for r in computed if not r.get("error")]
    error_rows = [r for r in computed if r.get("error")]
    skipped = [r for r in computed if r.get("skipped")]

    for r in error_rows:
        st.error(f"{r['symbol']}: {r['error']}")
    if skipped:
        st.caption(f"Skipped from P&L (missing quantity or avg price): {', '.join(r['symbol'] for r in skipped)}")

    real_rows = [r for r in ok_rows if not r.get("skipped")]
    if not real_rows:
        st.caption("No holdings with both quantity and avg price set yet — fill those in above and Refresh again.")
        return

    # ETFs/funds have no PP fundamentals to score (no P/E, ROE, ROCE, etc.),
    # so the health/verdict/strength sections below run on this subset only.
    # Totals, concentration, allocation, and the holdings table still use
    # real_rows (all holdings) since P&L and position sizing apply to ETFs too.
    scoreable_rows = [r for r in real_rows if not r.get("is_etf")]
    etf_rows = [r for r in real_rows if r.get("is_etf")]

    st.write("")
    _render_totals(real_rows)

    if etf_rows:
        st.caption(f"⚪ Not scored on PP fundamentals (ETF/fund): {', '.join(r['symbol'] for r in etf_rows)}")

    st.write("")
    st.markdown("##### Portfolio health")
    if scoreable_rows:
        _render_health_summary(scoreable_rows)

        st.write("")
        health_col1, health_col2 = st.columns(2)
        with health_col1:
            _render_verdict_breakdown(scoreable_rows)
        with health_col2:
            _render_strength_gauges(scoreable_rows)
    else:
        st.caption("No holdings with PP fundamentals to score yet — your holdings are all ETFs/funds.")

    st.write("")
    _render_concentration_panel(real_rows)

    history_df = load_portfolio_history()
    if len(history_df) >= 2:
        st.write("")
        st.markdown("##### Value trend")
        _render_value_trend(history_df)

    st.write("")
    if st.button("📥 Log all to history"):
        for r in real_rows:
            log_evaluation(r["symbol"], r["passed"], r["total"], r["current_price"], r["verdict_text"])
        st.toast(f"Logged {len(real_rows)} holdings to score history")

    st.write("")
    st.markdown("##### Allocation & sector mix")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        _render_allocation_treemap(real_rows)
    with chart_col2:
        _render_sector_donut(real_rows)

    st.write("")
    st.markdown("##### Where the P&L is coming from")
    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        _render_sector_pnl_bar(real_rows)
    with chart_col4:
        _render_pnl_bar_chart(real_rows)

    st.write("")
    _render_top_movers(real_rows)

    st.write("")
    st.markdown("##### Holdings")
    df = _build_table_df(real_rows)
    styled = _style_table(df)
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Export portfolio as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="portfolio_snapshot.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------
def _compute_holdings(holdings_df):
    results = []
    manual_data = load_manual_data()
    progress = st.progress(0.0, text="Refreshing...")
    rows = holdings_df.to_dict("records")

    for i, row in enumerate(rows):
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        quantity = row.get("quantity") or 0
        avg_price = row.get("avg_price")

        entry = {"symbol": symbol, "quantity": quantity, "avg_price": avg_price}

        if not quantity or avg_price is None or pd.isna(avg_price):
            entry["skipped"] = True
            results.append(entry)
            progress.progress((i + 1) / max(len(rows), 1), text=f"Skipped {symbol}")
            continue

        try:
            bundle = fetch_stock_bundle(symbol)
            current_price = bundle["current_price"]
            cost_basis = avg_price * quantity
            current_value = current_price * quantity
            pnl = current_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0

            if _is_etf(symbol):
                # ETFs/gold funds have no P/E, ROE, ROCE, etc. — the PP
                # framework has nothing to check, so skip build_checks/
                # build_verdict entirely rather than scoring a fund on
                # criteria meant for operating companies. Still priced
                # above so P&L, allocation, and concentration stay accurate.
                entry.update({
                    "current_price": current_price,
                    "cost_basis": cost_basis,
                    "current_value": current_value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "passed": None,
                    "total": None,
                    "icon": "⚪",
                    "verdict_text": "ETF — PP fundamentals not applicable",
                    "color": None,
                    "fund_rate": None,
                    "tech_rate": None,
                    "sector": "ETF / Fund",
                    "bank_flag": False,
                    "is_etf": True,
                    "error": None,
                    "skipped": False,
                })
                results.append(entry)
                progress.progress((i + 1) / max(len(rows), 1), text=f"Priced {symbol} (ETF, not scored)")
                continue

            fund = bundle["fund"]
            bank_flag = is_bank_or_nbfc(symbol)
            saved = manual_data.get(symbol, {})
            pledge = float(saved.get("pledge", 0.0))
            eps_cagr_5yr = float(saved.get("eps_cagr_5yr", 0.0))

            checks = build_checks(
                fund, bundle["interest_coverage"], bundle["current_price"], bundle["ema200"],
                bundle["rsi14"], bundle["macd_bull"], pledge=pledge, eps_cagr_5yr=eps_cagr_5yr,
                roce=bundle["roce"], margin_trend=bundle["margin_trend"],
                volume_ratio=bundle["volume_ratio"], rel_strength=bundle["rel_strength"],
                is_bank=bank_flag, piotroski=bundle["piotroski"], golden_cross=bundle["golden_cross"],
            )
            passed, total = score_checks(checks)
            icon, verdict_text, color, fund_rate, tech_rate = build_verdict(
                checks, gtt=None, current_price=bundle["current_price"]
            )

            entry.update({
                "current_price": current_price,
                "cost_basis": cost_basis,
                "current_value": current_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "passed": passed,
                "total": total,
                "icon": icon,
                "verdict_text": verdict_text,
                "color": color,
                "fund_rate": fund_rate,
                "tech_rate": tech_rate,
                "sector": fund.get("sector"),
                "bank_flag": bank_flag,
                "is_etf": False,
                "error": None,
                "skipped": False,
            })
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:150]}"

        results.append(entry)
        progress.progress((i + 1) / max(len(rows), 1), text=f"Refreshed {symbol}")

    progress.empty()
    return results


def _maybe_log_snapshot(computed):
    """Log one portfolio-level snapshot per Refresh click, so the Value
    Trend chart accumulates real history rather than one point per
    Streamlit rerun."""
    real_rows = [r for r in computed if not r.get("error") and not r.get("skipped")]
    if not real_rows:
        return
    total_invested = sum(r["cost_basis"] for r in real_rows)
    total_current = sum(r["current_value"] for r in real_rows)
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
    log_portfolio_snapshot(total_invested, total_current, total_pnl, total_pnl_pct, len(real_rows))


# ---------------------------------------------------------------------------
# Rendering — totals / health
# ---------------------------------------------------------------------------
def _render_totals(rows):
    total_invested = sum(r["cost_basis"] for r in rows)
    total_current = sum(r["current_value"] for r in rows)
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Invested", f"₹{total_invested:,.0f}")
    c2.metric("Current Value", f"₹{total_current:,.0f}")
    c3.metric("P&L", f"₹{total_pnl:,.0f}", delta=f"{total_pnl_pct:+.2f}%")
    winners = sum(1 for r in rows if r["pnl"] > 0)
    c4.metric("Winners / Total", f"{winners}/{len(rows)}")

    best = max(rows, key=lambda r: r["pnl_pct"])
    worst = min(rows, key=lambda r: r["pnl_pct"])
    c5.metric("Best Holding", best["symbol"], delta=f"{best['pnl_pct']:+.1f}%")
    st.caption(f"Weakest: **{worst['symbol']}** at {worst['pnl_pct']:+.1f}%")


def _bucket_verdict(row):
    """Buckets a holding into Deploy-ready / Watch / Avoid using the same
    `icon` field the holdings table already renders per-row (a 🟢/🟡/🔴
    marker) — not the separate `color` field, which turned out not to be
    the plain "green"/"red" string this code originally assumed, causing
    every holding to fall through to the Watch bucket regardless of its
    actual verdict. Keying off `icon` guarantees the breakdown can never
    disagree with what the table shows for the same row."""
    icon = row.get("icon") or ""
    if "🟢" in icon:
        return "Deploy-ready"
    if "🔴" in icon:
        return "Avoid"
    if "🟡" in icon:
        return "Watch"
    # Fallback only if build_verdict() ever returns an icon using a
    # different symbol set — try the color field as a last resort.
    c = (row.get("color") or "").lower()
    if c in ("green", "success"):
        return "Deploy-ready"
    if c in ("red", "danger"):
        return "Avoid"
    return "Watch"


def _normalize_rate(value):
    """build_verdict()'s fund/tech rate might come back as a 0-100
    percentage or a 0-1 fraction depending on the codebase version —
    normalize to 0-100 so the gauges and score are always on the same
    scale regardless of which convention core/verdict.py uses."""
    if value is None:
        return None
    return value * 100 if 0 <= value <= 1.5 else value


def _render_health_summary(rows):
    """One headline number for 'is my portfolio healthy', value-weighted
    so a large healthy holding counts for more than a tiny shaky one —
    plus a plain-English sentence explaining *why* it landed there,
    since a bare 0-100 score means nothing on its own.

    Holdings with no fund/tech rate (e.g. insufficient data) are
    excluded from the average entirely rather than counted as a 0 —
    a missing score is not the same as a failing score, and letting it
    count as 0 can silently crush the weighted average if a large
    holding happens to be the one missing data.
    """
    scored = [r for r in rows if _normalize_rate(r.get("fund_rate")) is not None]
    scored_value = sum(r["current_value"] for r in scored) or 1
    weighted_fund = sum(_normalize_rate(r["fund_rate"]) * r["current_value"] for r in scored) / scored_value

    tech_scored = [r for r in rows if _normalize_rate(r.get("tech_rate")) is not None]
    tech_value = sum(r["current_value"] for r in tech_scored) or 1
    weighted_tech = sum(_normalize_rate(r["tech_rate"]) * r["current_value"] for r in tech_scored) / tech_value

    unscored = [r["symbol"] for r in rows if r not in scored]

    # Fundamentals weighted higher than technicals for a "how healthy is
    # this book" score, since technicals are entry-timing signals, not
    # a judgment on the underlying businesses you already hold.
    overall_score = weighted_fund * 0.65 + weighted_tech * 0.35

    if overall_score >= 75:
        label, color = "Strong", _GREEN
    elif overall_score >= 55:
        label, color = "Moderate", _AMBER
    else:
        label, color = "Weak", _RED

    total_value = sum(r["current_value"] for r in rows) or 1
    avoid_value_pct = sum(r["current_value"] for r in rows if _bucket_verdict(r) == "Avoid") / total_value * 100

    col1, col2 = st.columns([1, 1.6])
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=overall_score,
            number=dict(suffix="/100", font=dict(color=_TEXT, size=30)),
            gauge=dict(
                axis=dict(range=[0, 100], tickfont=dict(color=_MUTED, size=9)),
                bar=dict(color=color, thickness=0.3),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                steps=[
                    dict(range=[0, 55], color="rgba(248,113,113,0.15)"),
                    dict(range=[55, 75], color="rgba(251,191,36,0.15)"),
                    dict(range=[75, 100], color="rgba(74,222,128,0.15)"),
                ],
            ),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", height=190, margin=dict(l=20, r=20, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown(f"#### {label} portfolio health")
        st.write(
            f"Value-weighted across your {len(scored)} scored holdings, fundamentals score "
            f"**{weighted_fund:.0f}%** and technicals score **{weighted_tech:.0f}%** "
            f"on the PP framework. This combines into an overall score of **{overall_score:.0f}/100**, "
            f"weighted toward fundamentals since those judge the businesses you hold, "
            f"not just today's entry timing."
        )
        if avoid_value_pct > 0:
            st.caption(f"⚠️ {avoid_value_pct:.0f}% of your scored (non-ETF) holdings' value currently sits in Avoid-rated stocks.")
        else:
            st.caption("No scored holdings currently sit in Avoid-rated stocks.")
        if unscored:
            st.caption(f"Excluded from the score (no fund/tech rate returned): {', '.join(unscored)}")

    debug_rows = [{
        "Symbol": r["symbol"],
        "Weight %": round(r["current_value"] / total_value * 100, 1),
        "Raw fund_rate": r.get("fund_rate"),
        "Raw tech_rate": r.get("tech_rate"),
        "Normalized fund %": _normalize_rate(r.get("fund_rate")),
        "Normalized tech %": _normalize_rate(r.get("tech_rate")),
    } for r in sorted(rows, key=lambda r: r["current_value"], reverse=True)]
    label = "🔍 Per-holding fund/tech breakdown" if overall_score >= 20 else "⚠️ Score looks unusually low — see per-holding breakdown"
    with st.expander(label):
        st.caption("Compare 'Raw fund_rate' and 'Raw tech_rate' for each row. If they're identical (or "
                   "very close) for every holding, build_verdict() in core/verdict.py is likely returning "
                   "the same underlying value for both — not something this tab can fix, since it only "
                   "displays whatever build_verdict() hands back.")
        st.dataframe(pd.DataFrame(debug_rows), use_container_width=True, hide_index=True)


def _render_verdict_breakdown(rows):
    """Same three buckets as before, but now names the actual stocks in
    each one instead of just a count — a count alone doesn't tell you
    what to look at next."""
    buckets = {"Deploy-ready": [], "Watch": [], "Avoid": []}
    for r in rows:
        buckets[_bucket_verdict(r)].append(r["symbol"])

    labels = list(buckets.keys())
    values = [len(buckets[k]) for k in labels]
    colors = [_GREEN, _AMBER, _RED]

    fig = go.Figure(data=[go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors),
        text=values, textposition="outside",
    )])
    fig.update_layout(
        title=dict(text="Verdict breakdown", font=dict(size=13, color=_TEXT)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=220, margin=dict(l=10, r=30, t=40, b=10),
        xaxis=dict(gridcolor=_GRID, showgrid=True, dtick=1),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        font=dict(color=_MUTED),
    )
    st.plotly_chart(fig, use_container_width=True)

    icons = {"Deploy-ready": "🟢", "Watch": "🟡", "Avoid": "🔴"}
    for label in labels:
        symbols = buckets[label]
        if symbols:
            st.caption(f"{icons[label]} **{label}** ({len(symbols)}): {', '.join(symbols)}")


def _render_strength_gauges(rows):
    """Fundamentals and Technicals as two side-by-side gauges instead of
    plain progress bars, with the actual Deploy-ready thresholds (75%
    fund / 60% tech) marked as a line on each gauge so it's clear what
    'good' looks like — not just an unlabeled percentage."""
    fund_scores = [_normalize_rate(r["fund_rate"]) for r in rows if _normalize_rate(r.get("fund_rate")) is not None]
    tech_scores = [_normalize_rate(r["tech_rate"]) for r in rows if _normalize_rate(r.get("tech_rate")) is not None]
    avg_fund = sum(fund_scores) / len(fund_scores) if fund_scores else 0
    avg_tech = sum(tech_scores) / len(tech_scores) if tech_scores else 0

    def _gauge(value, title, threshold):
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number=dict(suffix="%", font=dict(color=_TEXT, size=22)),
            title=dict(text=title, font=dict(color=_MUTED, size=12)),
            gauge=dict(
                axis=dict(range=[0, 100], tickfont=dict(color=_MUTED, size=8)),
                bar=dict(color=_GREEN if value >= threshold else _AMBER, thickness=0.3),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                threshold=dict(line=dict(color=_TEXT, width=2), thickness=0.9, value=threshold),
            ),
        ))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=170, margin=dict(l=15, r=15, t=30, b=5))
        return fig

    st.markdown("**Average strength across holdings**")
    st.caption("Simple average across your 25 holdings (each stock counts equally) — "
               "this will differ from the value-weighted score above if your larger "
               "and smaller positions score differently.")
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.plotly_chart(_gauge(avg_fund, "Fundamentals+Quality", 75), use_container_width=True)
    with gcol2:
        st.plotly_chart(_gauge(avg_tech, "Technicals", 60), use_container_width=True)
    st.caption("White line marks the Deploy-ready threshold used in the PP framework (75% fund / 60% tech).")

    scored_for_weakest = [r for r in rows if _normalize_rate(r.get("fund_rate")) is not None]
    if scored_for_weakest:
        weakest_fund = min(scored_for_weakest, key=lambda r: _normalize_rate(r["fund_rate"]))
        st.caption(f"Weakest fundamentals: **{weakest_fund['symbol']}** ({_normalize_rate(weakest_fund['fund_rate']):.0f}%)")


def _render_concentration_panel(rows):
    """Concentration shown two ways: a per-holding weight bar (so you can
    see exactly which names dominate, not just a top-1 number) and the
    Herfindahl Index translated into a plain-language reading instead of
    a raw score most people don't have a mental scale for."""
    total_value = sum(r["current_value"] for r in rows) or 1
    weighted = sorted(rows, key=lambda r: r["current_value"], reverse=True)
    weights_pct = [r["current_value"] / total_value * 100 for r in weighted]
    hhi = sum((w / 100) ** 2 for w in weights_pct) * 10000  # 0-10000, higher = more concentrated

    top_holding = weighted[0]
    top_weight_pct = weights_pct[0]
    top3_weight_pct = sum(weights_pct[:3])

    if hhi > 2500 or top_weight_pct > 25:
        reading, reading_color = "Concentrated", _RED
        note = "A handful of names dominate the P&L swing — a large move in one stock moves the whole book."
    elif hhi > 1500:
        reading, reading_color = "Moderately concentrated", _AMBER
        note = "Reasonably spread, but a few positions still carry outsized weight — worth watching."
    else:
        reading, reading_color = "Well diversified", _GREEN
        note = "No single name or small group dominates — risk is spread across holdings."

    st.markdown("**Concentration**")
    m1, m2, m3 = st.columns(3)
    m1.metric("Largest position", f"{top_holding['symbol']}", f"{top_weight_pct:.1f}% of book")
    m2.metric("Top 3 combined", f"{top3_weight_pct:.1f}%")
    m3.metric("HHI reading", reading)

    fig = go.Figure(data=[go.Bar(
        x=[r["symbol"] for r in weighted], y=weights_pct,
        marker=dict(color=[reading_color if w == max(weights_pct) else "#5a8aff" for w in weights_pct]),
        text=[f"{w:.1f}%" for w in weights_pct], textposition="outside",
    )])
    fig.add_hline(y=25, line=dict(color=_RED, width=1, dash="dot"),
                  annotation_text="25% single-name caution line", annotation_font=dict(color=_MUTED, size=10))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", color=_MUTED),
        yaxis=dict(gridcolor=_GRID, title="Weight %", color=_MUTED),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"**{reading}** (HHI {hhi:,.0f}/10,000). {note}")


def _render_value_trend(history_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history_df["timestamp"], y=history_df["total_invested"],
        name="Invested", mode="lines", line=dict(color=_MUTED, width=2, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=history_df["timestamp"], y=history_df["total_current"],
        name="Current Value", mode="lines+markers",
        line=dict(color="#5a8aff", width=2.5),
        fill="tonexty", fillcolor="rgba(90,138,255,0.12)",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=300, margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(gridcolor=_GRID, showgrid=False, color=_MUTED),
        yaxis=dict(gridcolor=_GRID, showgrid=True, color=_MUTED, title="₹"),
        legend=dict(font=dict(color=_MUTED, size=10), orientation="h", y=1.1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Logged automatically each time you click Refresh — one point per refresh, not real-time.")


# ---------------------------------------------------------------------------
# Rendering — allocation / P&L charts
# ---------------------------------------------------------------------------
def _render_allocation_treemap(rows):
    labels = [r["symbol"] for r in rows]
    values = [r["current_value"] for r in rows]
    pnl_pcts = [r["pnl_pct"] for r in rows]
    texts = [f"{r['symbol']}<br>₹{r['current_value']:,.0f}<br>{r['pnl_pct']:+.1f}%" for r in rows]

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=[""] * len(labels),
        values=values,
        text=texts,
        textinfo="text",
        marker=dict(
            colors=pnl_pcts,
            colorscale=[[0, _RED], [0.5, "#3a3a52"], [1, _GREEN]],
            cmid=0,
            line=dict(color="#0a0a12", width=2),
            colorbar=dict(title="P&L %", tickfont=dict(color=_MUTED)),
        ),
        textfont=dict(color="#f8f9fc", size=12),
    ))
    fig.update_layout(
        title=dict(text="By symbol (size = value, color = P&L%)", font=dict(size=13, color=_TEXT)),
        paper_bgcolor="rgba(0,0,0,0)", height=340, margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_sector_donut(rows):
    """Same allocation data as the treemap, grouped by sector (banks/
    NBFCs bucketed as "Bank/NBFC" via the same bank_flag used everywhere
    else in the app) instead of by symbol — a portfolio can look
    diversified symbol-by-symbol while actually being concentrated in
    one or two sectors."""
    sector_totals = {}
    for r in rows:
        label = "Bank/NBFC" if r.get("bank_flag") else (r.get("sector") or "Unknown")
        sector_totals[label] = sector_totals.get(label, 0) + r["current_value"]

    labels = list(sector_totals.keys())
    values = list(sector_totals.values())
    colors = [_OVERLAY_COLORS[i % len(_OVERLAY_COLORS)] for i in range(len(labels))]

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color="#0a0a12", width=2)),
        textfont=dict(color="#f8f9fc", size=11),
    )])
    fig.update_layout(
        title=dict(text="By sector", font=dict(size=13, color=_TEXT)),
        paper_bgcolor="rgba(0,0,0,0)", height=340, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(font=dict(color=_MUTED, size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_sector_pnl_bar(rows):
    """Weighted P&L% per sector (sum of P&L over sum of cost basis in
    that sector), not a simple average of each stock's P&L% — a big
    winner shouldn't be diluted by a tiny loser in the same bar."""
    sector_pnl = {}
    sector_cost = {}
    for r in rows:
        label = "Bank/NBFC" if r.get("bank_flag") else (r.get("sector") or "Unknown")
        sector_pnl[label] = sector_pnl.get(label, 0) + r["pnl"]
        sector_cost[label] = sector_cost.get(label, 0) + r["cost_basis"]

    sectors = list(sector_pnl.keys())
    pnl_pcts = [(sector_pnl[s] / sector_cost[s] * 100) if sector_cost[s] else 0 for s in sectors]
    order = sorted(range(len(sectors)), key=lambda i: pnl_pcts[i])
    sectors = [sectors[i] for i in order]
    pnl_pcts = [pnl_pcts[i] for i in order]
    colors = [_RED if v < 0 else _GREEN for v in pnl_pcts]

    fig = go.Figure(data=[go.Bar(
        x=pnl_pcts, y=sectors, orientation="h",
        marker=dict(color=colors),
        text=[f"{v:+.1f}%" for v in pnl_pcts], textposition="outside",
    )])
    fig.update_layout(
        title=dict(text="Sector P&L % (weighted)", font=dict(size=13, color=_TEXT)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=10, r=30, t=40, b=10),
        xaxis=dict(gridcolor=_GRID, showgrid=True, title="P&L %"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        font=dict(color=_MUTED),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_pnl_bar_chart(rows):
    sorted_rows = sorted(rows, key=lambda r: r["pnl_pct"])
    labels = [r["symbol"] for r in sorted_rows]
    values = [r["pnl_pct"] for r in sorted_rows]
    colors = [_RED if v < 0 else _GREEN for v in values]

    fig = go.Figure(data=[go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors),
        text=[f"{v:+.1f}%" for v in values], textposition="outside",
    )])
    fig.update_layout(
        title=dict(text="Per-stock P&L % (worst to best)", font=dict(size=13, color=_TEXT)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=10, r=30, t=40, b=10),
        xaxis=dict(gridcolor=_GRID, showgrid=True, title="P&L %"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        font=dict(color=_MUTED),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_top_movers(rows):
    st.markdown("##### Top movers")
    gainers = sorted(rows, key=lambda r: r["pnl_pct"], reverse=True)[:3]
    losers = sorted(rows, key=lambda r: r["pnl_pct"])[:3]

    gcol, lcol = st.columns(2)
    with gcol:
        st.caption("🟢 Top gainers")
        for r in gainers:
            st.metric(r["symbol"], f"₹{r['current_value']:,.0f}", delta=f"{r['pnl_pct']:+.1f}%")
    with lcol:
        st.caption("🔴 Top laggards")
        for r in losers:
            st.metric(r["symbol"], f"₹{r['current_value']:,.0f}", delta=f"{r['pnl_pct']:+.1f}%")


# ---------------------------------------------------------------------------
# Rendering — table
# ---------------------------------------------------------------------------
def _build_table_df(rows):
    total_value = sum(r["current_value"] for r in rows) or 1
    table_rows = []
    for r in rows:
        if r.get("is_etf"):
            icon = "🪙"
        elif r.get("bank_flag"):
            icon = "🏦"
        else:
            icon = get_sector_icon(r.get("sector"))
        table_rows.append({
            "Symbol": f"{icon} {r['symbol']}",
            "Qty": r["quantity"],
            "Avg Price": r["avg_price"],
            "CMP": r["current_price"],
            "Invested": round(r["cost_basis"], 2),
            "Current Value": round(r["current_value"], 2),
            "Weight %": round(r["current_value"] / total_value * 100, 1),
            "P&L": round(r["pnl"], 2),
            "P&L %": round(r["pnl_pct"], 2),
            "Verdict": f"{r['icon']} {r['verdict_text']}",
        })
    return pd.DataFrame(table_rows)


def _style_table(df):
    """Color-codes the P&L columns green/red so winners and losers are
    visible at a glance without reading every number."""
    def _pnl_color(val):
        if not isinstance(val, (int, float)):
            return ""
        color = _GREEN if val > 0 else (_RED if val < 0 else _MUTED)
        return f"color: {color}; font-weight: 600"

    try:
        return df.style.map(_pnl_color, subset=["P&L", "P&L %"])
    except AttributeError:
        # older pandas (<2.1) doesn't have Styler.map yet
        return df.style.applymap(_pnl_color, subset=["P&L", "P&L %"])
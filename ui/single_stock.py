"""
ui/single_stock.py — the Single Stock page, restructured for information
density: raw data (Fetch step) and evaluation results (Evaluate step) are
both organized into tabs instead of one long vertical stack, so each
screen has a single clear purpose instead of "everything, in order."

Structure:
  Header — search, ticker strip, watchlist star (one compact row)
  "Your data" — manual pledge/EPS CAGR + notes, collapsed by default
  Raw data tabs — Overview | Fundamentals | Technicals | Valuation & Quality | Chart
  Evaluate button
  Score panels — ALWAYS visible once evaluated (this is the actual answer)
  Deployment Advisor — ALWAYS visible once evaluated, if a GTT is active
  Results tabs — Checks | Category Strength | Alternatives | Export | History

No scoring or logic changed from the prior version — see core/checks.py,
core/verdict.py, core/bundle.py for that. This file is purely layout.

FIX (this pass): render_deployment_advisor() was defined but never called
anywhere in render_single_stock() — that's why nothing rendered. It needs
ev["fund_rate"]/ev["tech_rate"], which only exist post-Evaluate, so it's
called in the always-visible section right after the reject-log banner,
using get_gtt_distance() to resolve the nearest GTT level for the symbol.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.checks import build_checks, score_checks
from core.verdict import build_verdict, build_sampat_verdict
from core.graham import compute_graham_fair_value
from core.gtt import get_gtt_distance, suggest_partial_entry
from core.suggestions import get_peer_suggestions
from config.sectors import is_bank_or_nbfc, get_sector_icon
from config.stock_universe import search_universe
from config.sector_pe import get_sector_pe_benchmark
from config.check_explainers import get_explainer
from storage.manual_data import load_manual_data, save_manual_entry
from storage.history import log_evaluation, load_history
from storage.app_state import load_last_symbol, save_last_symbol
from storage.reject_log import log_rejection, get_last_rejection, days_since_rejection, has_improved
from storage.watchlist import is_watchlisted, toggle_watchlist
from storage.notes import load_note, save_note
from storage.partial_fills import log_partial_fill
from storage.portfolio import get_held_qty
from storage.gtt_levels import add_level as add_gtt_level, remove_level as remove_gtt_level, get_levels as get_stored_gtt_levels
from ui.exports import build_copy_summary, build_csv_bytes, build_pdf_bytes
from data.indicators import calculate_ema



# ---------------------------------------------------------------------
# HTML-builder helpers
# ---------------------------------------------------------------------

def _ticker_strip_html(symbol, price, sector, bank_flag):
    icon = "🏦" if bank_flag else get_sector_icon(sector)
    sector_html = f' <span class="sector-inline">{icon} {sector}</span>' if sector else (
        f' <span class="sector-inline">🏦 Bank/NBFC</span>' if bank_flag else ""
    )
    return (
        f'<div class="ticker-strip">'
        f'<div><span class="ticker-symbol">{symbol}</span>'
        f'<span class="ticker-price">₹{price}</span>{sector_html}</div>'
        f'</div>'
    )


def _score_panel_html(name, icon, verdict_text, color, passed, total, pct):
    return (
        f'<div class="score-panel">'
        f'<div class="score-panel-header">'
        f'<span class="score-panel-name">{name}</span>'
        f'<span class="score-panel-verdict" style="color:{color};">{icon} {verdict_text}</span>'
        f'</div>'
        f'<div class="score-panel-bar-track">'
        f'<div class="score-panel-bar-fill" style="width:{pct}%; background:{color};"></div>'
        f'</div>'
        f'<div class="score-panel-footer">{passed}/{total} checks passed · {pct}%</div>'
        f'</div>'
    )


def _delta_badge_html(current_pct, prev_pct):
    if prev_pct is None:
        return ""
    diff = current_pct - prev_pct
    if diff > 0:
        cls, arrow = "delta-up", "▲"
    elif diff < 0:
        cls, arrow = "delta-down", "▼"
    else:
        cls, arrow = "delta-flat", "–"
    return f'<span class="delta-badge {cls}">{arrow} {abs(diff)}% vs last check</span>'


def _completeness_badge_html(checks):
    total_listed = len(checks)
    with_data = sum(1 for _, ok in checks if ok is not None)
    return f'<span class="completeness-badge">{with_data}/{total_listed} checks had data</span>'


# ---------------------------------------------------------------------
# Bulk manual data (all symbols) — new
# ---------------------------------------------------------------------

def render_bulk_manual_data():
    """Not tied to whichever symbol is currently loaded — this operates on
    the whole manual_data.csv, so it lives at the top of the page rather
    than inside the per-symbol 'Your data' expander further down."""
    with st.expander("📥 Bulk manual data (all symbols)"):
        st.caption(
            "Export everything currently saved, or upload a CSV to update "
            "promoter pledge / EPS CAGR for many symbols in one go."
        )
        all_manual = load_manual_data()

        if all_manual:
            export_df = pd.DataFrame([
                {
                    "symbol": symbol,
                    "pledge": values.get("pledge", 0.0),
                    "eps_cagr_5yr": values.get("eps_cagr_5yr", 0.0),
                }
                for symbol, values in all_manual.items()
            ])
            st.download_button(
                "⬇️ Export current manual data",
                data=export_df.to_csv(index=False).encode("utf-8"),
                file_name="manual_data_export.csv",
                mime="text/csv",
            )
        else:
            st.caption("No manual data saved yet.")

        uploaded = st.file_uploader(
            "Upload CSV (columns: symbol, pledge, eps_cagr_5yr)",
            type="csv",
            key="bulk_manual_upload",
        )
        if uploaded is not None:
            try:
                upload_df = pd.read_csv(uploaded)
                upload_df.columns = [c.strip().lower() for c in upload_df.columns]
                required = {"symbol", "pledge", "eps_cagr_5yr"}
                if not required.issubset(set(upload_df.columns)):
                    st.error("CSV needs columns: symbol, pledge, eps_cagr_5yr")
                else:
                    st.dataframe(upload_df, use_container_width=True, hide_index=True)
                    if st.button("Apply import", key="bulk_manual_apply"):
                        count = 0
                        for _, row in upload_df.iterrows():
                            save_manual_entry(
                                str(row["symbol"]).strip().upper(),
                                float(row["pledge"]),
                                float(row["eps_cagr_5yr"]),
                            )
                            count += 1
                        st.success(f"Imported {count} symbol(s). Reopen a symbol above to see updated values.")
            except Exception as e:
                st.error(f"Could not read CSV: {type(e).__name__}: {str(e)[:150]}")


# ---------------------------------------------------------------------
# Raw-data tab renderers (Fetch step — no scoring)
# ---------------------------------------------------------------------

def render_overview_tab(d, fund):
    """A genuine 'at a glance' view — the handful of numbers that matter
    most, plus a one-line business snippet. Not exhaustive by design;
    that's what the other tabs are for."""
    oc1, oc2, oc3, oc4 = st.columns(4)
    oc1.metric("PE", fund["pe"] if fund["pe"] is not None else "N/A")
    oc2.metric("ROE %", fund["roe"] if fund["roe"] is not None else "N/A")
    oc3.metric("D/E", fund["de"] if fund["de"] is not None else "N/A")
    oc4.metric("52wk high", f"-{d['pct_below_high']}%")
    oc5, oc6, oc7, oc8 = st.columns(4)
    oc5.metric("RSI (14)", d["rsi14"] if d["rsi14"] is not None else "N/A")
    oc6.metric("MACD", "Bullish" if d["macd_bull"] else ("Bearish" if d["macd_bull"] is not None else "N/A"))
    oc7.metric("Golden Cross", "Yes" if d["golden_cross"] else ("No" if d["golden_cross"] is not None else "N/A"))
    oc8.metric("F-Score", f"{d['piotroski']['score']}/{d['piotroski']['max_score']}" if d["piotroski"] else "N/A")

    if d.get("data_warning"):
        st.markdown(f'<div class="warning-banner">{d["data_warning"]}</div>', unsafe_allow_html=True)

    if fund.get("business_summary"):
        st.write("")
        summary = fund["business_summary"]
        snippet = summary if len(summary) < 220 else summary[:220].rsplit(" ", 1)[0] + "…"
        st.caption(snippet)
        if len(summary) >= 220:
            with st.expander("Read full business summary"):
                st.write(summary)
                if fund.get("website"):
                    st.caption(fund["website"])


def render_fundamentals_tab(d, fund):
    st.markdown('<div class="cat-card profitability">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("PE", fund["pe"] if fund["pe"] is not None else "N/A")
    fc2.metric("ROE %", fund["roe"] if fund["roe"] is not None else "N/A")
    fc3.metric("ROCE %", d["roce"] if d["roce"] is not None else "N/A")
    fc4.metric("D/E", fund["de"] if fund["de"] is not None else "N/A")
    sector_benchmark = get_sector_pe_benchmark(fund.get("sector"))
    if sector_benchmark is not None and fund["pe"] is not None:
        richness = "richer than" if fund["pe"] > sector_benchmark else "cheaper than"
        st.caption(f"Sector ({fund.get('sector')}) average PE ≈ {sector_benchmark}x — trades {richness} its sector average. Approximate context only.")

    fc5, fc6, fc7, fc8 = st.columns(4)
    fc5.metric("PEG", fund["peg"] if fund["peg"] is not None else "N/A")
    fc6.metric("Revenue growth %", fund["revenue_growth_yoy"] if fund["revenue_growth_yoy"] is not None else "N/A")
    fc7.metric("Interest coverage", d["interest_coverage"] if d["interest_coverage"] is not None else "N/A")
    fcf_display = "Positive" if (fund.get("fcf") is not None and fund["fcf"] > 0) else ("Negative" if fund.get("fcf") is not None else "N/A")
    fc8.metric("FCF", fcf_display)

    fc9, fc10, fc11, fc12 = st.columns(4)
    fc9.metric("Dividend yield", f"{fund['dividend_yield']}%" if fund.get("dividend_yield") is not None else "N/A")
    fc10.metric("Insider holding", f"{fund['insider_holding_proxy']}%" if fund.get("insider_holding_proxy") is not None else "N/A")
    fc11.metric("ATR (14d)", f"₹{d['atr']} ({d['atr_pct']}%)" if d.get("atr") is not None else "N/A")

    if d["margin_trend"] is not None:
        st.caption(f"Operating margin: {d['margin_trend']['margin_3yr_ago']}% (3yr ago) → {d['margin_trend']['margin_now']}% (now), {d['margin_trend']['change_pts']:+.1f} pts")
    else:
        st.caption("Operating margin trend: N/A (needs 4yr data)")
    st.markdown('</div>', unsafe_allow_html=True)


def render_technicals_tab(d):
    st.markdown('<div class="cat-card momentum">', unsafe_allow_html=True)
    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("200 EMA", f"₹{d['ema200']}" if d["ema200"] is not None else "N/A")
    tc2.metric("RSI (14)", d["rsi14"] if d["rsi14"] is not None else "N/A")
    tc3.metric("MACD", "Bullish" if d["macd_bull"] else ("Bearish" if d["macd_bull"] is not None else "N/A"))
    tc4.metric("Golden Cross", "Yes" if d["golden_cross"] else ("No" if d["golden_cross"] is not None else "N/A"))
    tc5, tc6, tc7, tc8 = st.columns(4)
    tc5.metric("Volume ratio", f"{d['volume_ratio']}x" if d["volume_ratio"] is not None else "N/A")
    tc6.metric("vs Nifty (3mo)", f"{d['rel_strength']['outperformance']:+.1f}%" if d["rel_strength"] else "N/A")
    tc7.metric("52wk high", f"-{d['pct_below_high']}%")
    st.markdown('</div>', unsafe_allow_html=True)

    if d.get("data_warning"):
        st.markdown(f'<div class="warning-banner">{d["data_warning"]}</div>', unsafe_allow_html=True)


def render_valuation_quality_tab(d, fund, saved):
    gr1, gr2 = st.columns(2)
    with gr1:
        st.markdown('<div class="cat-card valuation">', unsafe_allow_html=True)
        st.markdown('<div class="cat-title valuation">💰 Graham Fair Value</div>', unsafe_allow_html=True)
        graham = compute_graham_fair_value(d["current_price"], fund["pe"], saved.get("eps_cagr_5yr"), d["eps_cagr_3yr_auto"])
        if graham["fair_value"] is None:
            st.caption("N/A — needs a valid PE and either a manual or auto-fetched EPS CAGR.")
        else:
            gc1, gc2, gc3 = st.columns(3)
            gc1.metric("Fair Value", f"₹{graham['fair_value']}")
            gc2.metric("Margin", f"{graham['margin_pct']:+.1f}%")
            gc3.metric("Growth used", f"{graham['growth_used']}%")
            st.caption(f"Source: {graham['growth_source']}. Conservative estimate — quality compounders often trade above this. Context only, not a pass/fail gate.")
        st.markdown('</div>', unsafe_allow_html=True)

    with gr2:
        st.markdown('<div class="cat-card balance">', unsafe_allow_html=True)
        st.markdown('<div class="cat-title balance">🎯 GTT proximity</div>', unsafe_allow_html=True)
        gtt = get_gtt_distance(d["symbol"], d["current_price"])
        if gtt is None:
            st.caption("No GTT levels set for this symbol yet — add one below.")
        else:
            st.metric(f"Nearest GTT (₹{gtt['nearest_gtt']})", f"{gtt['pct_from_gtt']:+.2f}% from current price")
            if len(gtt["all_levels"]) > 1:
                st.caption("All levels: " + ", ".join(f"₹{lvl}" for lvl in gtt["all_levels"]))

        with st.expander("⚙️ Set / manage GTT levels"):
            gc1, gc2 = st.columns([2, 1])
            with gc1:
                new_level = st.number_input(
                    "Add GTT level (₹)", min_value=0.0, step=5.0, key=f"new_gtt_{d['symbol']}"
                )
            with gc2:
                st.write("")
                if st.button("➕ Add", key=f"add_gtt_{d['symbol']}"):
                    if new_level > 0:
                        add_gtt_level(d["symbol"], new_level)
                        st.success(f"Added ₹{new_level} as a GTT level for {d['symbol']}.")
                        st.rerun()

            stored = get_stored_gtt_levels(d["symbol"])
            if stored:
                st.caption("UI-added levels (config/gtt_levels.py entries, if any, aren't editable here):")
                for lvl in stored:
                    rlc1, rlc2 = st.columns([3, 1])
                    rlc1.write(f"₹{lvl}")
                    if rlc2.button("🗑️", key=f"remove_gtt_{d['symbol']}_{lvl}"):
                        remove_gtt_level(d["symbol"], lvl)
                        st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="cat-card quality">', unsafe_allow_html=True)
    st.markdown('<div class="cat-title quality">🧪 Piotroski F-Score breakdown</div>', unsafe_allow_html=True)
    p = d["piotroski"]
    if p is None:
        st.caption("N/A — needs multi-year financial statements this stock doesn't have yet.")
    else:
        st.markdown(f"**{p['score']}/{p['max_score']}**")
        pc1, pc2 = st.columns(2)
        half = (len(p["breakdown"]) + 1) // 2
        with pc1:
            for label, ok in p["breakdown"][:half]:
                st.markdown(f"{'🟢' if ok else '🔴'} {label}")
        with pc2:
            for label, ok in p["breakdown"][half:]:
                st.markdown(f"{'🟢' if ok else '🔴'} {label}")
    st.markdown('</div>', unsafe_allow_html=True)


def render_deployment_advisor(symbol, cmp, gtt_level, fund_pct, tech_pct):
    if gtt_level is None:
        return  # nothing to suggest without an active GTT

    held_qty = get_held_qty(symbol)

    st.write("")
    st.markdown("### 💰 Deployment Advisor")
    col1, col2 = st.columns(2)
    with col1:
        budget = st.number_input(
            "Budget available (₹)",
            min_value=0, step=500, value=10000,
            key=f"budget_{symbol}",
        )
    with col2:
        target_qty = st.number_input(
            "Target quantity (V13 queue)",
            min_value=held_qty, step=1, value=max(held_qty, 1),
            key=f"target_{symbol}",
        )
    st.caption(f"Currently held: {held_qty} shares · GTT trigger: ₹{gtt_level}")

    if st.button("Suggest partial entry", key=f"suggest_{symbol}"):
        result = suggest_partial_entry(cmp, gtt_level, budget, target_qty, held_qty, fund_pct, tech_pct)

        if result["stance"] == "already_target":
            st.info(result["reason"])
            st.session_state.pop(f"advisor_result_{symbol}", None)
        else:
            st.session_state[f"advisor_result_{symbol}"] = result

    result = st.session_state.get(f"advisor_result_{symbol}")
    if result:
        gap_str = f"{result['gap_pct']:.1f}%" if result["gap_pct"] is not None else "n/a"
        st.write(f"**Gap vs GTT:** {gap_str}")
        st.write(f"**Suggested now:** {result['suggested_qty']} shares (₹{result['suggested_cost']:,.0f})")
        st.write(f"**Remaining on GTT:** {result['remaining_qty']} shares")

        if result["stance"] == "gtt_only":
            st.warning(result["reason"])
        else:
            st.success(result["reason"])

        if result["suggested_qty"] > 0 and st.button("Log this partial fill", key=f"log_{symbol}"):
            log_partial_fill(symbol, result["suggested_qty"], cmp, result["suggested_cost"])
            st.success(
                "Logged to partial_fills.csv. Add this fill to portfolio_holdings.csv "
                "(update quantity/avg_price) so held_qty reflects it next time."
            )


def render_chart_tab(d):
    df = d["price_history"]
    try:
        ema200_series = calculate_ema(df, 200)
        ema50_series = calculate_ema(df, 50)
        ema20_series = calculate_ema(df, 20)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Price", line=dict(color="#5a8aff", width=2)))
        fig.add_trace(go.Scatter(x=df.index, y=ema200_series, name="200 EMA", line=dict(color="#9ca3af", width=2.0, dash="dot")))
        fig.add_trace(go.Scatter(x=df.index, y=ema50_series, name="50 EMA", line=dict(color="#ffca33", width=1.5, dash="dot")))
        fig.add_trace(go.Scatter(x=df.index, y=ema20_series, name="20 EMA", line=dict(color="#0ca0ca", width=0.5, dash="dot")))
        fig.update_layout(
            height=380, margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="#0f0f1a", plot_bgcolor="#0f0f1a", font=dict(color="#9ca3af"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="#2d2d44", showgrid=True),
            yaxis=dict(gridcolor="#2d2d44", showgrid=True, title="Price (₹)"),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.caption("Chart unavailable for this symbol.")

    if d["fund"].get("business_summary"):
        with st.expander("📄 Full business summary"):
            st.write(d["fund"]["business_summary"])
            if d["fund"].get("website"):
                st.caption(d["fund"]["website"])


# ---------------------------------------------------------------------
# Evaluation results
# ---------------------------------------------------------------------

def render_departures_board(title, checks):
    def sort_key(item):
        _, ok = item
        if ok is None:
            return 1
        return 0 if not ok else 2

    row_html = ""
    for label, ok in sorted(checks, key=sort_key):
        if ok is None:
            cls, status = "board-na", "N/A"
        elif ok:
            cls, status = "board-pass", "PASS"
        else:
            cls, status = "board-fail", "FAIL"
        row_html += (
            f'<div class="board-row {cls}">'
            f'<span class="board-label">{label.upper()}</span>'
            f'<span class="board-dots"></span>'
            f'<span class="board-status">{status}</span>'
            f'</div>'
        )
    st.markdown(f'<div class="board-panel"><div class="board-title">{title}</div>{row_html}</div>', unsafe_allow_html=True)


def render_category_radar(checks):
    categories = {
        "Valuation": ["PE under 25x", "PEG under 1.0x"],
        "Balance Sheet": ["D/E under 0.5x", "Interest coverage above 5x", "FCF positive"],
        "Quality": ["Piotroski F-Score >= 7"],
        "Profitability": ["ROE above 15%", "ROCE above 15%", "Revenue growth above 10%", "Operating margin expanding (3yr)"],
        "Momentum": ["Price above 200 EMA", "RSI in 40-60 zone", "MACD bullish",
                     "Volume confirms move (>1.2x avg)", "Outperforming Nifty (3mo)", "Golden cross (50DMA > 200DMA)"],
    }
    check_map = {label: ok for label, ok in checks}
    labels, values = [], []
    for cat, fields in categories.items():
        relevant = [check_map.get(f) for f in fields if f in check_map]
        scored = [v for v in relevant if v is not None]
        if not scored:
            continue
        labels.append(cat)
        values.append(round((sum(1 for v in scored if v) / len(scored)) * 100))

    if not labels:
        st.caption("Not enough scored checks yet to plot category strength.")
        return

    labels_closed, values_closed = labels + [labels[0]], values + [values[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values_closed, theta=labels_closed, fill="toself",
                                   line=dict(color="#5a8aff", width=2), fillcolor="rgba(90,138,255,0.25)",
                                   marker=dict(size=6, color="#93b4ff")))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(visible=True, range=[0, 100], showticklabels=True, tickfont=dict(size=9, color="#6e7284"), gridcolor="#2d2d44"),
                   angularaxis=dict(tickfont=dict(size=12, color="#c4c8d6"), gridcolor="#2d2d44")),
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False, height=340, margin=dict(l=40, r=40, t=30, b=30),
    )
    st.plotly_chart(fig, use_container_width=False)


def _find_date_column(hist):
    for candidate in ["date", "timestamp", "checked_at", "evaluated_at", "datetime"]:
        if candidate in hist.columns:
            return candidate
    return None


def render_score_trend_chart(hist):
    """A line chart of score % over time, sitting above the raw history
    table. Falls back to a plain caption (table below still shows) if the
    history frame doesn't have a column this recognizes as a date."""
    if "score_pct" not in hist.columns:
        return
    date_col = _find_date_column(hist)
    if date_col is None:
        st.caption("Trend chart needs a date/timestamp column in score_history.csv — showing table only.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist[date_col], y=hist["score_pct"], mode="lines+markers",
        line=dict(color="#5a8aff", width=2), marker=dict(size=6, color="#93b4ff"),
    ))
    fig.update_layout(
        height=220, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#0f0f1a", plot_bgcolor="#0f0f1a", font=dict(color="#9ca3af"),
        xaxis=dict(gridcolor="#2d2d44", showgrid=True),
        yaxis=dict(gridcolor="#2d2d44", showgrid=True, range=[0, 100], title="Score %"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_single_stock():
    st.subheader("🔍 Single Stock")

    render_bulk_manual_data()

    # ---- Header: search + ticker strip + watchlist ----
    last_symbol = load_last_symbol()
    query = st.text_input("NSE symbol", placeholder="Type a symbol or company name to search...", value=last_symbol or "")
    matches = search_universe(query) if query else []

    symbol = ""
    if matches:
        match_lookup = dict(matches)
        picked_label = st.selectbox(f"{len(matches)} match(es) — pick one", [l for l, _ in matches])
        symbol = match_lookup.get(picked_label, "")
    elif query:
        st.caption("No matches in the known universe — you can still fetch it directly below if you know the exact NSE symbol.")

    with st.expander("Can't find it? Enter symbol manually"):
        manual_symbol = st.text_input("NSE symbol (manual override)", placeholder="e.g. a stock not yet in stock_universe.csv").strip().upper()
    if manual_symbol:
        symbol = manual_symbol

    fetch_clicked = st.button("Fetch", type="primary")

    if fetch_clicked and symbol:
        try:
            with st.spinner(f"Fetching {symbol}..."):
                bundle = fetch_stock_bundle(symbol)
            st.session_state["bundle"] = bundle
            st.session_state.pop("last_eval", None)
            save_last_symbol(symbol)
        except ValueError as e:
            st.error(str(e))
            return
        except Exception as e:
            st.error(f"Could not fetch data: {type(e).__name__}: {str(e)[:150]}")
            return

    if "bundle" not in st.session_state:
        st.caption("Search a symbol above and click Fetch to begin.")
        return

    d = st.session_state["bundle"]
    fund = d["fund"]
    bank_flag = is_bank_or_nbfc(d["symbol"])

    st.write("")
    hs1, hs2 = st.columns([5, 1])
    with hs1:
        st.markdown(_ticker_strip_html(d["symbol"], d["current_price"], fund.get("sector"), bank_flag), unsafe_allow_html=True)
    with hs2:
        watchlisted = is_watchlisted(d["symbol"])
        if st.button("★ Watchlisted" if watchlisted else "☆ Add", key=f"watchlist_{d['symbol']}"):
            toggle_watchlist(d["symbol"])
            st.rerun()

    # ---- Your data — consolidated, collapsed by default ----
    manual_data = load_manual_data()
    saved = manual_data.get(d["symbol"], {})
    with st.expander("🔒 Your data — manual pledge/EPS CAGR, notes"):
        mc1, mc2, mc3 = st.columns([1, 1, 1])
        pledge = mc1.number_input("Promoter pledge %", min_value=0.0, max_value=100.0, value=float(saved.get("pledge", 0.0)))
        eps_cagr = mc2.number_input("EPS CAGR % 5yr", value=float(saved.get("eps_cagr_5yr", 0.0)))
        with mc3:
            st.write("")
            if st.button("💾 Save manual data"):
                save_manual_entry(d["symbol"], pledge, eps_cagr)
                st.success("Saved.")
                st.rerun()

        note_text = st.text_area("📝 Notes", value=load_note(d["symbol"]), height=70,
                                  placeholder="Why you like/dislike this stock, what to watch for, etc.")
        if st.button("💾 Save note"):
            save_note(d["symbol"], note_text)
            st.success("Note saved.")

    # ---- Raw data tabs ----
    tab_overview, tab_fund, tab_tech, tab_val, tab_chart = st.tabs(
        ["Overview", "Fundamentals", "Technicals", "Valuation & Quality", "Chart"]
    )
    with tab_overview:
        render_overview_tab(d, fund)
    with tab_fund:
        render_fundamentals_tab(d, fund)
    with tab_tech:
        render_technicals_tab(d)
    with tab_val:
        render_valuation_quality_tab(d, fund, saved)
    with tab_chart:
        render_chart_tab(d)

    # ---- Evaluate ----
    st.write("")
    evaluate_clicked = st.button("✅ Evaluate against PP + Sampat", type="primary")

    if evaluate_clicked:
        checks = build_checks(
            fund, d["interest_coverage"], d["current_price"], d["ema200"],
            d["rsi14"], d["macd_bull"], pledge=pledge, eps_cagr_5yr=eps_cagr,
            roce=d["roce"], margin_trend=d["margin_trend"],
            volume_ratio=d["volume_ratio"], rel_strength=d["rel_strength"],
            is_bank=bank_flag, piotroski=d["piotroski"], golden_cross=d["golden_cross"],
        )
        passed, total = score_checks(checks)
        icon, verdict_text, color, fund_rate, tech_rate = build_verdict(checks, gtt=None, current_price=d["current_price"])
        sampat = build_sampat_verdict(checks, fund, bank_flag)

        prior_hist = load_history(d["symbol"])
        prev_score_pct = int(prior_hist["score_pct"].iloc[-1]) if not prior_hist.empty else None

        log_evaluation(d["symbol"], passed, total, d["current_price"], verdict_text)

        st.session_state["last_eval"] = {
            "checks": checks, "passed": passed, "total": total,
            "icon": icon, "verdict_text": verdict_text, "color": color,
            "fund_rate": fund_rate, "tech_rate": tech_rate, "sampat": sampat,
            "prev_score_pct": prev_score_pct,
        }

    if "last_eval" not in st.session_state:
        return

    ev = st.session_state["last_eval"]
    pp_pct = round((ev["passed"] / ev["total"]) * 100) if ev["total"] else 0

    # ---- Score panels — always visible, this is the actual answer ----
    st.write("")
    v1, v2 = st.columns(2)
    with v1:
        st.markdown(_score_panel_html("PP FRAMEWORK", ev["icon"], ev["verdict_text"].split(" — ")[0], ev["color"], ev["passed"], ev["total"], pp_pct), unsafe_allow_html=True)
        st.markdown(_delta_badge_html(pp_pct, ev.get("prev_score_pct")) + " " + _completeness_badge_html(ev["checks"]), unsafe_allow_html=True)
    with v2:
        st.markdown(_score_panel_html("SAMPAT MODE", ev["sampat"]["icon"], ev["sampat"]["text"], ev["sampat"]["color"], ev["sampat"]["passed"], ev["sampat"]["total"], ev["sampat"]["pct"]), unsafe_allow_html=True)

    # ---- Reject-log improvement check — shown regardless of today's verdict ----
    past_rejection = get_last_rejection(d["symbol"])
    if past_rejection:
        days_ago = days_since_rejection(d["symbol"])
        when = "today" if days_ago == 0 else f"{days_ago}d ago"
        if has_improved(d["symbol"], pp_pct, ev["verdict_text"]):
            st.markdown(f'<div class="warning-banner" style="background:rgba(74,222,128,0.1); border-color:rgba(74,222,128,0.3); color:#4ade80;">📈 Worth a second look — rejected {when} at {past_rejection["score_pct"]}%, now {pp_pct}%.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="warning-banner">🚫 Rejected {when} (score {past_rejection["score_pct"]}%) — still {pp_pct}% today, no meaningful change.</div>', unsafe_allow_html=True)

    # ---- Deployment Advisor — always visible once evaluated, if a GTT is active ----
    # (THE FIX: this call was missing entirely before — the function existed but nothing invoked it)
    gtt = get_gtt_distance(d["symbol"], d["current_price"])
    gtt_level = gtt["nearest_gtt"] if gtt else None
    render_deployment_advisor(d["symbol"], d["current_price"], gtt_level, ev["fund_rate"], ev["tech_rate"])

    # ---- Results tabs ----
    tab_checks, tab_radar, tab_alt, tab_export, tab_hist = st.tabs(
        ["Checks", "Category Strength", "Alternatives", "Export", "History"]
    )

    with tab_checks:
        b1, b2 = st.columns(2)
        with b1:
            render_departures_board("PP FRAMEWORK", ev["checks"])
        with b2:
            render_departures_board("SAMPAT MODE", ev["sampat"]["checks"])
        with st.expander("ℹ️ What do these checks mean?"):
            seen = set()
            for label, ok in ev["checks"] + ev["sampat"]["checks"]:
                if label in seen:
                    continue
                seen.add(label)
                explanation = get_explainer(label)
                if explanation:
                    st.caption(f"**{label}** — {explanation}")

    with tab_radar:
        render_category_radar(ev["checks"])

    with tab_alt:
        if not ev["verdict_text"].startswith("Avoid"):
            st.caption("Alternatives are only suggested when the PP verdict is Avoid.")
        else:
            rc1, rc2 = st.columns(2)
            with rc1:
                if st.button("🚫 Mark as rejected"):
                    log_rejection(d["symbol"], pp_pct, ev["verdict_text"])
                    st.success(f"Logged — {d['symbol']} marked rejected at {pp_pct}%.")
                    st.rerun()
            with rc2:
                find_clicked = st.button("🔎 Find peer stocks in the same sector")
            if find_clicked:
                with st.spinner("Scanning sector peers..."):
                    st.session_state["peer_suggestions"] = {"symbol": d["symbol"], "results": get_peer_suggestions(d["symbol"])}

            cached = st.session_state.get("peer_suggestions")
            if cached and cached["symbol"] == d["symbol"]:
                suggestions = cached["results"]
                if not suggestions:
                    st.caption("No sector match found, or no peer scored well enough to suggest — try adding more stocks to config/stock_universe.py.")
                else:
                    for s in suggestions:
                        cap_badge = f'<span style="font-size:10.5px; color:#93b4ff; background:rgba(90,138,255,0.12); border:1px solid rgba(90,138,255,0.3); border-radius:20px; padding:2px 9px; margin-left:8px;">{s["cap_category"]}</span>' if s.get("same_cap_tier") else ""
                        st.markdown(
                            f'<div class="cat-card momentum">'
                            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                            f'<div><b style="color:#f8f9fc; font-size:15px;">{s["symbol"]}</b>{cap_badge} '
                            f'<span style="color:#9ca3af; font-size:12.5px;">— {s["name"]}</span><br>'
                            f'<span style="color:{s["color"]}; font-size:12.5px;">{s["icon"]} {s["verdict"]}</span></div>'
                            f'<div style="text-align:right; font-size:12.5px; color:#9ca3af;">'
                            f'₹{s["current_price"]}<br>Fund {s["fund_pct"]}% · Tech {s["tech_pct"]}%</div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

    with tab_export:
        summary_text = build_copy_summary(d["symbol"], d["current_price"], ev)
        st.code(summary_text, language=None)
        st.caption("Hover the block above and click the copy icon in the top-right corner.")
        exp1, exp2 = st.columns(2)
        with exp1:
            st.download_button("⬇️ Export CSV", data=build_csv_bytes(d["symbol"], d["current_price"], ev),
                                file_name=f"{d['symbol']}_evaluation.csv", mime="text/csv")
        with exp2:
            st.download_button("⬇️ Export PDF", data=build_pdf_bytes(d["symbol"], d["current_price"], ev),
                                file_name=f"{d['symbol']}_evaluation.pdf", mime="application/pdf")

    with tab_hist:
        hist = load_history(d["symbol"])
        if hist.empty:
            st.caption("No history yet — the Evaluate click above just logged the first entry.")
        else:
            render_score_trend_chart(hist)
            st.dataframe(hist[::-1], use_container_width=True, hide_index=True)
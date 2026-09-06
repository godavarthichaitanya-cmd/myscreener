"""
ui/compare.py — Compare tab: 2 to 4 stocks, side by side.

Reuses the same core functions the same way batch.py and single_stock.py
do (fetch_stock_bundle, build_checks, score_checks, build_verdict,
build_sampat_verdict, compute_graham_fair_value, get_gtt_distance) so all
three tabs stay consistent — no separate scoring logic lives here.

Symbol entry auto-resolves to the top search_universe() match rather than
showing a "N matches — pick one" dropdown (that was the old behavior;
removed per request) — if you want a specific one of several similarly-
named matches, type more of the company name to narrow it, or type the
exact NSE symbol directly.

Picks up batch.py's "Select for Compare" checkboxes automatically: if
symbols are sitting in st.session_state["compare_selection"], they
pre-fill Symbol A / B here (that flow only ever selects 2, so C/D start
blank — fill them in manually if you want a 3- or 4-way comparison).

Layout: ticker strips -> PP + Sampat score panels, for each stock ->
a normalized price overlay chart (all stocks rebased to 100 at the start
of their fetched history) -> one metrics comparison table (a proper
table now, not a 2-column "A vs B" board, since that doesn't scale past
two) -> PP and Sampat departures boards side by side for every stock.

Compare is enabled once at least 2 of the 4 symbol fields are filled.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.checks import build_checks, score_checks
from core.verdict import build_verdict, build_sampat_verdict
from core.graham import compute_graham_fair_value
from core.gtt import get_gtt_distance
from storage.manual_data import load_manual_data
from storage.history import log_evaluation
from config.sectors import is_bank_or_nbfc, get_sector_icon
from config.stock_universe import search_universe

_OVERLAY_COLORS = ["#5a8aff", "#fb923c", "#4ade80", "#f472b6"]
_SLOTS = ["A", "B", "C", "D"]


def render_compare_tab():
    st.subheader("⚖️ Compare")

    preselected = st.session_state.get("compare_selection", [])
    defaults = {slot: (preselected[i] if len(preselected) > i else "") for i, slot in enumerate(_SLOTS)}

    cols = st.columns(4)
    symbols = []
    for col, slot in zip(cols, _SLOTS):
        with col:
            symbols.append(_symbol_picker(slot, defaults[slot]))

    filled = [s for s in symbols if s]
    compare_clicked = st.button("⚖️ Compare", type="primary", disabled=len(filled) < 2)

    if compare_clicked:
        with st.spinner(f"Fetching {', '.join(filled)}..."):
            st.session_state["compare_result"] = [_fetch_one(s) for s in filled]

    results = st.session_state.get("compare_result")
    if not results:
        st.caption("Fill in at least 2 symbols (up to 4) and hit Compare.")
        return

    errored = [r for r in results if r.get("error")]
    entries = [r for r in results if not r.get("error")]
    for r in errored:
        st.error(f"{r['symbol']}: {r['error']}")

    if len(entries) < 2:
        st.caption("Need at least 2 successfully-fetched symbols to compare.")
        return

    st.write("")
    ticker_cols = st.columns(len(entries))
    for col, entry in zip(ticker_cols, entries):
        with col:
            _render_ticker(entry)

    st.write("")
    panel_cols = st.columns(len(entries))
    for col, entry in zip(panel_cols, entries):
        with col:
            _render_score_panels(entry)

    st.write("")
    if st.button("📥 Log all to history"):
        for entry in entries:
            log_evaluation(entry["symbol"], entry["passed"], entry["total"], entry["bundle"]["current_price"], entry["verdict_text"])
        st.toast(f"Logged {len(entries)} symbols to score history")

    st.write("")
    _render_price_overlay(entries)

    st.write("")
    _render_metrics_table(entries)

    st.write("")
    board_cols = st.columns(len(entries))
    for col, entry in zip(board_cols, entries):
        with col:
            _render_departures_board(f"{entry['symbol']} — PP", entry["checks"])
            _render_departures_board(f"{entry['symbol']} — SAMPAT", entry["sampat"]["checks"])


# ---------------------------------------------------------------------------
# Symbol picker — auto-resolves to the top match, no dropdown
# ---------------------------------------------------------------------------
def _symbol_picker(label, default):
    query = st.text_input(f"Symbol {label}", value=default, key=f"cmp_query_{label}", placeholder="e.g. TCS")
    if not query:
        return ""
    matches = search_universe(query)
    if matches:
        return list(dict(matches).values())[0]
    return query.strip().upper()


# ---------------------------------------------------------------------------
# Fetch + score one symbol
# ---------------------------------------------------------------------------
def _fetch_one(symbol):
    entry = {"symbol": symbol}
    try:
        bundle = fetch_stock_bundle(symbol)
        fund = bundle["fund"]
        bank_flag = is_bank_or_nbfc(symbol)
        saved = load_manual_data().get(symbol, {})
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
        sampat = build_sampat_verdict(checks, fund, bank_flag)
        graham = compute_graham_fair_value(
            bundle["current_price"], fund["pe"], eps_cagr_5yr or None, bundle["eps_cagr_3yr_auto"]
        )
        gtt = get_gtt_distance(symbol, bundle["current_price"])
        piotroski = bundle["piotroski"]
        f_score_display = f"{piotroski['score']}/{piotroski['max_score']}" if piotroski else None

        entry.update({
            "bundle": bundle, "fund": fund, "bank_flag": bank_flag, "checks": checks,
            "passed": passed, "total": total, "icon": icon, "verdict_text": verdict_text,
            "color": color, "fund_rate": fund_rate, "tech_rate": tech_rate, "sampat": sampat,
            "graham": graham, "gtt": gtt, "f_score_display": f_score_display, "error": None,
        })
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {str(e)[:150]}"
    return entry


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _render_ticker(entry):
    fund = entry["fund"]
    bank_flag = entry["bank_flag"]
    icon = "🏦" if bank_flag else get_sector_icon(fund.get("sector"))
    sector_html = f' <span class="sector-inline">{icon} {fund.get("sector") or ("Bank/NBFC" if bank_flag else "")}</span>'
    st.markdown(
        f'<div class="ticker-strip"><div>'
        f'<span class="ticker-symbol">{entry["symbol"]}</span>'
        f'<span class="ticker-price">₹{entry["bundle"]["current_price"]}</span>{sector_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_score_panels(entry):
    pp_pct = round((entry["passed"] / entry["total"]) * 100) if entry["total"] else 0
    st.markdown(
        f'<div class="score-panel">'
        f'<div class="score-panel-header">'
        f'<span class="score-panel-name">PP FRAMEWORK</span>'
        f'<span class="score-panel-verdict" style="color:{entry["color"]};">{entry["icon"]} {entry["verdict_text"]}</span>'
        f'</div>'
        f'<div class="score-panel-bar-track"><div class="score-panel-bar-fill" style="width:{pp_pct}%; background:{entry["color"]};"></div></div>'
        f'<div class="score-panel-footer">{entry["passed"]}/{entry["total"]} checks passed · {pp_pct}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    sampat = entry["sampat"]
    st.markdown(
        f'<div class="score-panel" style="margin-top:6px;">'
        f'<div class="score-panel-header">'
        f'<span class="score-panel-name">SAMPAT MODE</span>'
        f'<span class="score-panel-verdict" style="color:{sampat["color"]};">{sampat["icon"]} {sampat["text"]}</span>'
        f'</div>'
        f'<div class="score-panel-bar-track"><div class="score-panel-bar-fill" style="width:{sampat["pct"]}%; background:{sampat["color"]};"></div></div>'
        f'<div class="score-panel-footer">{sampat["passed"]}/{sampat["total"]} checks passed · {sampat["pct"]}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_price_overlay(entries):
    """Every stock's Close price rebased to 100 at the start of the
    fetched window, so relative performance is comparable regardless of
    each stock's actual price level."""
    try:
        fig = go.Figure()
        for i, entry in enumerate(entries):
            df = entry["bundle"]["price_history"]
            norm = (df["Close"] / df["Close"].iloc[0]) * 100
            color = _OVERLAY_COLORS[i % len(_OVERLAY_COLORS)]
            fig.add_trace(go.Scatter(x=df.index, y=norm, name=entry["symbol"], line=dict(color=color, width=2)))
        fig.update_layout(
            height=340, margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="#0f0f1a", plot_bgcolor="#0f0f1a", font=dict(color="#9ca3af"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="#2d2d44", showgrid=True),
            yaxis=dict(gridcolor="#2d2d44", showgrid=True, title="Rebased to 100"),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.caption("Price overlay unavailable for one or more symbols.")


def _fmt(val, suffix=""):
    return "None" if val is None else f"{val}{suffix}"


def _macd_text(bundle):
    if bundle["macd_bull"] is None:
        return "None"
    return "Bullish" if bundle["macd_bull"] else "Bearish"


def _golden_text(bundle):
    if bundle["golden_cross"] is None:
        return "None"
    return "Yes" if bundle["golden_cross"] else "No"


def _render_metrics_table(entries):
    """A real table (Metric rows x one column per stock) rather than the
    old 2-column 'A vs B' board layout — that trick only reads cleanly for
    two stocks, not up to four."""
    def gtt_display(e):
        gtt = e["gtt"]
        return f"{gtt['pct_from_gtt']:+.2f}% (₹{gtt['nearest_gtt']})" if gtt else "No GTT set"

    metric_defs = [
        ("CMP", lambda e: f"₹{e['bundle']['current_price']}"),
        ("PE", lambda e: _fmt(e["fund"]["pe"])),
        ("ROE %", lambda e: _fmt(e["fund"]["roe"])),
        ("ROCE %", lambda e: _fmt(e["bundle"]["roce"])),
        ("D/E", lambda e: _fmt(e["fund"]["de"])),
        ("PEG", lambda e: _fmt(e["fund"]["peg"])),
        ("Div Yield %", lambda e: _fmt(e["fund"].get("dividend_yield"))),
        ("F-Score", lambda e: e["f_score_display"] or "None"),
        ("RSI", lambda e: _fmt(e["bundle"]["rsi14"])),
        ("MACD", lambda e: _macd_text(e["bundle"])),
        ("Golden Cross", lambda e: _golden_text(e["bundle"])),
        ("ATR %", lambda e: _fmt(e["bundle"].get("atr_pct"))),
        ("% below 52wk high", lambda e: _fmt(e["bundle"].get("pct_below_high"))),
        ("Graham Fair Value", lambda e: f"₹{e['graham']['fair_value']}" if e["graham"].get("fair_value") is not None else "None"),
        ("GTT proximity", gtt_display),
        ("PP Score", lambda e: f"{e['passed']}/{e['total']}"),
        ("Sampat Score", lambda e: f"{e['sampat']['passed']}/{e['sampat']['total']}"),
    ]

    rows = []
    for label, fn in metric_defs:
        row = {"Metric": label}
        for entry in entries:
            row[entry["symbol"]] = fn(entry)
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_departures_board(title, checks):
    def sort_key(item):
        _, ok = item
        return 1 if ok is None else (0 if not ok else 2)

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
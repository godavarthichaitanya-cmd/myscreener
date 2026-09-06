"""
ui/batch.py — Batch (V13 queue) tab for the rebuilt PP Screener.

Card and table surface the same breadth of data as Single Stock's
Overview/Fundamentals/Valuation tabs, condensed:
  PE, ROE%, ROCE%, D/E, PEG, Dividend yield%, F-Score, RSI, MACD, Golden
  Cross, ATR%, % below 52wk high, Nearest GTT / % from GTT, Graham Fair
  Value / Margin%, PP score (passed/total), rejection status, last-checked.

Calls the same core functions the same way single_stock.py does:
  - core/cached_bundle.py: fetch_stock_bundle_cached(symbol) — a cached
    wrapper around core/bundle.py's fetch_stock_bundle(), shared by every
    tab (see that file for why)
  - core/checks.py: build_checks(...), score_checks(checks) -> (passed, total)
  - core/verdict.py: build_verdict(checks, gtt=None, current_price=...)
    -> (icon, verdict_text, color, fund_rate, tech_rate)
    build_sampat_verdict(checks, fund, is_bank) -> dict
  - core/graham.py: compute_graham_fair_value(current_price, pe, manual_eps_cagr, auto_eps_cagr)
  - core/gtt.py: get_gtt_distance(symbol, current_price)
  - storage/manual_data.py: load_manual_data()
  - storage/history.py: log_evaluation(...), days_since_last_check(symbol)
  - storage/reject_log.py: get_last_rejection(symbol), days_since_rejection(symbol)
  - config/sectors.py: is_bank_or_nbfc(symbol), get_sector_icon(sector)
  - storage/portfolio.py: get_portfolio_symbols()
  - config/queue.py: CORE_V13_QUEUE — shared with alerts.py and signals.py
    so the three can't drift apart from each other (previously each file
    hardcoded its own identical copy of this list).

Evaluate lives inside each card (via st.container(border=True), since
Streamlit widgets can't sit inside a hand-written HTML div), plus one
"Evaluate all" button above the grid that logs every non-error result in
one go. A "View as sortable table instead" expander sits under the grid
with the same fields as columns — Streamlit's dataframe sorts natively by
clicking a header.

Symbols that errored during scan are always shown (in their own row,
unaffected by the verdict filter or sort control) rather than silently
sorting to an arbitrary position — see _split_results().
"""

import streamlit as st
import pandas as pd

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.checks import build_checks, score_checks
from core.verdict import build_verdict, build_sampat_verdict
from core.graham import compute_graham_fair_value
from core.gtt import get_gtt_distance
from storage.manual_data import load_manual_data
from storage.history import log_evaluation, days_since_last_check
from storage.reject_log import get_last_rejection, days_since_rejection
from config.sectors import is_bank_or_nbfc, get_sector_icon
from storage.portfolio import get_portfolio_symbols
from config.queue import CORE_V13_QUEUE


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------
def _build_presets():
    return {
        "Core V13 Queue": CORE_V13_QUEUE,
        "Full Portfolio": get_portfolio_symbols(),
        "Custom": [],
    }


def render_batch_tab():
    st.subheader("📋 Batch")

    presets = _build_presets()
    preset_col, filter_col, sort_col = st.columns([2, 1, 1])

    with preset_col:
        preset = st.selectbox("Queue", list(presets.keys()), key="batch_preset")

    if preset == "Custom":
        symbols = _render_custom_symbol_picker()
    else:
        symbols = presets[preset]
        if preset == "Full Portfolio" and not symbols:
            st.warning("No holdings with an avg_price set yet — add some in the Portfolio tab.")
        st.caption(f"{len(symbols)} symbols")

    with filter_col:
        verdict_filter = st.selectbox(
            "Filter",
            ["All", "Deploy ready", "Watch", "Avoid", "Previously rejected"],
            key="batch_filter",
        )
    with sort_col:
        sort_by = st.selectbox(
            "Sort by", ["Fund score", "Tech score", "Symbol", "Last checked"], key="batch_sort"
        )

    scan_clicked = st.button("🔍 Scan queue", type="primary")

    if scan_clicked:
        st.session_state["batch_results"] = _scan_symbols(symbols)

    results = st.session_state.get("batch_results", [])
    if not results:
        st.caption("Pick a queue and hit Scan to pull fresh data for every symbol below.")
        return

    error_entries, ok_entries = _split_results(results)
    ok_entries = _apply_filter(ok_entries, verdict_filter)
    ok_entries = _apply_sort(ok_entries, sort_by)

    if ok_entries:
        eval_all_clicked = st.button(
            f"✅ Evaluate all ({len(ok_entries)})", key="batch_eval_all", use_container_width=False
        )
        if eval_all_clicked:
            for entry in ok_entries:
                log_evaluation(
                    entry["symbol"], entry["passed"], entry["total"],
                    entry["bundle"]["current_price"], entry["verdict_text"],
                )
            st.toast(f"Logged {len(ok_entries)} symbols to score history")

    if error_entries:
        st.markdown(f"**⚠️ {len(error_entries)} symbol(s) failed to fetch:**")
        err_cols = st.columns(min(len(error_entries), 3))
        for col, entry in zip(err_cols, error_entries):
            with col:
                _render_card(entry)
        # Overflow beyond the first row, if more than 3 errored.
        for row_start in range(3, len(error_entries), 3):
            cols = st.columns(3)
            for col, entry in zip(cols, error_entries[row_start:row_start + 3]):
                with col:
                    _render_card(entry)
        st.write("")

    if not ok_entries:
        if not error_entries:
            st.caption("No symbols match the current filter.")
        return

    _render_grid(ok_entries)

    with st.expander("📋 View as sortable table instead", expanded=True):
        df = _build_table_df(ok_entries)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption("Click a column header to sort.")
        st.download_button(
            "⬇️ Export this scan as CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="batch_scan.csv",
            mime="text/csv",
        )

    if st.session_state.get("compare_selection"):
        selected = st.session_state["compare_selection"]
        cinfo, cbtn = st.columns([4, 1])
        with cinfo:
            st.info(f"Selected for Compare ({len(selected)}/4): {', '.join(selected)}")
        with cbtn:
            st.write("")
            if len(selected) >= 2 and st.button("⚖️ Go to Compare", key="batch_goto_compare"):
                # Can't set st.session_state["active_page"] directly here —
                # that key belongs to the st.radio widget in app.py, which
                # has already been instantiated earlier in this same run.
                # Streamlit raises if you write to a widget's key after
                # it's been created. Instead, stash the request in a plain
                # (non-widget) key; app.py consumes it and sets
                # active_page BEFORE creating the radio on the next run.
                st.session_state["nav_target"] = "Compare"
                st.rerun()


def _render_custom_symbol_picker():
    raw = st.text_input(
        "Symbols (comma-separated)",
        value=",".join(st.session_state.get("batch_custom_symbols", [])),
        placeholder="e.g. TCS, HDFCBANK, ITC",
        key="batch_custom_input",
    )
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    st.session_state["batch_custom_symbols"] = symbols
    if symbols:
        st.caption(f"{len(symbols)} symbols")
    return symbols


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def _scan_symbols(symbols):
    """Fetch + score every symbol (no logging — logging only happens when
    the user clicks Evaluate on an individual card or Evaluate all, same as
    Single Stock's Fetch (no log) vs Evaluate (logs) split)."""
    results = []
    manual_data = load_manual_data()
    progress = st.progress(0.0, text="Scanning...")

    for i, symbol in enumerate(symbols):
        entry = {"symbol": symbol}
        try:
            bundle = fetch_stock_bundle(symbol)
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
            sampat = build_sampat_verdict(checks, fund, bank_flag)

            graham = compute_graham_fair_value(
                bundle["current_price"], fund["pe"], eps_cagr_5yr or None, bundle["eps_cagr_3yr_auto"]
            )
            gtt = get_gtt_distance(symbol, bundle["current_price"])

            piotroski = bundle["piotroski"]
            f_score_display = f"{piotroski['score']}/{piotroski['max_score']}" if piotroski else None

            last_rejection = get_last_rejection(symbol)
            days_rejected = days_since_rejection(symbol) if last_rejection else None

            entry.update({
                "bundle": bundle,
                "fund": fund,
                "bank_flag": bank_flag,
                "checks": checks,
                "passed": passed,
                "total": total,
                "icon": icon,
                "verdict_text": verdict_text,
                "color": color,
                "fund_rate": fund_rate,
                "tech_rate": tech_rate,
                "sampat": sampat,
                "graham": graham,
                "gtt": gtt,
                "f_score_display": f_score_display,
                "last_rejection": last_rejection,
                "days_rejected": days_rejected,
                "last_checked_days": days_since_last_check(symbol),
                "data_note": _data_note(checks),
                "error": None,
            })
        except Exception as e:
            entry.update({"error": f"{type(e).__name__}: {str(e)[:150]}"})

        results.append(entry)
        progress.progress((i + 1) / max(len(symbols), 1), text=f"Scanned {symbol}")

    progress.empty()
    return results


def _data_note(checks):
    missing = [label for label, ok in checks if ok is None]
    if not missing:
        return None
    if len(missing) <= 3:
        return f"N/A: {', '.join(missing)}"
    return f"N/A: {len(missing)} checks missing data"


# ---------------------------------------------------------------------------
# Split / filter / sort
# ---------------------------------------------------------------------------
def _split_results(results):
    """Errored symbols are pulled out up front so they're always shown
    (they carry no fund_rate/tech_rate/last_checked_days to sort or filter
    on) rather than silently landing at an arbitrary position via a -1
    sentinel in the sort key."""
    error_entries = [r for r in results if r.get("error")]
    ok_entries = [r for r in results if not r.get("error")]
    return error_entries, ok_entries


def _apply_filter(ok_entries, verdict_filter):
    if verdict_filter == "All":
        return ok_entries
    if verdict_filter == "Previously rejected":
        return [r for r in ok_entries if r.get("last_rejection")]
    return [r for r in ok_entries if r.get("verdict_text", "").startswith(verdict_filter)]


def _apply_sort(ok_entries, sort_by):
    if sort_by == "Fund score":
        return sorted(ok_entries, key=lambda r: r["fund_rate"], reverse=True)
    if sort_by == "Tech score":
        return sorted(ok_entries, key=lambda r: r["tech_rate"], reverse=True)
    if sort_by == "Symbol":
        return sorted(ok_entries, key=lambda r: r["symbol"])
    if sort_by == "Last checked":
        # Never-checked entries (None) always sort last, regardless of how
        # many days the checked ones span — mixing "never" in as -1 would
        # otherwise put it first, which reads as "most recent."
        return sorted(
            ok_entries,
            key=lambda r: (1, 0) if r["last_checked_days"] is None else (0, r["last_checked_days"]),
        )
    return ok_entries


# ---------------------------------------------------------------------------
# Shared formatting helpers (used by both the card and the table, so the
# MACD/Golden Cross/Checked-status text can't drift between the two views)
# ---------------------------------------------------------------------------
def _fmt(val, suffix=""):
    if val is None:
        return "None"
    return f"{val}{suffix}"


def _macd_text(bundle):
    if bundle["macd_bull"] is None:
        return None
    return "Bullish" if bundle["macd_bull"] else "Bearish"


def _golden_text(bundle):
    if bundle["golden_cross"] is None:
        return None
    return "Yes" if bundle["golden_cross"] else "No"


def _checked_status(entry):
    """Returns (days, is_stale) — the shared source of truth for both the
    card's colored badge and the table's plain-text column."""
    days = entry["last_checked_days"]
    if days is None:
        return None, False
    return days, days >= 14


def _completeness(checks):
    """(with_data, total) — how many checks had a real True/False result vs
    None (genuinely missing from yfinance for that stock, e.g. ROE/FCF on a
    loss-making company). Always computed and always shown, same phrasing
    Single Stock already uses ("X/Y checks had data"), so every card shows
    this line regardless of whether anything is actually missing — cards
    with complete data and cards with gaps end up the same height instead
    of the line only appearing when something's wrong."""
    total = len(checks)
    with_data = sum(1 for _, ok in checks if ok is not None)
    return with_data, total


def _completeness_badge_html(checks):
    with_data, total = _completeness(checks)
    return f'<span class="completeness-badge">{with_data}/{total} checks had data</span>'


# ---------------------------------------------------------------------------
# Grid (cards)
# ---------------------------------------------------------------------------
def _render_grid(results):
    for row_start in range(0, len(results), 3):
        cols = st.columns(3)
        for col, entry in zip(cols, results[row_start:row_start + 3]):
            with col:
                _render_card(entry)


def _checked_line_html(entry):
    days, stale = _checked_status(entry)
    if days is None:
        return '<span style="color:#565a6e; font-size:11.5px;">Checked: Never</span>'
    if stale:
        return f'<span style="color:#fbbf24; font-size:11.5px;">⚠️ Checked: {days}d ago</span>'
    return f'<span style="color:#8b8fa3; font-size:11.5px;">Checked: {days}d ago</span>'


def _render_card(entry):
    symbol = entry["symbol"]

    # Native bordered container rather than a raw .cat-card <div> — this is
    # what lets the Evaluate button sit visually inside the card
    # (Streamlit widgets can't live inside a hand-written HTML div). See
    # ui/styles.py for the .cat-card-look CSS applied to this container.
    with st.container(border=True):
        if entry.get("error"):
            st.markdown(f'<div class="ticker-symbol">{symbol}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="warning-banner">⚠️ {entry["error"]}</div>', unsafe_allow_html=True)
            return

        fund = entry["fund"]
        bundle = entry["bundle"]
        pct = round((entry["passed"] / entry["total"]) * 100) if entry["total"] else 0
        macd_text = _macd_text(bundle) or "None"
        golden_text = _golden_text(bundle) or "None"
        graham = entry["graham"]
        graham_display = f"₹{graham['fair_value']}" if graham.get("fair_value") is not None else "None"
        sector_icon = "🏦" if entry.get("bank_flag") else get_sector_icon(fund.get("sector"))
        gtt = entry.get("gtt")
        gtt_display = f"{gtt['pct_from_gtt']:+.2f}% (₹{gtt['nearest_gtt']})" if gtt else "No GTT set"

        rejection_html = ""
        if entry["last_rejection"]:
            rejection_html = (
                f'<div style="color:#f87171; font-size:12px; margin-top:6px;">'
                f'🚫 Rejected {entry["days_rejected"]}d ago</div>'
            )

        # IMPORTANT: every line below must have zero leading whitespace.
        # st.markdown treats 4+ leading spaces as a Markdown code block —
        # a Python-indented triple-quoted string trips that and renders
        # as literal text instead of HTML.
        card_html = "".join([
            f'<div style="display:flex; justify-content:space-between; align-items:center;">',
            f'<span class="ticker-symbol" style="font-size:16px;">{sector_icon} {symbol}</span>',
            f'<span class="delta-badge delta-down" style="color:{entry["color"]}; border-color:{entry["color"]}55; background:{entry["color"]}22;">{pct}%</span>',
            f'</div>',
            f'<div style="font-size:14px; color:#c4c8d6; margin:2px 0 2px 0;">₹{bundle["current_price"]}</div>',
            f'<div style="font-size:12.5px; color:{entry["color"]}; font-weight:700; margin-bottom:8px;">{entry["verdict_text"]}</div>',
            f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:4px 10px; font-size:12.5px;">',
            f'<div style="color:#8b8fa3;">PE <span style="float:right; color:#f8f9fc;">{_fmt(fund["pe"])}</span></div>',
            f'<div style="color:#8b8fa3;">ROE% <span style="float:right; color:#f8f9fc;">{_fmt(fund["roe"])}</span></div>',
            f'<div style="color:#8b8fa3;">RSI <span style="float:right; color:#f8f9fc;">{_fmt(bundle["rsi14"])}</span></div>',
            f'<div style="color:#8b8fa3;">MACD <span style="float:right; color:#f8f9fc;">{macd_text}</span></div>',
            f'<div style="color:#8b8fa3;">F-Score <span style="float:right; color:#f8f9fc;">{entry["f_score_display"] or "None"}</span></div>',
            f'<div style="color:#8b8fa3;">Golden X <span style="float:right; color:#f8f9fc;">{golden_text}</span></div>',
            f'<div style="color:#8b8fa3; grid-column: span 2;">Graham FV <span style="float:right; color:#f8f9fc;">{graham_display}</span></div>',
            f'<div style="color:#8b8fa3; grid-column: span 2;">GTT <span style="float:right; color:#f8f9fc;">{gtt_display}</span></div>',
            f'</div>',
            rejection_html,
            f'<hr style="margin:8px 0 6px 0 !important;">',
            _checked_line_html(entry),
        ])
        st.markdown(card_html, unsafe_allow_html=True)

        # Always rendered — see _completeness() docstring for why this
        # replaced the old "only show a line when something's missing"
        # behavior (it made cards inconsistent heights and, worse, made a
        # correctly-empty result — e.g. TCS having every check available —
        # look untested rather than simply complete).
        st.markdown(_completeness_badge_html(entry["checks"]), unsafe_allow_html=True)
        if entry.get("data_note"):
            st.caption(entry["data_note"])

        # Lets you tag up to 4 symbols here; Compare reads
        # st.session_state["compare_selection"] to pre-fill its symbol
        # fields, and the "⚖️ Go to Compare" button above the grid jumps
        # straight there once 2+ are selected.
        compare_selection = st.session_state.setdefault("compare_selection", [])
        is_selected = symbol in compare_selection
        compare_disabled = (not is_selected) and len(compare_selection) >= 4
        compare_clicked = st.checkbox(
            "Select for Compare", value=is_selected, key=f"cmp_{symbol}", disabled=compare_disabled
        )
        if compare_clicked and symbol not in compare_selection:
            compare_selection.append(symbol)
        elif not compare_clicked and symbol in compare_selection:
            compare_selection.remove(symbol)

        if st.button("✅ Evaluate", key=f"eval_{symbol}", use_container_width=True):
            log_evaluation(symbol, entry["passed"], entry["total"], bundle["current_price"], entry["verdict_text"])
            st.toast(f"{symbol} logged to score history")


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
def _build_table_df(results):
    """Builds the DataFrame used for both the on-screen table and the CSV
    export, so the two can never drift out of sync with each other."""
    rows = []
    for entry in results:
        fund = entry["fund"]
        bundle = entry["bundle"]
        graham = entry["graham"]
        gtt = entry["gtt"]
        days, stale = _checked_status(entry)
        checked_display = "Never" if days is None else (f"⚠️ {days}d ago" if stale else f"{days}d ago")
        with_data, total_checks = _completeness(entry["checks"])

        rows.append({
            "Symbol": entry["symbol"],
            "Status": "✅ OK",
            "Data": f"{with_data}/{total_checks}",
            "CMP": bundle["current_price"],
            "PE": fund["pe"],
            "ROE %": fund["roe"],
            "ROCE %": bundle["roce"],
            "D/E": fund["de"],
            "PEG": fund["peg"],
            "Div Yield %": fund.get("dividend_yield"),
            "F-Score": entry["f_score_display"],
            "RSI": bundle["rsi14"],
            "MACD": _macd_text(bundle),
            "Golden X": _golden_text(bundle),
            "ATR %": bundle.get("atr_pct"),
            "% below high": bundle.get("pct_below_high"),
            "Nearest GTT": gtt["nearest_gtt"] if gtt else "No GTT set",
            "% from GTT": gtt["pct_from_gtt"] if gtt else "-",
            "Graham Fair Value": graham.get("fair_value"),
            "Graham Margin %": graham.get("margin_pct"),
            "Score": f"{entry['passed']}/{entry['total']}",
            "Last Checked": checked_display,
        })

    return pd.DataFrame(rows)
"""
ui/short_term_view.py — "Short Term View" tab: one screen combining
what used to require two separate visits (Signals + Alerts), plus
ATR-based stop-loss and position sizing on top.

Design (Sept 2026):
  - Existing Signals and Alerts tabs are left in place, untouched —
    other code may still call into their scan functions independently,
    and there's no reason to force a migration. This tab is additive:
    a new consolidated UI built on the same underlying logic.
  - Queue is a dedicated Short Term Watchlist (storage/short_term_watchlist.py),
    NOT the V13 queue — short-term candidates are a different, faster-
    changing list than long-term deploy-ready names. Core V13 Queue /
    Full Portfolio are still offered as alternate views since you may
    want a quick short-term read on an existing holding too.
  - Position sizing uses a single short-term capital pool
    (storage/short_term_capital.py), NOT per-trade capital entry —
    settings: ₹10,000 pool, 2% risk/trade, 1.5x ATR stop (edit via the
    expander below).
  - One card per symbol: bullish/bearish label (from signals logic) +
    any fired alerts (from alerts logic) + suggested stop/quantity (from
    core/position_sizing.py). A quiet stock (no fired alerts, Neutral
    label) still shows its sizing numbers, since you might already be
    holding it and just want a stop-loss reference.

Depends on core/signal_calcs.py having an `atr()` function added — see
ADD_TO_signal_calcs.py. Without it, sizing suggestions show as
"Not enough data" rather than erroring.
"""

import streamlit as st

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.signal_calcs import atr
from core.position_sizing import suggest_stop_and_size
from core.short_term_engine import evaluate_short_term
from storage.portfolio import get_portfolio_symbols
from storage.short_term_watchlist import get_watchlist, add_symbol, remove_symbol
from storage.short_term_capital import get_settings, save_settings, risk_amount
from storage.alerts_history import log_alerts, alert_scan_count
from config.sectors import get_sector_icon, is_bank_or_nbfc
from config.queue import CORE_V13_QUEUE

_LABEL_COLORS = {
    "Strong Bullish": "#4ade80",
    "Moderately Bullish": "#93c5fd",
    "Neutral": "#9ca3af",
    "Moderately Bearish": "#fb923c",
    "Strong Bearish": "#f87171",
}


def _build_presets():
    return {
        "Short Term Watchlist": get_watchlist(),
        "Core V13 Queue": CORE_V13_QUEUE,
        "Full Portfolio": get_portfolio_symbols(),
        "Custom": [],
    }


def render_short_term_view_tab():
    st.subheader("⚡ Short Term View")
    st.caption("Signals + Alerts + position sizing in one pass — for swing/short-term candidates, separate from the V13 discipline.")

    _render_settings_expander()
    _render_watchlist_manager()

    presets = _build_presets()
    preset = st.selectbox("Queue", list(presets.keys()), key="stv_preset")

    if preset == "Custom":
        raw = st.text_input("Symbols (comma-separated)", key="stv_custom_input", placeholder="e.g. TCS, HDFCBANK, ITC")
        symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    else:
        symbols = presets[preset]
        if preset == "Short Term Watchlist" and not symbols:
            st.info("Your Short Term Watchlist is empty — add symbols above.")
        if preset == "Full Portfolio" and not symbols:
            st.warning("No holdings with an avg_price set yet — add some in the Portfolio tab.")
        st.caption(f"{len(symbols)} symbols")

    scan_clicked = st.button("⚡ Scan", type="primary", disabled=not symbols)
    if scan_clicked:
        st.session_state["stv_results"] = _scan(symbols)

    results = st.session_state.get("stv_results")
    if not results:
        st.caption("Pick a queue and hit Scan.")
        return

    errored = [r for r in results if r.get("error")]
    ok = [r for r in results if not r.get("error")]
    for r in errored:
        st.error(f"{r['symbol']}: {r['error']}")

    if not ok:
        return

    cols_per_row = 2
    for row_start in range(0, len(ok), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, entry in zip(cols, ok[row_start:row_start + cols_per_row]):
            with col:
                _render_card(entry)


def _render_settings_expander():
    settings = get_settings()
    with st.expander(f"⚙️ Short-term capital settings — ₹{settings['capital']:,.0f} pool, {settings['risk_pct']}% risk/trade, {settings['atr_multiplier']}x ATR stop"):
        c1, c2, c3 = st.columns(3)
        capital = c1.number_input("Capital pool (₹)", min_value=0.0, value=float(settings["capital"]), step=1000.0, key="stv_capital_input")
        risk_pct = c2.number_input("Risk per trade (%)", min_value=0.1, max_value=100.0, value=float(settings["risk_pct"]), step=0.5, key="stv_risk_input")
        atr_mult = c3.number_input("Stop distance (x ATR)", min_value=0.5, max_value=5.0, value=float(settings["atr_multiplier"]), step=0.5, key="stv_atrmult_input")
        st.caption(f"₹{risk_amount({'capital': capital, 'risk_pct': risk_pct}):,.0f} at risk per trade at these settings.")
        if st.button("Save settings", key="stv_save_settings"):
            save_settings(capital, risk_pct, atr_mult)
            st.success("Saved.")
            st.rerun()


def _render_watchlist_manager():
    with st.expander("📋 Manage Short Term Watchlist"):
        current = get_watchlist()
        st.caption(", ".join(current) if current else "Empty")
        c1, c2 = st.columns([3, 1])
        new_symbol = c1.text_input("Add symbol", key="stv_add_symbol", label_visibility="collapsed", placeholder="e.g. TCS")
        if c2.button("Add", key="stv_add_btn") and new_symbol:
            add_symbol(new_symbol)
            st.rerun()
        if current:
            remove_choice = st.selectbox("Remove symbol", [""] + current, key="stv_remove_choice")
            if remove_choice and st.button("Remove", key="stv_remove_btn"):
                remove_symbol(remove_choice)
                st.rerun()


def _scan(symbols):
    settings = get_settings()
    results = []
    progress = st.progress(0.0, text="Scanning...")
    for i, symbol in enumerate(symbols):
        entry = {"symbol": symbol, "fired_alerts": []}
        try:
            bundle = fetch_stock_bundle(symbol)
            df = bundle["price_history"]
            fund = bundle["fund"]
            current_price = bundle["current_price"]

            # --- shared engine: votes, fired alerts, and the decision, all in one place ---
            evaluation = evaluate_short_term(df, bundle["rsi14"])
            entry["fired_alerts"] = evaluation["fired_alerts"]
            log_alerts(symbol, entry["fired_alerts"])
            entry["decision"] = evaluation["decision"]

            # --- position sizing ---
            atr_value = atr(df, period=14)
            sizing = suggest_stop_and_size(
                entry_price=current_price,
                atr=atr_value,
                capital=settings["capital"],
                risk_pct=settings["risk_pct"],
                atr_multiplier=settings["atr_multiplier"],
            )

            entry.update({
                "bank_flag": is_bank_or_nbfc(symbol),
                "sector": fund.get("sector"),
                "current_price": current_price,
                "reversal_watch": evaluation["reversal_watch"],
                "bullish_votes": evaluation["bullish_votes"],
                "bearish_votes": evaluation["bearish_votes"],
                "overall_label": evaluation["overall_label"],
                "scan_count": alert_scan_count(symbol),
                "sizing": sizing,
                "error": None,
            })
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:150]}"

        results.append(entry)
        progress.progress((i + 1) / max(len(symbols), 1), text=f"Scanned {symbol}")

    progress.empty()
    return results


def _render_card(entry):
    icon = "🏦" if entry["bank_flag"] else get_sector_icon(entry["sector"])
    decision = entry["decision"]

    with st.container(border=True):
        # --- header: symbol + price ---
        st.markdown(
            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
            f'<span class="ticker-symbol" style="font-size:15px;">{icon} {entry["symbol"]}</span>'
            f'<span style="color:#c4c8d6; font-size:12px;">₹{entry["current_price"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- the verdict, leading the card ---
        st.markdown(
            f'<div style="font-size:15px; color:{decision["color"]}; font-weight:700; margin-top:6px;">'
            f'{decision["headline"]}</div>'
            f'<div style="font-size:12.5px; color:#c4c8d6; margin-top:3px; line-height:1.4;">'
            f'{decision["reason"]}</div>',
            unsafe_allow_html=True,
        )

        # --- supporting detail, demoted below the verdict ---
        with st.expander("Why — raw signals"):
            st.markdown(
                f'<div style="font-size:12px; color:#8b8fa3;">'
                f'{entry["bullish_votes"]} bullish · {entry["bearish_votes"]} bearish vote'
                f'{"s" if entry["bullish_votes"] + entry["bearish_votes"] != 1 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if entry["fired_alerts"]:
                alert_lines = "".join(
                    f'<div style="font-size:12px; color:{"#4ade80" if a["tone"] == "bullish" else "#f87171"}; margin-top:3px;">● {a["label"]}</div>'
                    for a in entry["fired_alerts"]
                )
                st.markdown(alert_lines, unsafe_allow_html=True)
                if entry["scan_count"] > 1:
                    st.caption(f"📋 Logged in {entry['scan_count']} scans total.")
            else:
                st.caption("No alerts fired this scan.")

        # --- sizing, only meaningful once you've decided to act ---
        sizing = entry["sizing"]
        if sizing is None:
            st.caption("Not enough data for a sizing suggestion (needs 15+ days of price history).")
        else:
            cap_note = " (capped by capital pool)" if sizing["capped_by_capital"] else ""
            st.markdown(
                f'<div style="font-size:12px; color:#c4c8d6; margin-top:6px; border-top:1px solid #2a2d3a; padding-top:6px;">'
                f'If acting — Stop: <span style="color:#f8f9fc;">₹{sizing["stop_price"]}</span> '
                f'(₹{sizing["stop_distance"]} away) · '
                f'Qty: <span style="color:#f8f9fc;">{sizing["qty"]}{cap_note}</span> · '
                f'Risking ₹{sizing["risk_amount"]}'
                f'</div>',
                unsafe_allow_html=True,
            )
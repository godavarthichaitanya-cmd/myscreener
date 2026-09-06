"""
ui/alerts.py — Alerts tab: a lighter, faster pulse-check across a queue
for short-term signal changes, separate from the full 18-check PP
framework. Scans for:
  - RSI oversold (<30) / overbought (>70)
  - Fresh price-vs-200EMA crossover (within the last 3 trading days —
    not just "currently above/below", which core/checks.py's PP check
    already covers)
  - Fresh MACD line/signal crossover (within the last 3 trading days)
  - Volume spike (>=1.8x the 20-day average), tagged Buying/Selling by
    that day's candle direction

All four thresholds live in core/signal_calcs.py.

Snapshot-only, same as the old app's Alerts tab — this scans once when
you click, not a background/live monitor. Only symbols with at least one
alert firing are shown by default, so a clean scan (nothing notable)
stays quiet rather than listing every symbol as "no alerts."

Every fired alert is logged to storage/alerts_history.py, and each card
shows how many past scans have logged something for that symbol — a
plain count, not "N of last M scans" (this doesn't track how many scans
were quiet for that symbol, only how many weren't) — so a recurring
signal is distinguishable from a one-off blip without turning this into
live monitoring.

Queue presets (Core V13 Queue / Full Portfolio / Custom) now import
CORE_V13_QUEUE from config/queue.py, shared with batch.py and
signals.py, instead of each file hardcoding its own copy of that list.
"""

import streamlit as st

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.signal_calcs import rsi_zone, macd_lines, fresh_crossover, volume_spike, fresh_ema_crossover
from storage.portfolio import get_portfolio_symbols
from storage.alerts_history import log_alerts, alert_scan_count
from config.sectors import get_sector_icon, is_bank_or_nbfc
from config.queue import CORE_V13_QUEUE


def _build_presets():
    return {
        "Core V13 Queue": CORE_V13_QUEUE,
        "Full Portfolio": get_portfolio_symbols(),
        "Custom": [],
    }


def render_alerts_tab():
    st.subheader("🔔 Alerts")
    st.caption("A quick pulse-check across a queue — RSI extremes, fresh EMA200/MACD crossovers, and volume spikes. Snapshot only, not live monitoring.")

    presets = _build_presets()
    preset = st.selectbox("Queue", list(presets.keys()), key="alerts_preset")

    if preset == "Custom":
        raw = st.text_input("Symbols (comma-separated)", key="alerts_custom_input", placeholder="e.g. TCS, HDFCBANK, ITC")
        symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    else:
        symbols = presets[preset]
        if preset == "Full Portfolio" and not symbols:
            st.warning("No holdings with an avg_price set yet — add some in the Portfolio tab.")
        st.caption(f"{len(symbols)} symbols")

    scan_clicked = st.button("🔔 Scan for alerts", type="primary")
    if scan_clicked:
        st.session_state["alerts_results"] = _scan_alerts(symbols)

    results = st.session_state.get("alerts_results")
    if results is None:
        st.caption("Pick a queue and hit Scan.")
        return

    errored = [r for r in results if r.get("error")]
    fired = [r for r in results if not r.get("error") and r["alerts"]]
    quiet_count = len(results) - len(errored) - len(fired)

    for r in errored:
        st.error(f"{r['symbol']}: {r['error']}")

    if not fired:
        st.success(f"No alerts fired across {len(results) - len(errored)} symbol(s) scanned.")
        return

    st.caption(f"{len(fired)} symbol(s) with alerts · {quiet_count} quiet · {len(errored)} error(s)")

    for entry in fired:
        _render_alert_card(entry)


def _scan_alerts(symbols):
    results = []
    progress = st.progress(0.0, text="Scanning...")
    for i, symbol in enumerate(symbols):
        entry = {"symbol": symbol, "alerts": []}
        try:
            bundle = fetch_stock_bundle(symbol)
            df = bundle["price_history"]
            fund = bundle["fund"]
            entry["bank_flag"] = is_bank_or_nbfc(symbol)
            entry["sector"] = fund.get("sector")
            entry["current_price"] = bundle["current_price"]

            zone = rsi_zone(bundle["rsi14"])
            if zone in ("Oversold", "Overbought"):
                entry["alerts"].append({
                    "label": f"RSI {zone.lower()} ({bundle['rsi14']})",
                    "tone": "bullish" if zone == "Oversold" else "bearish",
                })

            ema_cross = fresh_ema_crossover(df, period=200)
            if ema_cross:
                entry["alerts"].append({
                    "label": f"Fresh {ema_cross} 200EMA crossover",
                    "tone": ema_cross,
                })

            macd_line, signal_line = macd_lines(df["Close"])
            macd_cross = fresh_crossover(macd_line, signal_line)
            if macd_cross:
                entry["alerts"].append({
                    "label": f"Fresh {macd_cross} MACD crossover",
                    "tone": macd_cross,
                })

            is_spike, ratio, direction = volume_spike(df)
            if is_spike:
                entry["alerts"].append({
                    "label": f"Volume spike {ratio}x avg — {direction}",
                    "tone": "bullish" if direction == "Buying" else "bearish",
                })

            log_alerts(symbol, entry["alerts"])
            entry["error"] = None
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:150]}"

        results.append(entry)
        progress.progress((i + 1) / max(len(symbols), 1), text=f"Scanned {symbol}")

    progress.empty()
    return results


def _render_alert_card(entry):
    icon = "🏦" if entry.get("bank_flag") else get_sector_icon(entry.get("sector"))
    scan_count = alert_scan_count(entry["symbol"])
    with st.container(border=True):
        st.markdown(
            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
            f'<span class="ticker-symbol" style="font-size:15px;">{icon} {entry["symbol"]}</span>'
            f'<span style="color:#c4c8d6; font-size:13px;">₹{entry["current_price"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        alert_lines = "".join(
            f'<div style="font-size:12.5px; color:{"#4ade80" if a["tone"] == "bullish" else "#f87171"}; margin-top:4px;">● {a["label"]}</div>'
            for a in entry["alerts"]
        )
        st.markdown(alert_lines, unsafe_allow_html=True)
        if scan_count > 1:
            st.caption(f"📋 Logged in {scan_count} scans total — recurring, not a one-off.")
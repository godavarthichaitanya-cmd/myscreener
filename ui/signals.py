"""
ui/signals.py — Signals tab: a quick technical read, single-stock or
batch mode. Not the full 18-check PP framework (that's Single
Stock/Batch/Compare) — three directional votes plus one contextual flag:
  - EMA200 trend (price above/below)
  - RSI zone (per core/signal_calcs.rsi_zone: Oversold/Overbought/Neutral)
  - MACD state (bullish/bearish, from latest MACD vs signal line)
  - Volume spike (context only — see below)

SCORING — rewritten from a bullish-only 0-3 count to a symmetric
bullish/bearish vote, because the original version had a real blind
spot: RSI<30 (Oversold) is traditionally read as a bullish reversal
setup, but scored zero points either way — a stock with weak EMA/MACD
AND an oversold RSI could land on "Bearish" despite the oversold reading
itself being a bullish signal, which is a contradiction the old framing
couldn't express. This version has each of the three indicators cast a
'bullish' / 'bearish' / 'neutral' vote:
  - EMA200: bullish if price above, bearish if below.
  - RSI: the 30-70 range is split at 50 — 50-70 votes bullish (healthy
    momentum, not yet overbought), 30-50 votes bearish (weak momentum).
    Overbought (>70) votes bearish (stretched, downside risk). Oversold
    (<30) does NOT vote either way — it's flagged separately as
    "Oversold — reversal watch", since it's genuinely ambiguous (can
    resolve either as a bounce or as continued weakness) rather than
    silently defaulting to bearish or bullish.
  - MACD: bullish if the MACD line is above its signal line, bearish if
    below.
Net score = bullish votes - bearish votes, ranging -3 to +3 in practice
(usually -2 to +2 since agreement across all three is what produces the
extremes). Net >= 2 -> Strong Bullish, net == 1 -> Moderately Bullish,
net == 0 -> Neutral, net == -1 -> Moderately Bearish, net <= -2 -> Strong
Bearish.

Volume spike is still shown as a supporting badge, not a vote — a spike
alone doesn't have an inherent direction without the candle context (see
core/signal_calcs.volume_spike).

Reuses the bundle's already-fetched price_history rather than a separate
fetch — core/bundle.py already pulls enough history for a stable 200EMA
(per your notes, the old app's Signals tab had a bug where a too-short
separate 6mo fetch made EMA200 unreliable, later corrected to 1y;
reusing the bundle here sidesteps that class of bug entirely since it's
one fetch shared by every tab, not a second one specific to Signals).

Queue presets (Core V13 Queue / Full Portfolio / Custom) now import
CORE_V13_QUEUE from config/queue.py, shared with batch.py and
alerts.py, instead of each file hardcoding its own copy of that list.
"""

import streamlit as st

from core.cached_bundle import fetch_stock_bundle_cached as fetch_stock_bundle
from core.signal_calcs import rsi_zone, macd_lines, ema_trend, volume_spike
from storage.portfolio import get_portfolio_symbols
from config.sectors import get_sector_icon, is_bank_or_nbfc
from config.stock_universe import search_universe
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
        "Core V13 Queue": CORE_V13_QUEUE,
        "Full Portfolio": get_portfolio_symbols(),
        "Custom": [],
    }


def render_signals_tab():
    st.subheader("📡 Signals")
    st.caption("A quick technical read — EMA200 trend, RSI zone, MACD state, volume — not the full PP framework.")

    mode = st.radio("Mode", ["Single stock", "Batch"], horizontal=True, key="signals_mode", label_visibility="collapsed")

    if mode == "Single stock":
        query = st.text_input("Symbol", placeholder="e.g. TCS", key="signals_single_symbol")
        symbol = ""
        if query:
            matches = search_universe(query)
            symbol = list(dict(matches).values())[0] if matches else query.strip().upper()
        scan_clicked = st.button("📡 Check signals", type="primary", disabled=not symbol)
        symbols = [symbol] if symbol else []
    else:
        presets = _build_presets()
        preset = st.selectbox("Queue", list(presets.keys()), key="signals_preset")
        if preset == "Custom":
            raw = st.text_input("Symbols (comma-separated)", key="signals_custom_input", placeholder="e.g. TCS, HDFCBANK, ITC")
            symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
        else:
            symbols = presets[preset]
            if preset == "Full Portfolio" and not symbols:
                st.warning("No holdings with an avg_price set yet — add some in the Portfolio tab.")
            st.caption(f"{len(symbols)} symbols")
        scan_clicked = st.button("📡 Check signals", type="primary")

    if scan_clicked and symbols:
        st.session_state["signals_results"] = _scan_signals(symbols)

    results = st.session_state.get("signals_results")
    if not results:
        st.caption("Pick a symbol or queue and hit Check signals.")
        return

    errored = [r for r in results if r.get("error")]
    ok = [r for r in results if not r.get("error")]
    for r in errored:
        st.error(f"{r['symbol']}: {r['error']}")

    if not ok:
        return

    if len(ok) == 1:
        _render_signal_detail(ok[0])
    else:
        cols_per_row = 3
        for row_start in range(0, len(ok), cols_per_row):
            cols = st.columns(cols_per_row)
            for col, entry in zip(cols, ok[row_start:row_start + cols_per_row]):
                with col:
                    _render_signal_card(entry)


def _label_for_net(net):
    if net >= 2:
        return "Strong Bullish"
    if net == 1:
        return "Moderately Bullish"
    if net == 0:
        return "Neutral"
    if net == -1:
        return "Moderately Bearish"
    return "Strong Bearish"


def _rsi_vote(rsi_value, zone):
    """Returns 'bullish', 'bearish', or None (no vote — covers both
    missing data and Oversold, which is a deliberate non-vote; see
    module docstring)."""
    if rsi_value is None or zone is None:
        return None
    if zone == "Oversold":
        return None
    if zone == "Overbought":
        return "bearish"
    # Neutral (30-70), split at 50.
    return "bullish" if rsi_value >= 50 else "bearish"


def _scan_signals(symbols):
    results = []
    progress = st.progress(0.0, text="Checking...")
    for i, symbol in enumerate(symbols):
        entry = {"symbol": symbol}
        try:
            bundle = fetch_stock_bundle(symbol)
            df = bundle["price_history"]
            fund = bundle["fund"]

            trend_up = ema_trend(df, period=200)
            zone = rsi_zone(bundle["rsi14"])
            rsi_value = bundle["rsi14"]

            macd_line, signal_line = macd_lines(df["Close"])
            macd_bullish = None
            if not macd_line.empty and not signal_line.empty:
                macd_bullish = bool(macd_line.iloc[-1] > signal_line.iloc[-1])

            is_spike, ratio, direction = volume_spike(df)

            votes = []
            votes.append("bullish" if trend_up else ("bearish" if trend_up is not None else None))
            votes.append(_rsi_vote(rsi_value, zone))
            votes.append("bullish" if macd_bullish else ("bearish" if macd_bullish is not None else None))

            bullish_votes = sum(1 for v in votes if v == "bullish")
            bearish_votes = sum(1 for v in votes if v == "bearish")
            net = bullish_votes - bearish_votes

            entry.update({
                "bundle": bundle,
                "sector": fund.get("sector"),
                "bank_flag": is_bank_or_nbfc(symbol),
                "trend_up": trend_up,
                "rsi_zone": zone,
                "rsi_value": rsi_value,
                "macd_bullish": macd_bullish,
                "is_spike": is_spike,
                "spike_ratio": ratio,
                "spike_direction": direction,
                "bullish_votes": bullish_votes,
                "bearish_votes": bearish_votes,
                "net": net,
                "overall_label": _label_for_net(net),
                "reversal_watch": zone == "Oversold",
                "error": None,
            })
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:150]}"

        results.append(entry)
        progress.progress((i + 1) / max(len(symbols), 1), text=f"Checked {symbol}")

    progress.empty()
    return results


def _volume_line(entry):
    if entry["is_spike"]:
        return f'{entry["spike_ratio"]}x avg — {entry["spike_direction"]}'
    return "Normal"


def _render_signal_card(entry):
    icon = "🏦" if entry["bank_flag"] else get_sector_icon(entry["sector"])
    color = _LABEL_COLORS[entry["overall_label"]]
    trend_text = "Above" if entry["trend_up"] else ("Below" if entry["trend_up"] is not None else "N/A")
    macd_text = "Bullish" if entry["macd_bullish"] else ("Bearish" if entry["macd_bullish"] is not None else "N/A")
    volume_line = _volume_line(entry)

    with st.container(border=True):
        st.markdown(
            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
            f'<span class="ticker-symbol" style="font-size:15px;">{icon} {entry["symbol"]}</span>'
            f'<span style="color:{color}; font-weight:700; font-size:12px;">{entry["overall_label"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:11px; color:#8b8fa3; margin-top:2px;">'
            f'{entry["bullish_votes"]} bullish · {entry["bearish_votes"]} bearish</div>',
            unsafe_allow_html=True,
        )
        detail_html = "".join([
            f'<div style="font-size:12.5px; color:#8b8fa3; margin-top:6px;">',
            f'200EMA: <span style="color:#f8f9fc;">{trend_text}</span><br>',
            f'RSI: <span style="color:#f8f9fc;">{entry["rsi_value"]} ({entry["rsi_zone"] or "N/A"})</span><br>',
            f'MACD: <span style="color:#f8f9fc;">{macd_text}</span><br>',
            f'Volume: <span style="color:#f8f9fc;">{volume_line}</span>',
            f'</div>',
        ])
        st.markdown(detail_html, unsafe_allow_html=True)
        if entry["reversal_watch"]:
            st.markdown(
                '<div style="font-size:11.5px; color:#fbbf24; margin-top:4px;">⚠️ Oversold — reversal watch (not scored either way)</div>',
                unsafe_allow_html=True,
            )


def _render_signal_detail(entry):
    icon = "🏦" if entry["bank_flag"] else get_sector_icon(entry["sector"])
    color = _LABEL_COLORS[entry["overall_label"]]

    st.markdown(
        f'<div class="ticker-strip"><div>'
        f'<span class="ticker-symbol">{icon} {entry["symbol"]}</span>'
        f'<span class="ticker-price">₹{entry["bundle"]["current_price"]}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        f'<div style="font-size:16px; color:{color}; font-weight:700;">'
        f'{entry["overall_label"]} — {entry["bullish_votes"]} bullish · {entry["bearish_votes"]} bearish</div>',
        unsafe_allow_html=True,
    )
    if entry["reversal_watch"]:
        st.markdown(
            '<div style="font-size:12.5px; color:#fbbf24; margin-top:4px;">⚠️ RSI is Oversold — a classic reversal-watch zone, deliberately not counted as bullish or bearish above (see the Signals tab docstring for why).</div>',
            unsafe_allow_html=True,
        )
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("200 EMA trend", "Above" if entry["trend_up"] else ("Below" if entry["trend_up"] is not None else "N/A"))
    c2.metric("RSI", entry["rsi_value"] if entry["rsi_value"] is not None else "N/A", entry["rsi_zone"] or "")
    c3.metric("MACD", "Bullish" if entry["macd_bullish"] else ("Bearish" if entry["macd_bullish"] is not None else "N/A"))
    c4.metric("Volume", _volume_line(entry))
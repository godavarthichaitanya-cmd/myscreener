"""
core/short_term_engine.py — the vote-counting + alert-detection logic
that used to live only inside ui/short_term_view.py's _scan(), pulled
out so ui/single_stock.py can compute the same short-term read for a
combined PP + short-term banner (see core/combined_signal.py) without
duplicating this logic a second time.

evaluate_short_term(df, rsi14) takes exactly what's already sitting in
a fetched bundle (bundle["price_history"], bundle["rsi14"]) — no new
fetch, no new dependency.
"""

from core.signal_calcs import rsi_zone, macd_lines, ema_trend, volume_spike, fresh_crossover, fresh_ema_crossover
from core.short_term_decision import decide_action


def _rsi_vote(rsi_value, zone):
    if rsi_value is None or zone is None:
        return None
    if zone == "Oversold":
        return None
    if zone == "Overbought":
        return "bearish"
    return "bullish" if rsi_value >= 50 else "bearish"


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


def evaluate_short_term(df, rsi14):
    """Returns a dict with everything a caller needs: raw votes, fired
    alerts, and the final decision (headline/reason/color/key from
    core/short_term_decision.py). Any field can come back None/empty if
    there isn't enough price history yet — callers should treat a None
    decision as "not enough data," not an error."""

    trend_up = ema_trend(df, period=200)
    zone = rsi_zone(rsi14)

    macd_line, signal_line = macd_lines(df["Close"])
    macd_bullish = None
    if not macd_line.empty and not signal_line.empty:
        macd_bullish = bool(macd_line.iloc[-1] > signal_line.iloc[-1])

    is_spike, ratio, direction = volume_spike(df)

    votes = [
        "bullish" if trend_up else ("bearish" if trend_up is not None else None),
        _rsi_vote(rsi14, zone),
        "bullish" if macd_bullish else ("bearish" if macd_bullish is not None else None),
    ]
    bullish_votes = sum(1 for v in votes if v == "bullish")
    bearish_votes = sum(1 for v in votes if v == "bearish")
    net = bullish_votes - bearish_votes

    fired_alerts = []
    if zone in ("Oversold", "Overbought"):
        fired_alerts.append({
            "label": f"RSI {zone.lower()} ({rsi14})",
            "tone": "bullish" if zone == "Oversold" else "bearish",
        })
    ema_cross = fresh_ema_crossover(df, period=200)
    if ema_cross:
        fired_alerts.append({"label": f"Fresh {ema_cross} 200EMA crossover", "tone": ema_cross})
    macd_cross = fresh_crossover(macd_line, signal_line)
    if macd_cross:
        fired_alerts.append({"label": f"Fresh {macd_cross} MACD crossover", "tone": macd_cross})
    if is_spike:
        fired_alerts.append({
            "label": f"Volume spike {ratio}x avg — {direction}",
            "tone": "bullish" if direction == "Buying" else "bearish",
        })

    decision = decide_action(
        net=net,
        zone=zone,
        fresh_macd_cross=macd_cross,
        fresh_ema_cross=ema_cross,
        is_spike=is_spike,
        spike_direction=direction,
    )

    return {
        "trend_up": trend_up,
        "rsi_zone": zone,
        "rsi_value": rsi14,
        "macd_bullish": macd_bullish,
        "is_spike": is_spike,
        "spike_ratio": ratio,
        "spike_direction": direction,
        "ema_cross": ema_cross,
        "macd_cross": macd_cross,
        "bullish_votes": bullish_votes,
        "bearish_votes": bearish_votes,
        "net": net,
        "overall_label": _label_for_net(net),
        "reversal_watch": zone == "Oversold",
        "fired_alerts": fired_alerts,
        "decision": decision,
    }
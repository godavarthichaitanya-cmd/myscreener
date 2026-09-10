"""
core/short_term_decision.py — turns the raw signal votes (trend/RSI/
MACD/volume) into ONE verdict with a plain-English reason, instead of
leaving the interpretation to the reader.

This is the missing layer between "here are four numbers" and "here's
what to do." Priority order matters — checked top to bottom, first
match wins:

  1. Overbought RSI takes priority over everything else, because a
     stretched reading changes what a bullish trend means (momentum
     intact but risky to chase) vs what a bearish/neutral trend means
     (likely rolling over).
  2. Oversold RSI is checked next, and specifically asks whether a
     fresh bullish MACD or EMA200 crossover has ALSO just fired — that
     combination is what separates "possible reversal starting" from
     "still falling, don't catch it."
  3. Everything else falls through to the plain vote count (net
     bullish - bearish), with volume-spike direction used as a
     conviction modifier on the two extremes.

Colors follow the same 4-way scheme as the rest of the app:
  green = lean toward acting, yellow = caution/wait, red = avoid,
  gray = no clear setup either way.
"""

VERDICT_COLORS = {
    "buy_setup": "#4ade80",
    "reversal_confirming": "#4ade80",
    "bullish_lean": "#93c5fd",
    "caution_overbought": "#fbbf24",
    "no_setup": "#9ca3af",
    "bearish_lean": "#fb923c",
    "wait_reversal": "#fbbf24",
    "avoid_selling": "#f87171",
    "avoid_downtrend": "#f87171",
    "avoid_overbought_weak": "#f87171",
}


def decide_action(net, zone, fresh_macd_cross, fresh_ema_cross, is_spike, spike_direction):
    """
    net              — bullish_votes - bearish_votes, -3..3 (from signals logic)
    zone             — 'Oversold' / 'Overbought' / 'Neutral' / None
    fresh_macd_cross — 'bullish' / 'bearish' / None (from fresh_crossover)
    fresh_ema_cross  — 'bullish' / 'bearish' / None (from fresh_ema_crossover)
    is_spike         — bool, volume spike fired
    spike_direction  — 'Buying' / 'Selling' / None

    Returns dict: key, headline, reason, color
    """

    # --- 1. Overbought takes priority ---
    if zone == "Overbought":
        if net >= 1:
            return {
                "key": "caution_overbought",
                "headline": "Caution — extended",
                "reason": "Trend and MACD are bullish, but RSI is overbought. Momentum is real, but chasing here risks buying right before a pullback. Consider waiting for a dip toward the 200EMA rather than entering at market.",
                "color": VERDICT_COLORS["caution_overbought"],
            }
        return {
            "key": "avoid_overbought_weak",
            "headline": "Avoid — overbought, trend not confirming",
            "reason": "RSI is stretched above 70 but the trend/MACD aren't backing it up. This combination often precedes a reversal down rather than further upside.",
            "color": VERDICT_COLORS["avoid_overbought_weak"],
        }

    # --- 2. Oversold: check specifically for a confirming crossover ---
    if zone == "Oversold":
        if fresh_macd_cross == "bullish" or fresh_ema_cross == "bullish":
            return {
                "key": "reversal_confirming",
                "headline": "Reversal confirming",
                "reason": "RSI is oversold AND a bullish crossover just fired — this is the specific combination that separates a possible bounce from a falling knife. Still early-stage; use a tight stop.",
                "color": VERDICT_COLORS["reversal_confirming"],
            }
        return {
            "key": "wait_reversal",
            "headline": "Wait — reversal not confirmed",
            "reason": "RSI is oversold, but trend and MACD haven't turned up yet. Entering now means betting on a bounce with no confirmation it's started. Wait for a bullish MACD or EMA200 crossover before acting.",
            "color": VERDICT_COLORS["wait_reversal"],
        }

    # --- 3. Neutral RSI: fall through to vote count, with volume as a modifier ---
    if net >= 2:
        if is_spike and spike_direction == "Buying":
            return {
                "key": "buy_setup",
                "headline": "Momentum buy setup",
                "reason": "Trend, MACD, and volume all point the same direction — the strongest alignment this scan produces. Still size to the stop-loss below, not to conviction.",
                "color": VERDICT_COLORS["buy_setup"],
            }
        return {
            "key": "bullish_lean",
            "headline": "Bullish, unconfirmed by volume",
            "reason": "Trend and MACD are aligned bullish, but there's no unusual buying volume backing the move yet. Workable, but lower conviction than a volume-confirmed setup.",
            "color": VERDICT_COLORS["bullish_lean"],
        }

    if net == 1:
        return {
            "key": "bullish_lean",
            "headline": "Mild bullish lean",
            "reason": "Only one of trend/RSI/MACD is confirming bullish — a lean, not a setup. Better as a watch-item than an entry on its own.",
            "color": VERDICT_COLORS["bullish_lean"],
        }

    if net == -1:
        return {
            "key": "bearish_lean",
            "headline": "Mild bearish lean",
            "reason": "Only one of trend/RSI/MACD is confirming bearish — not a strong enough signal to act on alone.",
            "color": VERDICT_COLORS["bearish_lean"],
        }

    if net <= -2:
        if is_spike and spike_direction == "Selling":
            return {
                "key": "avoid_selling",
                "headline": "Avoid — active selling",
                "reason": "Trend and MACD are bearish AND volume shows active selling. If you're holding this, it's a signal to reassess; not a name to enter fresh.",
                "color": VERDICT_COLORS["avoid_selling"],
            }
        return {
            "key": "avoid_downtrend",
            "headline": "Avoid — clear downtrend",
            "reason": "Trend and MACD both confirm bearish with no reversal signal (RSI isn't even oversold yet — there may be more room to fall).",
            "color": VERDICT_COLORS["avoid_downtrend"],
        }

    return {
        "key": "no_setup",
        "headline": "No clear setup",
        "reason": "Trend, RSI, and MACD are roughly balanced — nothing here to act on either direction right now.",
        "color": VERDICT_COLORS["no_setup"],
    }
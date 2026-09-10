"""
core/combined_signal.py — merges the PP Framework verdict (long-term,
fundamentals+technicals-for-entry) with the Short Term View decision
(pure momentum, no fundamentals) into a single banner for Single Stock.

Deliberately conservative about the word "BUY" — it only appears when
BOTH sides are at their strongest: PP Deploy-ready AND Short Term's
highest-conviction verdict (buy_setup / reversal_confirming). Every
other combination gets an honest, specific sentence instead of a label,
because most real combinations (good business + decent-but-unconfirmed
momentum, like Castrol's "Deploy ready" + "Bullish, unconfirmed by
volume") are genuinely in-between — calling that BUY would overstate
what the short-term side is actually saying.

pp_color is whatever build_verdict() already returns: 'green' / 'yellow'
/ 'red' (match to however verdict.py actually names them — adjust the
three comparisons below if the real values differ, e.g. if it returns
hex codes instead of names).
"""

_ST_BUY_KEYS = {"buy_setup", "reversal_confirming"}
_ST_LEAN_BULLISH_KEYS = {"bullish_lean"}
_ST_WAIT_KEYS = {"caution_overbought", "wait_reversal"}
_ST_LEAN_BEARISH_KEYS = {"bearish_lean"}
_ST_AVOID_KEYS = {"avoid_selling", "avoid_downtrend", "avoid_overbought_weak"}
_ST_NEUTRAL_KEYS = {"no_setup"}


def _st_tier(st_key):
    if st_key in _ST_BUY_KEYS:
        return "buy"
    if st_key in _ST_LEAN_BULLISH_KEYS:
        return "lean_bullish"
    if st_key in _ST_WAIT_KEYS:
        return "wait"
    if st_key in _ST_LEAN_BEARISH_KEYS:
        return "lean_bearish"
    if st_key in _ST_AVOID_KEYS:
        return "avoid"
    return "neutral"


def combine_pp_and_short_term(pp_color, st_decision):
    """
    pp_color     — 'green' / 'yellow' / 'red' from build_verdict()
    st_decision  — the dict returned by core/short_term_decision.decide_action()
                   (has 'key', 'headline', 'reason')

    Returns dict: headline, reason, color, is_buy_call (bool — True only
    for the single strongest-alignment case, useful if the UI wants to
    render that one case distinctly, e.g. a bigger banner or a badge).
    """
    st_tier = _st_tier(st_decision["key"])

    # --- The one true BUY: both sides at their strongest ---
    if pp_color == "green" and st_tier == "buy":
        return {
            "headline": "🟢🟢 BUY — both sides confirm",
            "reason": f"Fundamentals clear the Deploy-ready bar AND the short-term picture is fully confirmed ({st_decision['headline']}). This is the strongest alignment the tool produces — a quality business at a technically confirmed entry.",
            "color": "#4ade80",
            "is_buy_call": True,
        }

    # --- Green PP, but short-term isn't fully there yet ---
    if pp_color == "green" and st_tier == "lean_bullish":
        return {
            "headline": "Good business, decent timing",
            "reason": f"Fundamentals are strong (Deploy-ready), and short-term momentum is leaning positive — but not fully confirmed yet ({st_decision['reason']}). Reasonable to start a position; a volume-confirmed move would strengthen the case further.",
            "color": "#93c5fd",
            "is_buy_call": False,
        }

    if pp_color == "green" and st_tier == "wait":
        return {
            "headline": "Good business — wait on entry timing",
            "reason": f"Fundamentals are strong, but the short-term signal says wait: {st_decision['reason']}",
            "color": "#fbbf24",
            "is_buy_call": False,
        }

    if pp_color == "green" and st_tier in ("lean_bearish", "avoid"):
        return {
            "headline": "Good business, weak near-term",
            "reason": f"Fundamentals clear the bar, but the short-term picture is currently negative ({st_decision['headline']}). Worth sticking to your GTT/staggered-entry discipline rather than buying at market right now.",
            "color": "#fb923c",
            "is_buy_call": False,
        }

    if pp_color == "green" and st_tier == "neutral":
        return {
            "headline": "Good business, no timing signal either way",
            "reason": "Fundamentals are strong; short-term technicals are flat/mixed right now — no particular urgency or reason to wait from a momentum standpoint.",
            "color": "#9ca3af",
            "is_buy_call": False,
        }

    # --- Yellow PP (Watch): short-term can't upgrade a business that hasn't cleared fundamentals ---
    if pp_color == "yellow" and st_tier == "buy":
        return {
            "headline": "Short-term opportunity only — not a V13 add",
            "reason": f"Technicals look genuinely good right now ({st_decision['headline']}), but fundamentals haven't cleared the Deploy-ready bar. If you act on this, treat it as a trade with its own stop — not a long-term V13 position.",
            "color": "#93c5fd",
            "is_buy_call": False,
        }

    if pp_color == "yellow":
        return {
            "headline": "Mixed — business still Watch-stage",
            "reason": f"PP verdict is Watch (one side of fundamentals/technicals isn't confirming yet). Short-term picture: {st_decision['headline']} — {st_decision['reason']}",
            "color": "#9ca3af",
            "is_buy_call": False,
        }

    # --- Red PP (Avoid): short-term buy signal is a trade, explicitly not an investment ---
    if pp_color == "red" and st_tier == "buy":
        return {
            "headline": "Caution — technical bounce only",
            "reason": f"Fundamentals say Avoid, but the short-term technical picture is showing {st_decision['headline'].lower()}. This would be a pure momentum trade against a business the PP framework has flagged as weak — high risk, and not a candidate for V13.",
            "color": "#f87171",
            "is_buy_call": False,
        }

    return {
        "headline": "Avoid",
        "reason": f"Fundamentals say Avoid. Short-term picture: {st_decision['headline']} — {st_decision['reason']}",
        "color": "#f87171",
        "is_buy_call": False,
    }
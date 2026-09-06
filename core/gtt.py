"""
core/gtt.py — finds the nearest GTT trigger level (merged from
config.gtt_levels and storage/gtt_levels.py) below or at the current
price, and how far away it is as a percentage. Purely a display/context
helper — not a scored PP/Sampat check.

UPDATED: get_gtt_distance now merges two sources — config/gtt_levels.py
(hand-maintained code, e.g. TCS/BLS entries you've already set up) and
storage/gtt_levels.py (a CSV, editable from the UI). Neither shadows the
other; a symbol's full ladder is the union of both. Also now returns
"all_levels" so the UI can show the complete ladder, not just the nearest.
"""

from config.gtt_levels import GTT_LEVELS
from storage.gtt_levels import get_levels as get_stored_levels


def get_gtt_distance(symbol: str, current_price: float):
    """
    Returns {"nearest_gtt": float, "pct_from_gtt": float, "all_levels": list}
    for the closest GTT level to the current price (by absolute distance,
    not just levels below price — so it still shows something useful if
    price has already dropped through your lowest planned entry). Returns
    None if the symbol has no GTT levels configured or set via the UI yet.
    """
    symbol = symbol.upper()
    levels = sorted(set(list(GTT_LEVELS.get(symbol, [])) + get_stored_levels(symbol)))
    if not levels:
        return None

    nearest = min(levels, key=lambda lvl: abs(lvl - current_price))
    pct_from = round(((current_price - nearest) / nearest) * 100, 2)
    return {"nearest_gtt": nearest, "pct_from_gtt": pct_from, "all_levels": levels}


def suggest_partial_entry(cmp, gtt_level, budget, target_qty, held_qty, fund_pct, tech_pct):
    """
    Suggests a partial buy when price is above the GTT trigger but budget
    is available now and fundamentals still look reasonable.

    Returns a dict:
        gap_pct        - % CMP sits above the GTT trigger (None if no GTT set)
        suggested_qty  - shares affordable within budget at CMP, capped at remaining target
        suggested_cost - actual cost of suggested_qty at CMP
        remaining_qty  - target qty still open after this partial fill
        reason         - one-line explanation
        stance         - "partial_ok" | "gtt_only" | "already_target"
    """
    remaining_target = max(target_qty - held_qty, 0)
    if remaining_target == 0:
        return {
            "gap_pct": None,
            "suggested_qty": 0,
            "suggested_cost": 0,
            "remaining_qty": 0,
            "reason": "Target quantity already fully held.",
            "stance": "already_target",
        }

    gap_pct = ((cmp - gtt_level) / gtt_level) * 100 if gtt_level else None

    suggested_qty = int(budget // cmp) if cmp else 0
    suggested_qty = min(suggested_qty, remaining_target)
    suggested_cost = suggested_qty * cmp
    remaining_qty = remaining_target - suggested_qty

    deploy_ready = fund_pct >= 75 and tech_pct >= 60
    stretched = gap_pct is not None and gap_pct > 25

    if suggested_qty == 0:
        stance = "gtt_only"
        reason = "Budget doesn't cover even 1 share at CMP."
    elif stretched and not deploy_ready:
        stance = "gtt_only"
        reason = (
            f"CMP is {gap_pct:.1f}% above GTT and the score doesn't clear Deploy-ready "
            f"thresholds — better to leave the full remainder on the GTT rather than chase."
        )
    elif stretched and deploy_ready:
        stance = "partial_ok"
        reason = (
            f"CMP is {gap_pct:.1f}% above GTT, but fundamentals still clear Deploy-ready "
            f"thresholds (fund {fund_pct:.0f}%, tech {tech_pct:.0f}%) — a partial entry is "
            f"reasonable while the rest waits on the GTT."
        )
    else:
        gap_str = f"{gap_pct:.1f}%" if gap_pct is not None else "n/a"
        stance = "partial_ok"
        reason = f"CMP is only {gap_str} above GTT and fundamentals look fine — a partial entry is low-risk here."

    return {
        "gap_pct": gap_pct,
        "suggested_qty": suggested_qty,
        "suggested_cost": suggested_cost,
        "remaining_qty": remaining_qty,
        "reason": reason,
        "stance": stance,
    }
"""
core/diff.py — compares two evaluations' check lists and reports what
changed. Used to answer "what flipped since my last check?" without
having to eyeball two departures boards side by side.
"""


def diff_checks(prev_checks, curr_checks):
    """
    prev_checks / curr_checks: lists of (label, True/False/None) tuples,
    as produced by core.checks.build_checks().

    Returns a list of (label, prev_status, curr_status) for every label
    whose status differs between the two evaluations. A label present in
    curr_checks but absent from prev_checks (e.g. a manual EPS CAGR entry
    added for the first time) is treated as prev_status=None.
    """
    if not prev_checks:
        return []

    prev_map = dict(prev_checks)
    curr_map = dict(curr_checks)

    changes = []
    for label, curr_status in curr_map.items():
        prev_status = prev_map.get(label)
        if prev_status != curr_status:
            changes.append((label, prev_status, curr_status))
    return changes
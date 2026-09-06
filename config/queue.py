"""
config/queue.py — single shared source for queue presets used by Batch,
Alerts, and Signals. Previously each of those three files defined its own
identical _build_presets() with a hardcoded Core V13 Queue list — flagged
as a TODO since batch.py's first version and now consolidated here so the
three can't silently drift apart from each other.

"Full Portfolio" is intentionally NOT built here — it depends on
storage/portfolio.py's get_portfolio_symbols(), and keeping this module
free of that import means config/ doesn't reach into storage/. Callers
build the full preset dict themselves as:
    from config.queue import CORE_V13_QUEUE
    presets = {"Core V13 Queue": CORE_V13_QUEUE, "Full Portfolio": get_portfolio_symbols(), "Custom": []}
"""

CORE_V13_QUEUE = [
    "ADANIPOWER","ASIANPAINT","GAIL","HDFCBANK","HUDCO","INFY","IOC","IRCON","IRFC",
    "LATENTVIEW","NHPC","NTPC","ONGC","POWERGRID","RVNL","RELIANCE","SBIN","SETFGOLD",
    "SUZLON","TATACONSUM","TMCV","TMPV","TATATECH","TCS","TITAN","BLS","PIDILITIND",
    "ZYDUSLIFE","CIPLA","BHARTIARTL","ICICIBANK","ABSLAMC","ATULAUTO","ITC","NATIONALUM",
    "PARAS","TATAPOWER","SETFNIF50"
]
"""
core/cached_bundle.py — a cached wrapper around core/bundle.py's
fetch_stock_bundle(), used by every tab (Single Stock, Batch, Compare,
Portfolio, Alerts, Signals) instead of calling fetch_stock_bundle()
directly.

WHY THIS EXISTS: I flagged early on (in batch.py's original docstring)
that batch scans would feel slow if fetch_stock_bundle() wasn't already
cached, and I've never actually seen core/bundle.py to confirm either
way. Rather than guess and edit a file I haven't seen, this adds one
cache layer here that every tab goes through. If fetch_stock_bundle() is
already @st.cache_data-wrapped internally, this is a harmless redundant
cache (a cache hit here just returns immediately, no real double-fetch).
If it wasn't cached, this is what actually fixes the slowness — re-
scanning the same queue, switching tabs, or re-running Compare on the
same symbols now only re-fetches after the TTL expires, not every time.

TTL matches the 1hr pattern used elsewhere in this app (data_fetcher.py's
fundamentals cache, per your notes on the old app).
"""

import streamlit as st
from core.bundle import fetch_stock_bundle as _fetch_stock_bundle_uncached


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_bundle_cached(symbol):
    return _fetch_stock_bundle_uncached(symbol)
"""
app.py — thin entrypoint. Single Stock, Batch, Compare, Portfolio,
Alerts, Signals, and Reference are wired up so far; Mutual Funds comes
back in a later step once this core pipeline is confirmed working end
to end.

NAVIGATION NOTE: this uses st.radio (styled to look like tabs — see
ui/styles.py's "Page switcher" CSS block) instead of st.tabs. st.tabs has
no API to switch tabs from code, so it couldn't support Batch's
"⚖️ Go to Compare" button.

Streamlit forbids writing to a widget's own session_state key (here,
"active_page") after that widget has already been instantiated in the
current run. Batch's button fires *after* the radio below has already
been created earlier in the same run, so it can't set "active_page"
directly — it stashes the request in a separate plain key, "nav_target",
instead. This file consumes that key and applies it to "active_page"
right here, BEFORE the radio widget is created — which is the one place
in the whole run where that's still allowed.
"""

import streamlit as st

from ui.styles import inject_custom_css
from ui.single_stock import render_single_stock
from ui.batch import render_batch_tab
from ui.compare import render_compare_tab
from ui.portfolio import render_portfolio_tab
from ui.alerts import render_alerts_tab
from ui.signals import render_signals_tab
from ui.reference import render_reference_tab

st.set_page_config(page_title="My Screener", layout="wide", page_icon="📊")
inject_custom_css()
st.title("📊 My Screener")

PAGES = ["Single Stock", "Batch", "Compare", "Portfolio", "Alerts", "Signals", "Reference"]
if "active_page" not in st.session_state:
    st.session_state["active_page"] = "Single Stock"

# Apply any pending navigation request from Batch (or elsewhere) before the
# radio widget below is created — see NAVIGATION NOTE above.
if "nav_target" in st.session_state:
    st.session_state["active_page"] = st.session_state.pop("nav_target")

active_page = st.radio(
    "Page", PAGES, horizontal=True, key="active_page", label_visibility="collapsed"
)

if active_page == "Single Stock":
    render_single_stock()
elif active_page == "Batch":
    render_batch_tab()
elif active_page == "Compare":
    render_compare_tab()
elif active_page == "Portfolio":
    render_portfolio_tab()
elif active_page == "Alerts":
    render_alerts_tab()
elif active_page == "Signals":
    render_signals_tab()
elif active_page == "Reference":
    render_reference_tab()
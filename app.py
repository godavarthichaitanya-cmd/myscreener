"""
app.py — thin entrypoint. Single Stock, Batch, Compare, Portfolio,
Alerts, Signals, Short Term View, and Reference are wired up so far;
Mutual Funds comes back in a later step once this core pipeline is
confirmed working end to end.

NAVIGATION NOTE (updated again): st.radio styled to look like tabs was
functional but visually still read as a radio button, and the first
streamlit-option-menu pass didn't span the window width or sit flush
with the title above it. This pass: the nav bar container is full-width
with a border/rounded card so it reads as one component, each pill uses
flex-grow so items spread evenly across that full width instead of
hugging their own text, and the title above it uses tightened custom
CSS spacing instead of st.title's default margins, so title + nav read
as one aligned header block instead of two floating pieces.

Batch's "⚖️ Go to Compare" button still works via the same nav_target
handoff as before — see the manual_select block below, unchanged in
behavior from the last pass.
"""

import streamlit as st
from streamlit_option_menu import option_menu

from ui.styles import inject_custom_css
from ui.single_stock import render_single_stock
from ui.batch import render_batch_tab
from ui.compare import render_compare_tab
from ui.portfolio import render_portfolio_tab
from ui.alerts import render_alerts_tab
from ui.signals import render_signals_tab
from ui.reference import render_reference_tab
from ui.short_term_view import render_short_term_view_tab

st.set_page_config(page_title="My Screener", layout="wide", page_icon="📊")
inject_custom_css()

# --- Header spacing/alignment fixes local to this file. If ui/styles.py
# already centralizes CSS elsewhere, move this block there later — kept
# here for now so it's obvious exactly what changed for this pass. ---
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
    }
    .app-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        padding-left: 2px;
    }
    .app-header .logo {
        font-size: 26px;
        line-height: 1;
    }
    .app-header .title {
        font-size: 25px;
        font-weight: 800;
        color: #f8f9fc;
        letter-spacing: -0.4px;
        line-height: 1;
    }
    /* streamlit-option-menu renders inside an iframe-free component
       container — this targets the wrapper div Streamlit gives it so
       the nav bar sits flush under the header with no stray gap. */
    div[data-testid="stHorizontalBlock"] iframe {
        margin-top: -4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="app-header"><span class="logo">📊</span><span class="title">My Screener</span></div>', unsafe_allow_html=True)

PAGES = ["Single Stock", "Batch", "Compare", "Portfolio", "Alerts", "Signals", "Short Term View", "Reference"]
# Bootstrap icon names (streamlit-option-menu uses the Bootstrap Icons set,
# not emoji) — swap any of these for whatever fits better at
# https://icons.getbootstrap.com/
ICONS = ["search", "list-task", "bar-chart-line", "briefcase", "bell", "broadcast", "lightning", "book"]

# Translate a pending nav_target (set by Batch's "Go to Compare" button,
# or anywhere else that wants to force a page jump) into an index for
# manual_select. Popped so it only fires once.
manual_index = None
if "nav_target" in st.session_state:
    target = st.session_state.pop("nav_target")
    if target in PAGES:
        manual_index = PAGES.index(target)

active_page = option_menu(
    menu_title=None,
    options=PAGES,
    icons=ICONS,
    orientation="horizontal",
    manual_select=manual_index,
    default_index=0,
    key="active_page_menu",
    styles={
        "container": {
            "padding": "5px",
            "background-color": "#12121f",
            "border": "1px solid #2d2d44",
            "border-radius": "10px",
            "width": "100%",
        },
        "icon": {"color": "#93b4ff", "font-size": "13px"},
        "nav-link": {
            "font-size": "13px",
            "font-weight": "500",
            "text-align": "center",
            "flex-grow": "1",          # <- the fix: every pill claims equal
                                        #    width, so the bar always fills
                                        #    the full container regardless
                                        #    of window size.
            "margin": "0px 3px",
            "padding": "9px 6px",
            "border-radius": "7px",
            "color": "#9ca3af",
            "--hover-color": "#1c1c2e",
        },
        "nav-link-selected": {
            "background-color": "#5a8aff",
            "color": "#f8f9fc",
            "font-weight": "700",
            "box-shadow": "0 2px 10px rgba(90,138,255,0.35)",
        },
    },
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
elif active_page == "Short Term View":
    render_short_term_view_tab()
elif active_page == "Reference":
    render_reference_tab()
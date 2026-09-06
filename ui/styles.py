"""
ui/styles.py — the dark glassmorphic visual theme. This is a polish pass
over the original version: tighter padding/margins throughout (the goal
is "cosy and compact," not spacious), softer/smaller shadows, a subtle
hover lift on cards, and a couple of new small-badge classes (.delta-up/
.delta-down/.delta-flat, .completeness-badge) for the score-delta and
data-completeness indicators in ui/single_stock.py.

Call inject_custom_css() once, near the top of app.py, before rendering
any page content.
"""

import streamlit as st


def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        * { font-family: 'Inter', -apple-system, sans-serif; }

        .main .block-container { padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1180px; }

        section[data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at 15% 0%, #181a32 0%, #0a0a12 45%, #0a0a12 100%);
            background-attachment: fixed;
        }

        /* Tighten Streamlit's own vertical rhythm — the default block
           spacing is generous, which reads as "airy" rather than "cosy". */
        div[data-testid="stVerticalBlock"] > div { margin-bottom: 0.15rem; }
        div[data-testid="column"] { padding: 0 6px; }

        div[data-testid="stMetric"] {
            background: linear-gradient(160deg, rgba(34,36,58,0.75) 0%, rgba(20,20,32,0.92) 100%);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px; padding: 10px 14px;
            box-shadow: 0 1px 0 rgba(255,255,255,0.05) inset;
            transition: border-color 0.2s ease;
        }
        div[data-testid="stMetric"]:hover { border-color: rgba(90,138,255,0.35); }
        div[data-testid="stMetricLabel"] { font-size: 10.5px; color: #9497ad; text-transform: uppercase; letter-spacing: 0.7px; font-weight: 600; }
        div[data-testid="stMetricValue"] {
            font-size: 19px; font-weight: 700; letter-spacing: -0.4px;
            background: linear-gradient(135deg, #ffffff 0%, #c4c8d6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }

        div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input {
            background: rgba(26,26,42,0.92); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px; color: #f8f9fc; padding: 8px 13px; font-size: 14px;
        }
        div[data-testid="stTextInput"] input:focus, div[data-testid="stNumberInput"] input:focus {
            border-color: #5a8aff; box-shadow: 0 0 0 3px rgba(90,138,255,0.16);
        }

        div.stButton > button {
            border-radius: 10px; font-weight: 600; padding: 8px 20px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(26,26,42,0.85); color: #d1d5e0;
            transition: all 0.18s ease; font-size: 13.5px;
        }
        div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #5a8aff 0%, #3b5fe0 50%, #5a8aff 100%);
            border: none; color: white;
            box-shadow: 0 3px 14px rgba(90,138,255,0.4);
        }
        div.stButton > button[kind="primary"]:hover {
            box-shadow: 0 6px 22px rgba(90,138,255,0.55); transform: translateY(-1px);
        }
        div.stButton > button:not([kind="primary"]):hover {
            border-color: rgba(90,138,255,0.5); color: #93b4ff;
        }

        h1 {
            font-weight: 800 !important;
            background: linear-gradient(135deg, #ffffff 0%, #c4d0ff 50%, #a8b0c8 100%);
            -webkit-background-clip: text; letter-spacing: -1.6px;
            filter: drop-shadow(0 0 16px rgba(90,138,255,0.18));
            margin-bottom: 0.2rem !important;
        }
        h3, h4 { color: #f8f9fc !important; font-weight: 700 !important; margin: 0.3rem 0 !important; }
        h4 { font-size: 14.5px !important; letter-spacing: -0.1px; }

        hr {
            border: none !important; height: 1px !important; margin: 0.9rem 0 !important;
            background: linear-gradient(90deg, transparent, rgba(90,138,255,0.18), transparent) !important;
        }
        .stCaption, small { color: #6e7284 !important; font-size: 12px !important; }

        /* Dataframes (score history table etc.) — Streamlit theming has
           limited reach here, but a soft wrapper card keeps it visually
           consistent with everything else on the page. */
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; overflow: hidden;
            box-shadow: 0 4px 14px rgba(0,0,0,0.2);
        }

        /* Toggle / checkbox accent to match the blue theme instead of
           Streamlit's default red. */
        div[data-testid="stToggle"] label div[data-checked="true"] { background-color: #5a8aff !important; }

        /* Expander headers — align with the cat-card visual language
           rather than Streamlit's plain default. */
        div[data-testid="stExpander"] {
            border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 12px !important;
            background: rgba(20,20,32,0.5); overflow: hidden;
        }
        div[data-testid="stExpander"] summary {
            font-size: 13px !important; font-weight: 600 !important; color: #c4c8d6 !important;
        }

        /* ---- Tabs (raw-data tabs, results tabs) ---- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px; background: rgba(20,20,32,0.6); backdrop-filter: blur(8px);
            padding: 4px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.07);
            width: fit-content;
        }
        .stTabs [data-baseweb="tab-list"] button {
            background: transparent !important; border-radius: 8px !important;
            padding: 6px 16px !important; font-weight: 600; font-size: 12.5px;
            color: #6e7284 !important; border: none !important;
            transition: all 0.18s ease;
        }
        .stTabs [data-baseweb="tab-list"] button:hover { color: #c4c8d6 !important; }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            background: linear-gradient(135deg, #5a8aff 0%, #3b5fe0 100%) !important;
            color: white !important; box-shadow: 0 2px 10px rgba(90,138,255,0.35);
        }
        .stTabs [data-baseweb="tab-highlight"] { background: transparent !important; }
        .stTabs [data-baseweb="tab-border"] { background: transparent !important; height: 0 !important; }
        .stTabs [data-baseweb="tab-panel"] { padding-top: 0.9rem; }

        /* ---- Ticker / identity strip ---- */
        .ticker-strip {
            display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
            gap: 12px; background: linear-gradient(160deg, rgba(28,28,44,0.85) 0%, rgba(14,14,22,0.95) 100%);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.09); border-radius: 12px;
            padding: 12px 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        }
        .ticker-symbol { font-size: 19px; font-weight: 800; color: #f8f9fc; letter-spacing: -0.3px; }
        .ticker-price { font-size: 16px; font-weight: 700; color: #c4c8d6; margin-left: 12px; }
        .sector-inline { color: #fbbf24; font-size: 11.5px; margin-left: 9px; font-weight: 500; }

        /* ---- Score panels (PP / Sampat) ---- */
        .score-panel {
            background: linear-gradient(160deg, rgba(28,28,44,0.75) 0%, rgba(16,16,26,0.92) 100%);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;
            padding: 13px 16px; box-shadow: 0 4px 14px rgba(0,0,0,0.2);
        }
        .score-panel-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 9px; gap: 8px; flex-wrap: wrap;
        }
        .score-panel-name {
            font-size: 10.5px; font-weight: 700; letter-spacing: 1.1px; color: #8b8fa3; text-transform: uppercase;
        }
        .score-panel-verdict { font-size: 13px; font-weight: 700; }
        .score-panel-bar-track { height: 5px; border-radius: 3px; background: #1f1f30; overflow: hidden; margin-bottom: 7px; }
        .score-panel-bar-fill { height: 100%; border-radius: 3px; }
        .score-panel-footer { font-size: 12px; color: #9ca3af; display: flex; align-items: center; gap: 8px; }

        /* ---- Score delta / completeness mini-badges ---- */
        .delta-badge { font-size: 11.5px; font-weight: 700; padding: 2px 8px; border-radius: 10px; display: inline-block; margin-top: 4px; }
        .delta-up { color: #4ade80; background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.2); }
        .delta-down { color: #f87171; background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.2); }
        .delta-flat { color: #8b8fa3; background: rgba(139,143,163,0.1); border: 1px solid rgba(139,143,163,0.15); }
        .completeness-badge {
            font-size: 11px; color: #8b8fa3; background: rgba(139,143,163,0.08);
            border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 2px 8px;
            display: inline-block; margin-top: 4px;
        }

        /* ---- Departures board ---- */
        .board-panel {
            background: #05060a; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px;
            padding: 12px 16px; font-family: 'Courier New', monospace;
        }
        .board-title {
            font-size: 10.5px; font-weight: 700; color: #565a6e; letter-spacing: 1.8px;
            margin-bottom: 9px; text-transform: uppercase;
        }
        .board-row { display: flex; align-items: baseline; font-size: 12px; padding: 3px 0; letter-spacing: 0.4px; }
        .board-label { white-space: nowrap; }
        .board-dots { flex: 1; border-bottom: 1px dotted rgba(255,255,255,0.14); margin: 0 7px; height: 5px; }
        .board-status { white-space: nowrap; font-weight: 700; }
        .board-pass { color: #4ade80; }
        .board-fail { color: #f87171; }
        .board-na { color: #565a6e; }

        /* ---- Section cards (fundamentals / technicals / graham / gtt / piotroski) ---- */
        .cat-card {
            border-radius: 13px; padding: 13px 16px; margin-bottom: 10px;
            background: linear-gradient(160deg, rgba(28,28,44,0.65) 0%, rgba(16,16,26,0.88) 100%);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255,255,255,0.07);
            border-top: 2.5px solid transparent;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        .cat-card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.25); transform: translateY(-1px); }
        .cat-card.valuation { border-top-color: #c084fc; }
        .cat-card.profitability { border-top-color: #4ade80; }
        .cat-card.balance { border-top-color: #fb923c; }
        .cat-card.momentum { border-top-color: #60a5fa; }
        .cat-card.quality { border-top-color: #f472b6; }
        .cat-title {
            font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.1px;
            margin-bottom: 8px !important;
        }
        .cat-title.valuation { color: #c084fc; }
        .cat-title.profitability { color: #4ade80; }
        .cat-title.balance { color: #fb923c; }
        .cat-title.momentum { color: #60a5fa; }
        .cat-title.quality { color: #f472b6; }

        .warning-banner {
            background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.3);
            border-radius: 10px; padding: 9px 14px; margin: 7px 0; font-size: 12.5px; color: #fbbf24;
        }
        /* ---- Batch tab cards ----
           Batch uses st.container(border=True) instead of a raw .cat-card
           <div>, since the Evaluate button has to live inside the card and
           Streamlit widgets can't sit inside hand-written HTML. This gives
           that native bordered container the same glassmorphic look as
           .cat-card elsewhere, so Batch and Single Stock feel consistent. */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 13px !important;
            background: linear-gradient(160deg, rgba(28,28,44,0.65) 0%, rgba(16,16,26,0.88) 100%);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255,255,255,0.07) !important;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: 0 6px 20px rgba(0,0,0,0.25);
            transform: translateY(-1px);
        }
        /* ---- Page switcher (replaces st.tabs) ----
           app.py switched from st.tabs to st.radio bound to
           session_state["active_page"], because st.tabs has no API to
           switch tabs from code — Batch's "Go to Compare" button needs
           that. This makes the radio look like the same pill-tab bar
           .stTabs used.

           NOTE: an earlier version of this CSS tried to hide the native
           radio circle with a descendant selector (`label div:first-child`),
           which matched too broadly across Streamlit's actual DOM and
           hid the option TEXT along with the circle — empty pills, no
           labels. This version deliberately does NOT try to hide the
           circle at all (that requires knowing the exact DOM structure,
           which varies by Streamlit version) — it just recolors it to
           match the theme via `accent-color`, a plain CSS property that
           can't accidentally hide anything else. If you want the circle
           fully hidden for an exact match to the old tab look, send me
           the rendered HTML for one `div[data-testid="stRadio"]` (right-
           click → Inspect in the browser) and I'll target it precisely
           instead of guessing again. */
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 2px; background: rgba(20,20,32,0.6); backdrop-filter: blur(8px);
            padding: 4px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.07);
            width: fit-content; flex-direction: row;
        }
        div[data-testid="stRadio"] label {
            border-radius: 8px !important;
            padding: 4px 14px !important; margin: 0 !important;
            transition: background 0.18s ease; cursor: pointer;
        }
        div[data-testid="stRadio"] label:hover {
            background: rgba(255,255,255,0.05) !important;
        }
        div[data-testid="stRadio"] input[type="radio"] {
            accent-color: #5a8aff;
        }
        div[data-testid="stRadio"] label p {
            font-size: 12.5px !important; font-weight: 600; color: #c4c8d6 !important;
        }
        div[data-testid="stRadio"] label:has(input:checked) {
            background: linear-gradient(135deg, rgba(90,138,255,0.25) 0%, rgba(59,95,224,0.25) 100%) !important;
            box-shadow: 0 2px 10px rgba(90,138,255,0.2);
        }
        div[data-testid="stRadio"] label:has(input:checked) p {
            color: #ffffff !important;
        }
    </style>
    """, unsafe_allow_html=True)
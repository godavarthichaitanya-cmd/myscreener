"""
ui/reference.py — Reference tab: a glossary of every PP/Sampat check plus
a full plain-English walkthrough of the whole tool with a worked example.
Meant as a standing "what does this actually mean" document — no fetching,
no computation, works standalone at any time.

Two sub-tabs:
  Reference — every check grouped by category, using
    config/check_explainers.get_explainer() for the 16 checks whose exact
    label strings I've directly seen in code (single_stock.py's
    render_category_radar categories dict), plus hand-written descriptions
    for the 2 manual-entry checks (promoter pledge, EPS CAGR) since I
    haven't seen their exact label strings confirmed anywhere in code —
    calling get_explainer() with a guessed label risks a silent None, so
    these two are described directly here instead. If get_explainer()
    returns None for any of the 16 (label mismatch), a fallback note
    shows instead of a blank line. Also documents the Short Term View
    decision verdicts (Sept 2026) — same "why does this exist" treatment
    as the PP verdict thresholds below it.
  How to Read — a full narrative walkthrough: what the tool is for, what
    each tab does, and a worked example using illustrative (not live)
    numbers for a hypothetical stock, clearly labeled as illustrative
    throughout so it's never mistaken for a real fetched result.
"""

import streamlit as st

from config.check_explainers import get_explainer

_CATEGORIES = {
    "Valuation": ["PE under 25x", "PEG under 1.0x"],
    "Balance Sheet": ["D/E under 0.5x", "Interest coverage above 5x", "FCF positive"],
    "Quality": ["Piotroski F-Score >= 7"],
    "Profitability": ["ROE above 15%", "ROCE above 15%", "Revenue growth above 10%", "Operating margin expanding (3yr)"],
    "Momentum (technicals)": [
        "Price above 200 EMA", "RSI in 40-60 zone", "MACD bullish",
        "Volume confirms move (>1.2x avg)", "Outperforming Nifty (3mo)", "Golden cross (50DMA > 200DMA)",
    ],
}

_MANUAL_CHECKS = [
    ("Promoter pledge 0%", "Passes when the promoter pledge % you entered in a stock's \"Your data\" section is 0. A non-zero pledge means promoters have put their own shares up as loan collateral — a red flag if it's high, since a forced sale on default can hit the stock hard. This has to be entered by hand because it isn't in yfinance's data."),
    ("EPS CAGR above 12%", "Passes when the 5-year EPS CAGR % you entered (typically pulled from Screener.in) is above 12%. This is the manual figure that takes priority for Graham Fair Value too, over the auto-fetched 3-year fallback, because the auto version can't detect corporate actions like mergers or bonus issues that distort a naive year-over-year comparison."),
]

# Mirrors core/short_term_decision.py's VERDICT_COLORS keys and copy —
# kept here as plain reference text rather than importing decide_action's
# strings directly, since this tab is meant to work standalone with no
# computation.
_SHORT_TERM_VERDICTS = [
    ("🟢 Momentum buy setup", "Trend + MACD + volume all bullish — the only verdict with three-way confirmation. The closest thing to a green light this tool produces."),
    ("🟢 Reversal confirming", "RSI oversold AND a fresh bullish MACD/EMA200 crossover just fired. The specific combination that separates \"bounce starting\" from \"still falling\"."),
    ("🔵 Bullish, unconfirmed by volume", "Trend + MACD bullish, but no unusual buying volume backing it. Workable, lower conviction — size down or just watch."),
    ("🔵 Mild bullish lean", "Only one of trend/RSI/MACD agrees bullish. A lean, not a setup — a watch-item, not an entry."),
    ("🟡 Caution — extended", "Bullish and RSI is overbought. Momentum is real but chasing here risks buying right before a pullback — wait for a dip toward the 200EMA."),
    ("🟡 Wait — reversal not confirmed", "RSI is oversold but trend/MACD haven't turned up yet. Entering now is betting on a bounce with no confirmation it's started."),
    ("🟠 Mild bearish lean", "Only one of trend/RSI/MACD agrees bearish. Not strong enough to force an exit on its own if already held."),
    ("🔴 Avoid — active selling", "Trend + MACD bearish AND volume shows active selling. If holding, a signal to reassess; not a name to enter fresh."),
    ("🔴 Avoid — clear downtrend", "Trend + MACD both bearish with no reversal signal — RSI isn't even oversold yet, so there may be more room to fall."),
    ("🔴 Avoid — overbought, trend not confirming", "RSI stretched above 70 with nothing backing it up — often precedes a reversal down rather than further upside."),
    ("⚪ No clear setup", "Trend, RSI, and MACD are roughly balanced. Nothing to act on either direction right now."),
]


def render_reference_tab():
    st.subheader("📖 Reference")

    tab_glossary, tab_howto = st.tabs(["Check Glossary", "How to Read (walkthrough)"])

    with tab_glossary:
        _render_glossary()

    with tab_howto:
        _render_howto()


def _render_glossary():
    st.caption("Every check in the PP Framework, grouped by category. Sampat Mode uses a stricter subset of the same fundamentals checks — see the note at the bottom.")

    for category, labels in _CATEGORIES.items():
        st.markdown(f"#### {category}")
        for label in labels:
            explanation = get_explainer(label)
            st.markdown(f"**{label}**")
            st.caption(explanation if explanation else "No explainer text found for this check yet — add one in config/check_explainers.py.")
        st.write("")

    st.markdown("#### Manual Entries")
    st.caption("These two need a number you type in yourself (in a stock's \"Your data\" section) — yfinance doesn't carry them.")
    for label, explanation in _MANUAL_CHECKS:
        st.markdown(f"**{label}**")
        st.caption(explanation)
    st.write("")

    st.markdown("#### Verdict thresholds")
    st.markdown(
        "- 🟢 **Deploy ready** — fundamentals+quality checks pass at 75%+ AND technicals pass at 60%+\n"
        "- 🟡 **Watch** — strong on one side but not both (either fundamentals are solid but technicals haven't confirmed yet, or vice versa)\n"
        "- 🔴 **Avoid** — both sides are weak"
    )
    st.caption("A check that shows N/A (missing data for that stock) is excluded from both the numerator and denominator — it doesn't count against the stock, it just isn't scored.")

    st.markdown("#### Sampat Mode")
    st.caption(
        "A stricter, fundamentals-only second opinion shown alongside the standard PP verdict — near-zero D/E required "
        "(≤0.1x, vs the standard check's 0.5x), technicals excluded entirely, and Free Cash Flow double-weighted in the "
        "score without being shown twice as a separate row."
    )

    st.markdown("#### Context-only indicators (not scored)")
    st.markdown(
        "- **Graham Fair Value** — a conservative valuation estimate (EPS × (8.5 + 2×growth), growth capped at 20% "
        "to avoid absurd numbers on hyper-growth stocks). Quality compounders often trade above this — it's a floor "
        "to think about, not a target.\n"
        "- **GTT proximity** — how close the current price is to a GTT (Good-Till-Triggered) order level you've configured.\n"
        "- **Sector PE benchmark** — an approximate average PE for the stock's broad sector, for context on whether it's "
        "trading rich or cheap relative to peers.\n"
        "- **Dividend yield, ATR (volatility), 52-week-high proximity** — shown for context, no pass/fail attached."
    )

    st.markdown("#### Combined Signal (Single Stock)")
    st.caption(
        "Single Stock shows one more banner above the PP Framework / Sampat Mode panels once you Evaluate — it "
        "merges the PP verdict (long-term) with the Short Term View verdict (pure momentum, no fundamentals) "
        "computed off the same fetched data, no separate scan needed."
    )
    st.markdown(
        "- 🟢🟢 **BUY — both sides confirm** — the ONLY case that says BUY: PP verdict is Deploy-ready AND Short "
        "Term View hit its top verdict (Momentum buy setup or Reversal confirming). Everything else below is a "
        "more qualified sentence, not a label — a good business with unconfirmed short-term momentum (e.g. "
        "bullish trend but no volume backing it) does NOT get called BUY, on purpose.\n"
        "- **Good business, decent timing** — PP Deploy-ready, Short Term leaning bullish but not fully "
        "confirmed. Reasonable to start a position; not the strongest case.\n"
        "- **Good business — wait on entry timing** — PP Deploy-ready, but Short Term says wait (overbought or "
        "an unconfirmed oversold reversal).\n"
        "- **Good business, weak near-term** — PP Deploy-ready, but the short-term picture is currently "
        "negative. Sticking to a GTT/staggered entry rather than buying at market.\n"
        "- **Good business, no timing signal either way** — PP Deploy-ready, Short Term flat/mixed.\n"
        "- **Short-term opportunity only — not a V13 add** — PP is Watch, but Short Term hit its top verdict. "
        "A trade with its own stop, not a long-term position — the business hasn't earned that yet.\n"
        "- **Mixed — business still Watch-stage** — PP is Watch and Short Term isn't strong enough to change "
        "that framing.\n"
        "- **Caution — technical bounce only** — PP is Avoid, but Short Term shows a buy-tier signal. A pure "
        "momentum trade against a business the framework has flagged as weak — high risk, not a V13 candidate.\n"
        "- **Avoid** — PP is Avoid and Short Term isn't showing a strong enough signal to caveat that."
    )
    st.write("")

    st.markdown("#### Short Term View verdicts")
    st.caption(
        "A completely separate decision framework from the PP verdict above — no fundamentals involved at all, just "
        "trend (200EMA), RSI zone, MACD, and volume, combined into one of 11 verdicts. Checked in priority order: "
        "overbought RSI first, then oversold RSI (specifically checking for a confirming crossover), then everything "
        "else falls through to the plain bullish-vs-bearish vote count. Only the two 🟢 verdicts are genuine \"look "
        "closer\" signals — everything else is either a lean, a wait, or an avoid."
    )
    for headline, reason in _SHORT_TERM_VERDICTS:
        st.markdown(f"**{headline}**")
        st.caption(reason)
    st.write("")
    st.caption(
        "Position sizing (stop-loss and quantity) only shows underneath the two 🟢 verdicts as something worth "
        "acting on — for every other verdict it's still shown, but read it as \"if you were already holding this, "
        "here's your reference stop,\" not as an entry signal."
    )


def _render_howto():
    st.markdown(
"""
### What this tool actually does

At its core, this is a checklist. For any NSE-listed stock, it pulls
fundamentals (PE, ROE, debt levels, growth, cash flow, and more) and
technicals (moving averages, RSI, MACD, volume) and runs them through the
**PP Framework** — 18 pass/fail checks split into fundamentals+quality
(12 of them) and technicals (6 of them). It doesn't predict anything or
tell you what will happen to the price — it just tells you, plainly,
how many boxes a stock currently ticks, and which ones it doesn't.

The idea behind splitting fundamentals from technicals is simple: a
great business can still be a bad *entry point* right now (overbought,
no momentum), and a stock with great charts can still be a bad
*business* underneath. The verdict only turns green when both sides
agree.

---

### A worked example (illustrative numbers — not a live fetch)

Say you type **RELIANCE** into Single Stock and hit Fetch. Suppose —
purely as an example — it comes back showing:

- PE: 24.1 | ROE: 9.2% | D/E: 0.38x | PEG: 1.6x
- RSI: 52 | Price is above its 200-day EMA | MACD is bullish
- Piotroski F-Score: 6/9

Walking through a few of the 18 checks with these illustrative numbers:

- **PE under 25x** → 24.1 is under 25 → ✅ **PASS**
- **ROE above 15%** → 9.2% is below 15% → ❌ **FAIL**
- **D/E under 0.5x** → 0.38x is under 0.5x → ✅ **PASS**
- **PEG under 1.0x** → 1.6x is above 1.0x → ❌ **FAIL**
- **Price above 200 EMA** → yes → ✅ **PASS**
- **RSI in 40-60 zone** → 52 is inside that range → ✅ **PASS**
- **MACD bullish** → yes → ✅ **PASS**
- **Piotroski F-Score ≥ 7** → 6/9 is below 7 → ❌ **FAIL**

Roll all 18 up and you might land on something like **fundamentals 8/12
(67%)** and **technicals 5/6 (83%)**. Since fundamentals are below the
75% bar for a green verdict, this would land as 🟡 **Watch** —
technicals look genuinely good right now, but the underlying business
hasn't cleared the fundamentals bar yet. That's the tool telling you:
*the chart says "maybe now," the balance sheet says "not yet."*

---

### Reading the rest of the Single Stock page

- **The tabs above Evaluate** (Overview, Fundamentals, Technicals,
  Valuation & Quality, Chart) are all just the *raw data* — nothing is
  scored yet. Nothing gets logged to history until you click Evaluate.
- **The combined signal banner**, right above the two score panels once
  you Evaluate, merges the PP verdict with a Short Term View read
  computed off the same fetched data — no separate scan. It's
  deliberately conservative with the word BUY: that only appears when
  PP is Deploy-ready AND Short Term hits its top verdict. Every other
  combination (e.g. a Deploy-ready stock with unconfirmed short-term
  momentum) gets an honest, specific sentence instead — see "Combined
  Signal" in the Check Glossary tab for the full set.
- **The two score panels** (PP Framework, Sampat Mode) are the actual
  answer. Sampat Mode is a stricter second opinion — same idea, tighter
  bar (near-zero debt, fundamentals-only, no technicals at all).
- **The departures board** (in the Checks tab, styled like an old airport
  board) lists every check worst-first, so failures and N/As jump out
  immediately instead of being buried in a wall of green.
- **Category Strength** is the same 18 checks, but grouped into 5 spider-
  chart categories (Valuation, Balance Sheet, Quality, Profitability,
  Momentum) so you can see at a glance *which kind* of weakness a stock
  has, not just an overall score.
- If the verdict is **Avoid**, the **Alternatives** tab can suggest other
  stocks in the same industry that score better — useful when you like a
  sector but this particular pick isn't it.

---

### The other tabs, briefly

- **Batch** — runs the whole PP Framework across a queue (your V13 core
  list, your Portfolio, or any custom list) instead of one stock at a
  time. Same checks, same verdicts, just many stocks in a grid.
- **Compare** — 2 to 4 stocks side by side: score panels, a normalized
  price chart (so a ₹200 stock and a ₹4,000 stock are visually
  comparable), a metrics table, and both PP and Sampat check boards for
  each.
- **Portfolio** — your actual holdings. Not really about the PP
  Framework at first — it's P&L (what you paid vs. what it's worth now)
  — but each holding also gets a PP verdict for free, so you can see not
  just "am I up or down" but "does this still pass the checklist."
- **Alerts** — a much lighter, faster scan across a queue — just RSI
  extremes, fresh moving-average or MACD crossovers, and volume spikes.
  Not the 18-check framework at all; more like a "did anything just
  change" pulse-check. It only shows stocks where something actually
  fired.
- **Signals** — similarly lightweight, but framed as a directional
  read: how many of EMA trend / RSI / MACD are leaning bullish vs.
  bearish right now, single stock or across a queue.
- **Short Term View** — combines Alerts and Signals against a dedicated
  short-term watchlist (separate from the V13 queue), then goes one step
  further than either: instead of leaving you to interpret raw vote
  counts, it hands back one verdict with a plain-English reason (see the
  Short Term View verdicts section in the Check Glossary tab), plus an
  ATR-based stop-loss and position size sized to a capital pool you set
  aside specifically for short-term trades — completely separate from
  V13's long-term capital and completely separate from the PP Framework's
  fundamentals. This tab answers "is there a short-term trade here right
  now," not "is this a good business."

---

### The short version

If you only remember one thing: **green means both the business and the
chart currently agree it's a reasonable entry; yellow means only one of
them does; red means neither does.** Everything else in this tool exists
to help you see *why* a stock landed where it did, not just *that* it did.
Short Term View follows the same spirit on a faster clock: it's not
telling you the business is good, only that the trend/momentum/volume
picture right now does or doesn't support a short-term trade.
"""
    )
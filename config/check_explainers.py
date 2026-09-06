"""
config/check_explainers.py — short, plain-language descriptions for every
PP/Sampat check label, ported from the old app's Reference tab. Used by
ui/single_stock.py to show "what does this actually mean" next to the
departures board, without needing to flip to a separate tab to remember.

Keyed by the exact check label string used in core/checks.py and
core/verdict.py — if you rename or add a check there, add/update the
matching entry here too, or it'll just silently show no explanation.
"""

CHECK_EXPLAINERS = {
    "PE under 25x": "How many years of current profit it'd take to earn back your purchase price. Lower means you're paying less for the same earnings.",
    "ROE above 15%": "How efficiently the company turns shareholder money into profit — its own 'interest rate' on the capital it's been given.",
    "ROCE above 15%": "Same idea as ROE, but counts total capital (debt + equity). Can't be flattered by leverage alone the way ROE sometimes can.",
    "D/E under 0.5x": "How much the company has borrowed versus what shareholders own — like checking a loan against real savings.",
    "Interest coverage above 5x": "Whether operating profit comfortably covers loan interest payments.",
    "PEG under 1.0x": "PE adjusted for growth rate. Tells you if you're paying a fair price relative to how fast earnings are actually growing.",
    "Revenue growth above 10%": "Is the business genuinely getting bigger year over year, or standing still?",
    "Operating margin expanding (3yr)": "Is profitability per rupee of sales improving or eroding over time? Revenue can grow while margins quietly shrink.",
    "FCF positive": "Real spendable cash left after running the business — different from accounting profit, which can include non-cash items.",
    "Promoter pledge 0%": "Have founders/owners put their own shares up as loan collateral? Pledged shares can be forcibly sold if the stock crashes.",
    "EPS CAGR above 12%": "How much profit-per-share has compounded on average each year over 5 years, smoothing out one-off good or bad years.",
    "Piotroski F-Score >= 7": "A 9-point balance-sheet and earnings-quality checklist — positive ROA, real cash generation, decreasing leverage, no dilution, improving margins and efficiency.",
    "Price above 200 EMA": "The 200-day average is a slow-moving trend line. Price above it confirms a broader uptrend, not just a short bounce.",
    "RSI in 40-60 zone": "A 0-100 gauge of recent buying/selling intensity. The 40-60 zone targets calm, neutral entry conditions — not overheated, not oversold.",
    "MACD bullish": "Compares a fast-moving average against a slow one. A crossover above signals building upward momentum.",
    "Volume confirms move (>1.2x avg)": "Is there real trading conviction behind a price move, or is it happening on thin, unconvincing volume?",
    "Outperforming Nifty (3mo)": "Is the stock beating the broader market, or just drifting up because the whole market is up?",
    "Golden cross (50DMA > 200DMA)": "A classic trend-confirmation signal — the 50-day average crossing above the 200-day average signals a shift toward a sustained uptrend.",
    "D/E \u2264 0.1x (Sampat Strict)": "Sampat Mode's stricter near-zero debt bar — far tighter than the standard 0.5x check, looking for companies that barely borrow at all.",
}


def get_explainer(label: str):
    """Returns the explanation for a check label, or None if there isn't
    one on file yet (e.g. a newly added check nobody's documented here)."""
    return CHECK_EXPLAINERS.get(label)
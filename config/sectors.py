"""
config/sectors.py — flags stocks whose financials don't fit the standard
PP framework balance-sheet checks (ROCE, D/E, interest coverage, margin
trend, FCF all mean something different — or nothing — for banks/NBFCs,
since deposits and loans dominate their balance sheets instead of typical
assets/liabilities).

Edit BANK_NBFC_SYMBOLS directly as you evaluate more stocks and discover
ones that need the flag. Symbols should be NSE tickers, uppercase, no
".NS" suffix (that's added by data/fetch.py, not stored here).
"""

BANK_NBFC_SYMBOLS = {
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
    "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN", "PNB", "BANKBARODA",
    "IDFCFIRSTB", "FEDERALBNK", "AUBANK", "RBLBANK", "YESBANK",
    "SBIN", "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBANK",
    "PNB", "BANKBARODA", "CANBK", "IDFCFIRSTB", "FEDERALBNK", "RBLBANK",
    "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN",
    "PFC", "RECLTD", "IRFC", "HDFCLIFE", "SBILIFE", "ICICIPRULI", "ICICIGI","HUDCO"
}

# One emoji per yfinance sector string, for a quick visual identifier next
# to the sector name in the ticker strip. Falls back to a plain chart icon
# for any sector not listed here (a new/unmapped sector, or "Unknown").
SECTOR_ICONS = {
    "Technology": "💻",
    "Financial Services": "💰",
    "Healthcare": "⚕️",
    "Consumer Cyclical": "🛍️",
    "Consumer Defensive": "🛒",
    "Energy": "⛽",
    "Basic Materials": "🏗️",
    "Industrials": "🏭",
    "Communication Services": "📡",
    "Utilities": "💡",
    "Real Estate": "🏢",
}


def get_sector_icon(sector):
    """Returns the emoji for a sector string, or a generic fallback icon
    if the sector is unmapped/unknown/None."""
    if not sector:
        return "📊"
    return SECTOR_ICONS.get(sector, "📊")


def is_bank_or_nbfc(symbol: str) -> bool:
    """True if the given NSE symbol is a bank or NBFC and should skip the
    4 balance-sheet-specific PP checks (ROCE, D/E, interest coverage,
    margin trend, FCF)."""
    return symbol.upper() in BANK_NBFC_SYMBOLS
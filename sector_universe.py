"""
Loads the curated stock universe. If stock_universe.csv exists (built via
build_universe.py), uses that structured hierarchy. Otherwise falls back
to the flat CANDIDATE_UNIVERSE list so nothing breaks before the first build.

CANDIDATE_UNIVERSE itself is now sourced from NSE's official EQUITY_L.csv
when present (download manually: nseindia.com > Market Data > Equity >
Securities available for Trading, save as EQUITY_L.csv in this folder) —
covering ~2,000+ mainboard symbols instead of the original curated 300.
Falls back to the original 300-symbol list if EQUITY_L.csv isn't found.
"""
import csv
import os

_CSV_PATH = "stock_universe.csv"
_EQUITY_LIST_PATH = "EQUITY_L.csv"

# Fallback flat list — used only if EQUITY_L.csv hasn't been downloaded yet.
# Kept exactly as before so nothing breaks for existing setups.
_FALLBACK_UNIVERSE = [
    "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "PERSISTENT", "COFORGE",
    "MPHASIS", "LTTS", "OFSS", "TATAELXSI", "KPITTECH", "CYIENT", "SONATSOFTW",
    "BSOFT", "ZENSARTECH", "NEWGEN", "HDFCBANK", "ICICIBANK", "AXISBANK",
    "KOTAKBANK", "INDUSINDBK", "IDFCFIRSTB", "FEDERALBNK", "BANDHANBNK",
    "RBLBANK", "AUBANK", "CSBBANK", "DCBBANK", "SBIN", "BANKBARODA", "PNB",
    "CANBK", "UNIONBANK", "INDIANB", "BANKINDIA", "MAHABANK", "UCOBANK", "IOB",
    "CENTRALBK", "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN",
    "MUTHOOTFIN", "MANAPPURAM", "LICHSGFIN", "PNBHOUSING", "AAVAS",
    "CANFINHOME", "SUNDARMFIN", "M&MFIN", "PFC", "RECLTD", "IREDA", "HDFCLIFE",
    "SBILIFE", "ICICIPRULI", "ICICIGI", "STARHEALTH", "GICRE", "NIACL",
    "HDFCAMC", "NIPPONLIFE", "UTIAMC", "ANGELONE", "ISEC", "CDSL", "BSE",
    "MCX", "IEX", "CAMS", "SUNPHARMA", "CIPLA", "DRREDDY", "LUPIN",
    "AUROPHARMA", "TORNTPHARM", "ZYDUSLIFE", "ALKEM", "IPCALAB", "ABBOTINDIA",
    "MANKIND", "GLENMARK", "BIOCON", "DIVISLAB", "LAURUSLABS", "GLAND",
    "AJANTPHARM", "NATCOPHARM", "GRANULES", "SYNGENE", "PFIZER", "SANOFI",
    "JBCHEPHARM", "APOLLOHOSP", "FORTIS", "MAXHEALTH", "METROPOLIS",
    "LALPATHLAB", "NH", "KIMS", "RAINBOW", "MEDANTA", "ASTERDM", "HINDUNILVR",
    "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP",
    "TATACONSUM", "COLPAL", "VBL", "UBL", "EMAMILTD", "GILLETTE", "PGHH",
    "RADICO", "PATANJALI", "BAJAJCON", "MARUTI", "TATAMOTORS", "M&M",
    "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "TVSMOTOR", "ASHOKLEY", "ESCORTS",
    "FORCEMOT", "SMLISUZU", "BOSCHLTD", "MOTHERSON", "BALKRISIND", "MRF",
    "APOLLOTYRE", "CEATLTD", "EXIDEIND", "AMARAJABAT", "SUNDRMFAST",
    "BHARATFORG", "ENDURANCE", "SCHAEFFLER", "TITAN", "TRENT", "DMART",
    "PIDILITIND", "HAVELLS", "VOLTAS", "CROMPTON", "PAGEIND", "RELAXO",
    "BATAINDIA", "ABFRL", "VMART", "SHOPERSTOP", "KALYANKJIL", "WHIRLPOOL",
    "BLUESTARCO", "DIXON", "AMBER", "TATASTEEL", "JSWSTEEL", "HINDALCO",
    "VEDANTA", "JINDALSTEL", "SAIL", "NMDC", "HINDZINC", "NATIONALUM",
    "APLAPOLLO", "RATNAMANI", "JSL", "WELCORP", "UPL", "PIIND", "SRF",
    "AARTIIND", "DEEPAKNTR", "NAVINFLUOR", "ATUL", "FLUOROCHEM", "CHAMBLFERT",
    "COROMANDEL", "GNFC", "GSFC", "TATACHEM", "VINATIORGA", "CLEAN",
    "RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "HINDPETRO", "OIL", "PETRONET",
    "GUJGASLTD", "IGL", "MGL", "AEGISCHEM", "NTPC", "TATAPOWER", "ADANIPOWER",
    "ADANIGREEN", "ADANIENSOL", "NHPC", "SJVN", "TORNTPOWER", "CESC",
    "JSWENERGY", "SUZLON", "INOXWIND", "KPIGREEN", "POWERGRID", "COALINDIA",
    "LT", "SIEMENS", "ABB", "CUMMINSIND", "BEL", "BHEL", "HAL", "BEML",
    "THERMAX", "AIAENG", "KIRLOSENG", "CGPOWER", "TRITURBINE", "GRINDWELL",
    "POLYCAB", "KEI", "FINCABLES", "HONAUT", "ADANIPORTS", "CONCOR", "IRCTC",
    "GMRAIRPORT", "IRFC", "RVNL", "RAILTEL", "GRSE", "COCHINSHIP", "MAZDOCK",
    "TRANSPORTCORP", "VRLLOG", "DELHIVERY", "GESHIP", "GATI", "BDL",
    "SOLARINDS", "DATAPATTNS", "MTARTECH", "BHARTIARTL", "IDEA", "TATACOMM",
    "PVRINOX", "ZEEL", "SUNTV", "NETWORK18", "TIPSMUSIC", "SAREGAMA", "DLF",
    "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD", "LODHA", "BRIGADE",
    "SOBHA", "SUNTECK", "MAHLIFE", "ULTRACEMCO", "SHREECEM", "AMBUJACEM",
    "ACC", "DALBHARAT", "JKCEMENT", "RAMCOCEM", "HEIDELBERG", "STARCEMENT",
    "CENTURYPLY", "GREENPANEL", "TRIDENT", "WELSPUNIND", "KPRMILL", "GOKEX",
    "RAYMOND", "ARVIND", "VARDHMAN", "ZOMATO", "NYKAA", "PAYTM", "POLICYBZR",
    "NAUKRI", "MAPMYINDIA", "CARTRADE", "EASEMYTRIP", "ADANIENT", "GRASIM",
    "BAJAJHLDNG", "INDIGO", "SPICEJET",
]


def _load_full_symbol_list():
    """
    Reads NSE's official EQUITY_L.csv (all mainboard-listed symbols) if
    present in this folder. Only rows with SERIES == "EQ" are kept (the
    standard equity series — excludes SME/other series). Falls back to
    the curated 300-symbol list if the file hasn't been downloaded yet
    or fails to parse.

    NSE's CSV often has stray leading/trailing spaces in its header names
    (e.g. " SERIES" instead of "SERIES") — every key/value is stripped
    before matching to avoid silently falling back because of that.
    """
    if os.path.exists(_EQUITY_LIST_PATH):
        symbols = []
        with open(_EQUITY_LIST_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clean_row = {
                    (k.strip() if k else k): (v.strip() if isinstance(v, str) else v)
                    for k, v in row.items()
                }
                if clean_row.get("SERIES") == "EQ":
                    symbol = clean_row.get("SYMBOL")
                    if symbol:
                        symbols.append(symbol)
        if symbols:
            return symbols
        print(f"⚠️ {_EQUITY_LIST_PATH} found but 0 symbols matched SERIES=='EQ' — "
              f"check its column headers. Falling back to the curated {len(_FALLBACK_UNIVERSE)}-symbol list.")
    return _FALLBACK_UNIVERSE


CANDIDATE_UNIVERSE = _load_full_symbol_list()


def load_universe():
    """
    Returns a list of dicts: {Symbol, CompanyName, Sector, Industry,
    MarketCapCr, CapCategory}. Reads stock_universe.csv if present;
    otherwise returns bare-minimum dicts from CANDIDATE_UNIVERSE
    (Sector/Industry/CapCategory as "Unknown" until you run build_universe.py).
    """
    if os.path.exists(_CSV_PATH):
        with open(_CSV_PATH, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    return [
        {"Symbol": s, "CompanyName": "", "Sector": "Unknown", "Industry": "Unknown",
         "MarketCapCr": "", "CapCategory": "Unknown"}
        for s in CANDIDATE_UNIVERSE
    ]
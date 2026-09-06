import pandas as pd


def calculate_ema(df: pd.DataFrame, period: int = 200) -> pd.Series:
    """
    Exponential Moving Average — weights recent prices more heavily than
    old ones, so it reacts faster to trend changes than a simple average.
    Used for the 200 EMA (long-term trend) and inside MACD (12/26 EMA).
    Unlike a rolling SMA, ewm() doesn't need `period` rows to produce a
    value — it starts computing from the first row, so it won't return
    NaN just because history is shorter than `period`.
    """
    return df["Close"].ewm(span=period, adjust=False).mean()


def calculate_sma(df: pd.DataFrame, period: int) -> pd.Series:
    """
    Simple Moving Average — plain rolling average of the last `period`
    closes. Used for the 50DMA/200DMA pair that feeds the Golden Cross
    check. Unlike EMA, this genuinely returns NaN for any row before
    `period` rows of history exist (a real, correct NaN — not a bug).
    """
    return df["Close"].rolling(window=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Relative Strength Index — a 0-100 gauge of recent buying vs selling
    pressure over the last `period` days. Above 70 is generally considered
    overheated/overbought, below 30 oversold. The PP framework's "RSI in
    40-60 zone" check targets calm, neutral entry conditions rather than
    chasing momentum or catching a falling knife.
    """
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    Moving Average Convergence Divergence — compares a fast EMA against a
    slower EMA to gauge shifting momentum. Returns three series:
      - macd_line: fast EMA minus slow EMA
      - signal_line: a smoothed (EMA) version of the MACD line itself
      - histogram: macd_line minus signal_line (the gap between the two)
    "MACD bullish" in the PP framework means macd_line has crossed above
    signal_line — the fast trend just turned up relative to the slow one.
    """
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_atr(df: pd.DataFrame, period: int = 14):
    """
    Average True Range — a volatility measure: the average of the last
    `period` days' "true range" (the largest of today's high-low spread,
    today's high vs yesterday's close, or today's low vs yesterday's
    close). Context-only in the PP framework, not scored — useful for
    judging how much room to leave around a GTT trigger price.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr


def get_52wk_range(df: pd.DataFrame):
    """
    Simple 52-week high/low off the last ~252 trading days (252 trading
    days ≈ 1 calendar year). Used for the "% below 52-week high" context
    metric — not scored, just useful framing for how far a stock has
    pulled back from its recent peak.
    """
    last_year = df.tail(252)
    return {
        "low_52wk": round(last_year["Close"].min(), 2),
        "high_52wk": round(last_year["Close"].max(), 2)
    }


def get_golden_cross(df: pd.DataFrame):
    """
    Golden Cross check — True when the 50-day SMA is above the 200-day
    SMA (a classic bullish trend-confirmation signal), False when it's
    below (a "death cross" / bearish signal), None when there isn't
    enough price history yet to compute a reliable 200-day average
    (needs at least 200 trading days — roughly 9-10 months).

    NOTE: this was previously inverted in the old codebase (used `<`
    instead of `>`, so it silently reported death crosses as golden
    crosses). Fixed here — confirm this reads correctly against a known
    stock before relying on it.
    """
    if len(df) < 200:
        return None
    sma50 = calculate_sma(df, 50)
    sma200 = calculate_sma(df, 200)
    if pd.isna(sma50.iloc[-1]) or pd.isna(sma200.iloc[-1]):
        return None
    return sma50.iloc[-1] > sma200.iloc[-1]
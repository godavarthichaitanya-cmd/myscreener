"""
core/signal_calcs.py — shared technical-signal helpers for the Alerts and
Signals tabs (ui/alerts.py, ui/signals.py).

Both tabs need rolling, series-level RSI/MACD/volume analysis — not just
core/bundle.py's single latest values (bundle.py's rsi14/macd_bull/
golden_cross are enough for the PP framework's pass/fail checks, but
Alerts/Signals need to look back a few days to detect *fresh* crossovers
and spikes). This is new scoring logic, not a reuse of core/checks.py.

Reuses data/indicators.py's calculate_ema(df, period) for EMA — that
signature is already confirmed elsewhere in the app (used by
ui/single_stock.py's chart tab: `calculate_ema(df, 200)`). RSI, MACD, and
volume-spike detection are implemented locally here since I haven't seen
equivalent functions already in data/indicators.py or core/bundle.py —
guessing an unconfirmed signature has burned a build before (see
batch.py's early build_checks() mismatch). If data/indicators.py already
has RSI/MACD helpers, point me at them and I'll switch these over instead
of keeping a second implementation.

All functions take a price_history DataFrame with at least Close/Open/
Volume columns, indexed by date — the same shape core/bundle.py's
fetch_stock_bundle() already returns as bundle["price_history"].
"""

import pandas as pd
from data.indicators import calculate_ema

RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_SPIKE_WINDOW = 20
VOLUME_SPIKE_THRESHOLD = 1.8
FRESH_LOOKBACK_DAYS = 3


def rsi_series(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Standard Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def rsi_zone(latest_rsi):
    """Oversold (<30) / Overbought (>70) / Neutral (30-70) / None if no
    value. "Neutral" spans the whole healthy middle range — callers that
    want a bullish/bearish split within it (see ui/signals.py's 0-3
    count) do that themselves rather than this function overloading its
    return value."""
    if latest_rsi is None or pd.isna(latest_rsi):
        return None
    if latest_rsi < RSI_OVERSOLD:
        return "Oversold"
    if latest_rsi > RSI_OVERBOUGHT:
        return "Overbought"
    return "Neutral"


def macd_lines(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line) — standard 12/26/9 EMA MACD."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def fresh_crossover(series_a: pd.Series, series_b: pd.Series, lookback_days: int = FRESH_LOOKBACK_DAYS):
    """Returns 'bullish' if series_a crossed above series_b within the
    last `lookback_days` rows, 'bearish' if it crossed below, else None
    (no crossover in that window)."""
    diff = (series_a - series_b).dropna()
    if len(diff) < lookback_days + 1:
        return None
    sign = diff.apply(lambda x: 1 if x > 0 else -1)
    recent = sign.iloc[-(lookback_days + 1):]
    for i in range(1, len(recent)):
        if recent.iloc[i] != recent.iloc[i - 1]:
            return "bullish" if recent.iloc[i] > 0 else "bearish"
    return None


def volume_spike(df: pd.DataFrame, window: int = VOLUME_SPIKE_WINDOW, threshold: float = VOLUME_SPIKE_THRESHOLD):
    """Returns (is_spike, ratio, direction). direction is 'Buying' if the
    spike day's candle closed up (Close >= Open), 'Selling' if it closed
    down — same buying/selling-by-candle-direction tagging the old app's
    Alerts tab used."""
    if "Volume" not in df.columns or len(df) < window + 1:
        return False, None, None
    avg_vol = df["Volume"].iloc[-(window + 1):-1].mean()
    latest_vol = df["Volume"].iloc[-1]
    if avg_vol == 0 or pd.isna(avg_vol):
        return False, None, None
    ratio = latest_vol / avg_vol
    is_spike = ratio >= threshold
    direction = None
    if is_spike and "Open" in df.columns:
        direction = "Buying" if df["Close"].iloc[-1] >= df["Open"].iloc[-1] else "Selling"
    return is_spike, round(ratio, 2), direction


def ema_trend(df: pd.DataFrame, period: int = 200):
    """True if latest Close is above the EMA, False if below, None if
    not enough data to compute it."""
    ema = calculate_ema(df, period)
    if ema is None or ema.dropna().empty:
        return None
    latest_ema = ema.iloc[-1]
    if pd.isna(latest_ema):
        return None
    return df["Close"].iloc[-1] > latest_ema


def fresh_ema_crossover(df: pd.DataFrame, period: int = 200, lookback_days: int = FRESH_LOOKBACK_DAYS):
    """Fresh price-vs-EMA crossover — not just 'above/below today' (which
    core/checks.py's PP check already covers), but 'crossed within the
    last N days'."""
    ema = calculate_ema(df, period)
    if ema is None:
        return None
    return fresh_crossover(df["Close"], ema, lookback_days)

def atr(df, period=14):
    """Average True Range over `period` days. Returns None if there
    isn't enough price history yet (mirrors how ema_trend/rsi_zone
    handle insufficient data elsewhere in this file)."""
    if df is None or len(df) < period + 1:
        return None
 
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
 
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
 
    atr_series = true_range.rolling(period).mean()
    if atr_series.empty or pd.isna(atr_series.iloc[-1]):
        return None
 
    return round(float(atr_series.iloc[-1]), 2)
"""Historical intraday OHLCV data fetching, with local CSV caching."""

from __future__ import annotations

import os

import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data_cache")

# yfinance intraday history limits: 1m -> last ~7d, 5m/15m/30m/60m -> last ~60d.
INTERVAL_MAX_PERIOD = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
}


def fetch_intraday(ticker: str, interval: str = "5m", period: str | None = None, use_cache: bool = True) -> pd.DataFrame:
    """Fetch intraday OHLCV bars for `ticker`, restricted to regular trading hours.

    Returns a DataFrame indexed by tz-aware America/New_York timestamps with
    columns: open, high, low, close, volume.
    """
    if interval not in INTERVAL_MAX_PERIOD:
        raise ValueError(f"unsupported interval {interval!r}, choose one of {list(INTERVAL_MAX_PERIOD)}")
    period = period or INTERVAL_MAX_PERIOD[interval]

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{ticker}_{interval}_{period}.csv")

    if use_cache and os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        return df

    raw = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=True)
    if raw.empty:
        raise RuntimeError(f"no data returned for {ticker} ({interval}, {period})")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.columns = [c.lower() for c in raw.columns]
    raw = raw[["open", "high", "low", "close", "volume"]]

    if raw.index.tz is None:
        raw.index = raw.index.tz_localize("UTC")
    raw.index = raw.index.tz_convert("America/New_York")

    # Restrict to regular trading hours 9:30-16:00 ET.
    raw = raw.between_time("09:30", "16:00")

    raw.to_csv(cache_path)
    return raw

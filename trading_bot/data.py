"""Historical OHLCV data fetching, with local CSV caching.

Talks to Yahoo Finance's public chart API directly via `requests` rather
than through the `yfinance` package. `yfinance` uses `curl_cffi` to
impersonate a browser's TLS fingerprint, which gets its connections reset
by this environment's TLS-inspecting proxy; plain `requests` doesn't hit
that problem and reaches the same endpoint fine.
"""

from __future__ import annotations

import os

import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data_cache")
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Yahoo's intraday history limits: 1m -> last ~7d, 5m/15m/30m/60m -> last ~60d.
INTERVAL_MAX_RANGE = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
}


def _fetch_chart(ticker: str, interval: str, range_: str) -> pd.DataFrame:
    resp = requests.get(
        CHART_URL.format(ticker=ticker),
        params={"interval": interval, "range": range_},
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()["chart"]
    if payload.get("error"):
        raise RuntimeError(f"Yahoo Finance error for {ticker}: {payload['error']}")

    result = payload["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
        "volume": quote["volume"],
    }, index=pd.to_datetime(timestamps, unit="s", utc=True))
    df = df.dropna()
    if df.empty:
        raise RuntimeError(f"no data returned for {ticker} ({interval}, {range_})")

    df.index = df.index.tz_convert("America/New_York")
    return df


def fetch_intraday(ticker: str, interval: str = "5m", period: str | None = None, use_cache: bool = True) -> pd.DataFrame:
    """Fetch intraday OHLCV bars for `ticker`, restricted to regular trading hours.

    Returns a DataFrame indexed by tz-aware America/New_York timestamps with
    columns: open, high, low, close, volume.
    """
    if interval not in INTERVAL_MAX_RANGE:
        raise ValueError(f"unsupported interval {interval!r}, choose one of {list(INTERVAL_MAX_RANGE)}")
    period = period or INTERVAL_MAX_RANGE[interval]

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{ticker}_{interval}_{period}.csv")

    if use_cache and os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        return df

    df = _fetch_chart(ticker, interval, period)
    df = df.between_time("09:30", "16:00")  # regular trading hours only
    df.to_csv(cache_path)
    return df


def fetch_daily(ticker: str, period: str = "1y", use_cache: bool = True) -> pd.DataFrame:
    """Fetch daily OHLCV bars for `ticker` (for swing/screening use, not intraday)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{ticker}_1d_{period}.csv")

    if use_cache and os.path.exists(cache_path):
        return pd.read_csv(cache_path, index_col=0, parse_dates=True)

    df = _fetch_chart(ticker, "1d", period)
    df.to_csv(cache_path)
    return df

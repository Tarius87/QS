"""Quantitative screen for "promising" AI-sector stocks, over a fixed
watchlist rather than open-ended discovery (there's no free, reliable feed
of brand-new AI listings). Signal-only: never places orders.

Criteria (all rules-based, no news/sentiment judgment calls):
  - near_52w_high: close within `high_proximity_pct` of the trailing
    252-session high
  - volume_surge: latest volume >= `volume_multiple` x its 20-day average
  - momentum: `momentum_days`-session return >= `momentum_threshold_pct`

Edit WATCHLIST below to add/remove tickers you want tracked.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data import fetch_daily

WATCHLIST = [
    "NVDA", "AMD", "MSFT", "GOOGL", "META", "AVGO", "TSM", "SMCI", "PLTR",
    "AI", "SOUN", "BBAI", "IONQ", "ARM", "CRWD", "MRVL", "DELL", "ORCL",
    "ADBE", "NOW", "PANW",
]


@dataclass
class ScreenParams:
    high_proximity_pct: float = 5.0   # within 5% of 252-session high
    volume_multiple: float = 1.5      # 1.5x the 20-day average volume
    momentum_days: int = 20
    momentum_threshold_pct: float = 10.0


def screen_ticker(df: pd.DataFrame, params: ScreenParams) -> dict | None:
    """Pure evaluation of one ticker's daily OHLCV against the criteria.

    Returns a result dict if ALL criteria pass, else None. Unit-testable
    with synthetic price data.
    """
    if len(df) < params.momentum_days + 1:
        return None

    df = df.sort_index()
    last = df.iloc[-1]

    trailing = df.tail(252)
    high_252 = trailing["high"].max()
    pct_below_high = (high_252 - last["close"]) / high_252 * 100
    if pct_below_high > params.high_proximity_pct:
        return None

    avg_vol_20 = df["volume"].tail(21).iloc[:-1].mean()
    if avg_vol_20 <= 0 or last["volume"] < params.volume_multiple * avg_vol_20:
        return None

    momentum_start = df.iloc[-(params.momentum_days + 1)]["close"]
    momentum_pct = (last["close"] - momentum_start) / momentum_start * 100
    if momentum_pct < params.momentum_threshold_pct:
        return None

    return {
        "close": last["close"],
        "pct_below_52w_high": round(pct_below_high, 2),
        "volume_vs_20d_avg": round(last["volume"] / avg_vol_20, 2),
        "momentum_pct": round(momentum_pct, 2),
    }


def screen_watchlist(tickers: list[str] | None = None, params: ScreenParams | None = None) -> pd.DataFrame:
    """Fetch daily data (network) for each ticker and apply `screen_ticker`."""
    tickers = tickers or WATCHLIST
    params = params or ScreenParams()

    rows = []
    for ticker in tickers:
        try:
            df = fetch_daily(ticker)
        except Exception as exc:  # noqa: BLE001 - keep screening the rest on a single bad ticker
            print(f"skipping {ticker}: {exc}")
            continue
        result = screen_ticker(df, params)
        if result:
            rows.append({"ticker": ticker, **result})

    return pd.DataFrame(rows).sort_values("momentum_pct", ascending=False) if rows else pd.DataFrame()

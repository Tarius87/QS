"""Opening Range Breakout (ORB) strategy.

Classic intraday rules:
  1. Watch the first `opening_range_minutes` of the session; record its high/low.
  2. On the first subsequent bar that closes above the range high, go long
     (or below the range low, go short, if shorting is enabled).
  3. Stop-loss at the opposite side of the opening range.
  4. Take-profit at `take_profit_r` multiples of the range size.
  5. Force-exit any open position at `eod_exit_time`.
  6. At most `max_trades_per_day` entries per session (default 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pandas as pd


@dataclass
class ORBParams:
    opening_range_minutes: int = 15
    take_profit_r: float = 2.0
    direction: str = "both"  # "long_only", "short_only", "both"
    max_trades_per_day: int = 1
    eod_exit_time: time = field(default_factory=lambda: time(15, 55))


@dataclass
class Trade:
    day: pd.Timestamp
    side: str  # "long" or "short"
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str  # "stop", "target", "eod"


def generate_trades(df: pd.DataFrame, params: ORBParams) -> list[Trade]:
    """Simulate the ORB strategy bar-by-bar over each trading day in `df`."""
    trades: list[Trade] = []

    for day, day_df in df.groupby(df.index.date):
        day_df = day_df.sort_index()
        if len(day_df) < 3:
            continue

        session_start = day_df.index[0]
        range_end = session_start + pd.Timedelta(minutes=params.opening_range_minutes)
        opening = day_df[day_df.index < range_end]
        after_open = day_df[day_df.index >= range_end]
        if opening.empty or after_open.empty:
            continue

        range_high = opening["high"].max()
        range_low = opening["low"].min()
        range_size = range_high - range_low
        if range_size <= 0:
            continue

        trades_today = 0
        position = None  # dict while a trade is open

        for ts, bar in after_open.iterrows():
            if position is None:
                if trades_today >= params.max_trades_per_day:
                    continue
                if bar["close"] > range_high and params.direction in ("both", "long_only"):
                    position = {
                        "side": "long",
                        "entry_time": ts,
                        "entry_price": bar["close"],
                        "stop_price": range_low,
                        "target_price": bar["close"] + params.take_profit_r * range_size,
                    }
                elif bar["close"] < range_low and params.direction in ("both", "short_only"):
                    position = {
                        "side": "short",
                        "entry_time": ts,
                        "entry_price": bar["close"],
                        "stop_price": range_high,
                        "target_price": bar["close"] - params.take_profit_r * range_size,
                    }
                continue

            # Manage open position.
            exit_price = None
            exit_reason = None
            if position["side"] == "long":
                if bar["low"] <= position["stop_price"]:
                    exit_price, exit_reason = position["stop_price"], "stop"
                elif bar["high"] >= position["target_price"]:
                    exit_price, exit_reason = position["target_price"], "target"
            else:
                if bar["high"] >= position["stop_price"]:
                    exit_price, exit_reason = position["stop_price"], "stop"
                elif bar["low"] <= position["target_price"]:
                    exit_price, exit_reason = position["target_price"], "target"

            if exit_price is None and ts.time() >= params.eod_exit_time:
                exit_price, exit_reason = bar["close"], "eod"

            if exit_price is not None:
                trades.append(Trade(
                    day=pd.Timestamp(day),
                    side=position["side"],
                    entry_time=position["entry_time"],
                    entry_price=position["entry_price"],
                    stop_price=position["stop_price"],
                    target_price=position["target_price"],
                    exit_time=ts,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                ))
                trades_today += 1
                position = None

        # Force-close anything still open at end of day's data.
        if position is not None:
            last_ts, last_bar = after_open.index[-1], after_open.iloc[-1]
            trades.append(Trade(
                day=pd.Timestamp(day),
                side=position["side"],
                entry_time=position["entry_time"],
                entry_price=position["entry_price"],
                stop_price=position["stop_price"],
                target_price=position["target_price"],
                exit_time=last_ts,
                exit_price=last_bar["close"],
                exit_reason="eod",
            ))

    return trades

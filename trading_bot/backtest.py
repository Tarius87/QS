"""Backtest engine: turns a list of Trade signals into a simulated equity curve
with fixed-fractional position sizing and a daily max-loss circuit breaker.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .strategy import Trade


@dataclass
class RiskParams:
    starting_equity: float = 25_000.0  # PDT minimum for unrestricted day trading
    risk_per_trade_pct: float = 0.005  # fraction of equity risked per trade (stop distance)
    max_daily_loss_pct: float = 0.02  # halt new entries for the day once breached
    slippage_bps: float = 2.0  # adverse price move applied to entry & exit, in bps


@dataclass
class TradeResult:
    trade: Trade
    shares: float
    pnl_dollars: float
    equity_after: float


def run_backtest(trades: list[Trade], risk: RiskParams) -> tuple[list[TradeResult], pd.DataFrame]:
    """Simulate `trades` in chronological order against a single account.

    Returns (per-trade results, daily equity curve DataFrame indexed by day).
    """
    trades = sorted(trades, key=lambda t: t.entry_time)

    equity = risk.starting_equity
    results: list[TradeResult] = []
    daily_records = []

    current_day = None
    day_start_equity = equity
    day_pnl = 0.0
    slip = risk.slippage_bps / 10_000.0

    for t in trades:
        if t.day != current_day:
            if current_day is not None:
                daily_records.append({"day": current_day, "equity": equity, "pnl": day_pnl})
            current_day = t.day
            day_start_equity = equity
            day_pnl = 0.0

        if day_pnl <= -risk.max_daily_loss_pct * day_start_equity:
            continue  # circuit breaker tripped for the rest of the day

        stop_distance = abs(t.entry_price - t.stop_price)
        if stop_distance <= 0:
            continue

        risk_dollars = risk.risk_per_trade_pct * equity
        shares = risk_dollars / stop_distance

        entry_price = t.entry_price * (1 + slip if t.side == "long" else 1 - slip)
        exit_price = t.exit_price * (1 - slip if t.side == "long" else 1 + slip)

        if t.side == "long":
            pnl = (exit_price - entry_price) * shares
        else:
            pnl = (entry_price - exit_price) * shares

        equity += pnl
        day_pnl += pnl
        results.append(TradeResult(trade=t, shares=shares, pnl_dollars=pnl, equity_after=equity))

    if current_day is not None:
        daily_records.append({"day": current_day, "equity": equity, "pnl": day_pnl})

    equity_curve = pd.DataFrame(daily_records).set_index("day") if daily_records else pd.DataFrame(columns=["equity", "pnl"])
    return results, equity_curve

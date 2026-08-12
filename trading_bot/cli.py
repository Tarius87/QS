"""Run an Opening Range Breakout backtest from the command line.

Example:
    python -m trading_bot.cli --ticker SPY --interval 5m --range-minutes 15
"""

from __future__ import annotations

import argparse

from .backtest import RiskParams, run_backtest
from .data import fetch_intraday
from .metrics import compute_metrics, format_metrics
from .strategy import ORBParams, generate_trades


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticker", default="SPY")
    p.add_argument("--interval", default="5m", choices=["1m", "5m", "15m", "30m", "60m"])
    p.add_argument("--range-minutes", type=int, default=15)
    p.add_argument("--take-profit-r", type=float, default=2.0)
    p.add_argument("--direction", default="both", choices=["long_only", "short_only", "both"])
    p.add_argument("--starting-equity", type=float, default=25_000.0)
    p.add_argument("--risk-per-trade-pct", type=float, default=0.005)
    p.add_argument("--max-daily-loss-pct", type=float, default=0.02)
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args()

    df = fetch_intraday(args.ticker, interval=args.interval, use_cache=not args.no_cache)
    print(f"Loaded {len(df)} {args.interval} bars for {args.ticker} "
          f"({df.index[0].date()} to {df.index[-1].date()})")

    strat_params = ORBParams(
        opening_range_minutes=args.range_minutes,
        take_profit_r=args.take_profit_r,
        direction=args.direction,
    )
    trades = generate_trades(df, strat_params)

    risk_params = RiskParams(
        starting_equity=args.starting_equity,
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_daily_loss_pct=args.max_daily_loss_pct,
    )
    results, equity_curve = run_backtest(trades, risk_params)

    metrics = compute_metrics(results, equity_curve, args.starting_equity)
    print()
    print(format_metrics(metrics))


if __name__ == "__main__":
    main()

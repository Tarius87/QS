"""Offline sanity check for the ORB pipeline using a random-walk price series.

This does NOT test whether the strategy has any real edge — the price
process here is pure random noise, so results are meaningless as trading
performance. It only confirms the strategy/backtest/metrics plumbing runs
end-to-end and produces sane numbers (useful in environments without
market-data access, like this sandbox).

Run with: python -m trading_bot.synthetic_check
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import RiskParams, run_backtest
from .metrics import compute_metrics, format_metrics
from .strategy import ORBParams, generate_trades

BARS_PER_DAY = 78  # 6.5h session at 5-minute bars
SEED = 7


def make_random_walk_days(n_days: int = 60, start_price: float = 400.0, bar_vol: float = 0.0007, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    price = start_price

    for d in range(n_days):
        day = pd.Timestamp("2024-01-02") + pd.Timedelta(days=d)
        if day.weekday() >= 5:
            continue
        idx = pd.date_range(f"{day.date()} 09:30", periods=BARS_PER_DAY, freq="5min", tz="America/New_York")

        opens, highs, lows, closes, vols = [], [], [], [], []
        for _ in range(BARS_PER_DAY):
            sub_returns = rng.normal(0, bar_vol, 5)
            sub_prices = price * np.cumprod(1 + sub_returns)
            o = price
            c = sub_prices[-1]
            h = max(o, c, sub_prices.max())
            l = min(o, c, sub_prices.min())
            opens.append(o); highs.append(h); lows.append(l); closes.append(c)
            vols.append(rng.integers(500_000, 2_000_000))
            price = c

        frames.append(pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols}, index=idx
        ))

    return pd.concat(frames)


def run_one(seed: int, n_days: int = 60) -> dict:
    df = make_random_walk_days(n_days=n_days, seed=seed)
    strat_params = ORBParams(opening_range_minutes=15, take_profit_r=2.0, direction="both")
    trades = generate_trades(df, strat_params)
    risk_params = RiskParams(starting_equity=25_000.0, risk_per_trade_pct=0.005, max_daily_loss_pct=0.02)
    results, equity_curve = run_backtest(trades, risk_params)
    return compute_metrics(results, equity_curve, risk_params.starting_equity)


def main(n_seeds: int = 20, n_days: int = 60):
    print(f"Running ORB pipeline against {n_seeds} independent random-walk price series "
          f"({n_days} sessions each).")
    print("NOTE: price process is random noise in every run — this establishes what a "
          "NO-EDGE strategy looks like on this backtest engine, not a prediction of real "
          "performance. It is a noise floor to compare real results against, and a plumbing check.\n")

    rows = []
    for seed in range(n_seeds):
        m = run_one(seed, n_days=n_days)
        if m.get("trades", 0) > 0:
            rows.append(m)

    returns = np.array([m["total_return_pct"] for m in rows])
    pfs = np.array([m["profit_factor"] for m in rows if np.isfinite(m["profit_factor"])])
    sharpes = np.array([m["sharpe_annualized"] for m in rows])
    win_rates = np.array([m["win_rate"] for m in rows])
    drawdowns = np.array([m["max_drawdown_pct"] for m in rows])

    print(f"Seeds with trades: {len(rows)}/{n_seeds}\n")
    print(f"{'metric':<20}{'mean':>10}{'std':>10}{'min':>10}{'max':>10}")
    for name, arr in [
        ("total_return_pct", returns),
        ("profit_factor", pfs),
        ("sharpe_annualized", sharpes),
        ("win_rate", win_rates),
        ("max_drawdown_pct", drawdowns),
    ]:
        print(f"{name:<20}{arr.mean():>10.2f}{arr.std():>10.2f}{arr.min():>10.2f}{arr.max():>10.2f}")

    print(f"\nFraction of noise runs with positive return: {(returns > 0).mean():.0%}")
    print("If a real-data backtest doesn't clearly beat this range, treat it as noise, not edge.")


if __name__ == "__main__":
    main()

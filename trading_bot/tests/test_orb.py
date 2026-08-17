"""Unit tests for the ORB strategy and backtest engine against synthetic bars
(no network access required)."""

import pandas as pd

from trading_bot.backtest import RiskParams, run_backtest
from trading_bot.strategy import ORBParams, generate_trades


def _bar(ts, o, h, l, c, v=1000):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def make_synthetic_day(date: str, breakout: str) -> pd.DataFrame:
    """Build one session of 5-minute bars: a flat opening range, then either
    a clean breakout to a target (`breakout="target"`) or a fakeout that
    reverses to the stop (`breakout="stop"`)."""
    idx = pd.date_range(f"{date} 09:30", periods=20, freq="5min", tz="America/New_York")
    rows = []
    # Opening range: 3 bars, high=101, low=99.
    rows.append(_bar(idx[0], 100, 100.5, 99.5, 100))
    rows.append(_bar(idx[1], 100, 101, 99, 100.2))
    rows.append(_bar(idx[2], 100.2, 100.8, 99.8, 100))
    # Breakout bar closes above range high (101).
    rows.append(_bar(idx[3], 100, 101.5, 100, 101.5))

    if breakout == "target":
        # Range size = 2 (101-99), target = entry(101.5) + 2*2 = 105.5
        rows.append(_bar(idx[4], 101.5, 106, 101.4, 105.8))
    else:
        # Reverses hard back down through the stop (99).
        rows.append(_bar(idx[4], 101.5, 101.6, 98.5, 98.7))

    for i in range(5, 20):
        rows.append(_bar(idx[i], 100, 100.2, 99.8, 100))

    return pd.DataFrame(rows, index=idx)


def test_orb_hits_target():
    df = make_synthetic_day("2024-01-02", "target")
    trades = generate_trades(df, ORBParams(opening_range_minutes=15, take_profit_r=2.0))
    assert len(trades) == 1
    t = trades[0]
    assert t.side == "long"
    assert t.exit_reason == "target"
    assert t.exit_price > t.entry_price


def test_orb_hits_stop():
    df = make_synthetic_day("2024-01-03", "stop")
    trades = generate_trades(df, ORBParams(opening_range_minutes=15, take_profit_r=2.0))
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "stop"
    assert t.exit_price < t.entry_price


def test_backtest_position_sizing_and_equity():
    df1 = make_synthetic_day("2024-01-02", "target")
    df2 = make_synthetic_day("2024-01-03", "stop")
    df = pd.concat([df1, df2])

    trades = generate_trades(df, ORBParams(opening_range_minutes=15, take_profit_r=2.0))
    assert len(trades) == 2

    risk = RiskParams(starting_equity=25_000.0, risk_per_trade_pct=0.005, slippage_bps=0.0)
    results, equity_curve = run_backtest(trades, risk)

    assert len(results) == 2
    # Winning trade risked ~0.5% of equity at entry (stop distance * shares ~= risk_dollars).
    win = results[0]
    assert win.pnl_dollars > 0
    loss = results[1]
    assert loss.pnl_dollars < 0
    assert equity_curve["equity"].iloc[-1] == results[-1].equity_after


def test_daily_loss_circuit_breaker():
    # Two stop-outs on the same day should trip the breaker before a third.
    idx = pd.date_range("2024-01-04 09:30", periods=45, freq="5min", tz="America/New_York")
    rows = [_bar(idx[0], 100, 100.5, 99.5, 100), _bar(idx[1], 100, 101, 99, 100.2), _bar(idx[2], 100.2, 100.8, 99.8, 100)]
    rows.append(_bar(idx[3], 100, 101.5, 100, 101.5))
    rows.append(_bar(idx[4], 101.5, 101.6, 98.5, 98.7))  # stop 1
    for i in range(5, 20):
        rows.append(_bar(idx[i], 100, 100.2, 99.8, 100))
    df = pd.DataFrame(rows, index=idx[: len(rows)])

    trades = generate_trades(df, ORBParams(opening_range_minutes=15, take_profit_r=2.0, max_trades_per_day=5))
    risk = RiskParams(starting_equity=25_000.0, risk_per_trade_pct=0.5, max_daily_loss_pct=0.01, slippage_bps=0.0)
    results, equity_curve = run_backtest(trades, risk)

    assert len(results) <= 1  # breaker should block further entries same day after first big loss

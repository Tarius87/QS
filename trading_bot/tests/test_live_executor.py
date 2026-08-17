from datetime import datetime

import pytz

from trading_bot.live.broker import DryRunBroker
from trading_bot.live.executor import LiveExecutor
from trading_bot.live.risk_guard import LiveRiskLimits, RiskGuard
from trading_bot.strategy import ORBParams

TZ = pytz.timezone("America/New_York")


def _ts(hour, minute):
    return TZ.localize(datetime(2024, 1, 2, hour, minute))


def _bar(o, h, l, c, v=100_000):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def make_executor(max_position_dollars=1000.0, max_daily_loss_dollars=150.0, max_trades_per_day=3):
    guard = RiskGuard(LiveRiskLimits(max_position_dollars, max_daily_loss_dollars, max_trades_per_day))
    broker = DryRunBroker()
    executor = LiveExecutor(params=ORBParams(opening_range_minutes=15, take_profit_r=2.0), risk_guard=guard, broker=broker)
    return executor, broker, guard


def test_builds_opening_range_then_enters_on_breakout():
    executor, broker, _ = make_executor()

    assert "building opening range" in executor.on_bar("SPY", _ts(9, 30), _bar(100, 100.5, 99.5, 100))
    assert "building opening range" in executor.on_bar("SPY", _ts(9, 40), _bar(100, 101, 99, 100.2))

    result = executor.on_bar("SPY", _ts(9, 46), _bar(100, 101.5, 100, 101.5))
    assert "entered long" in result
    assert len(broker.log) == 1
    assert broker.log[0]["side"] == "buy"


def test_exits_on_target_and_records_pnl():
    executor, broker, guard = make_executor(max_position_dollars=1000.0)

    executor.on_bar("SPY", _ts(9, 30), _bar(100, 100.5, 99.5, 100))
    executor.on_bar("SPY", _ts(9, 40), _bar(100, 101, 99, 100.2))
    executor.on_bar("SPY", _ts(9, 46), _bar(100, 101.5, 100, 101.5))  # entry, range=2, target ~105.5

    result = executor.on_bar("SPY", _ts(9, 51), _bar(101.5, 106, 101.4, 105.8))
    assert "exited" in result
    assert "target" in result
    assert len(broker.log) == 2
    assert broker.log[1]["side"] == "sell"


def test_position_cap_blocks_entry_when_too_small():
    executor, broker, _ = make_executor(max_position_dollars=50.0)  # can't buy even 1 share near $100-101

    executor.on_bar("SPY", _ts(9, 30), _bar(100, 100.5, 99.5, 100))
    executor.on_bar("SPY", _ts(9, 40), _bar(100, 101, 99, 100.2))
    result = executor.on_bar("SPY", _ts(9, 46), _bar(100, 101.5, 100, 101.5))

    assert "skipped" in result
    assert len(broker.log) == 0


def test_risk_guard_blocks_second_entry_after_daily_loss():
    executor, broker, guard = make_executor(max_position_dollars=1000.0, max_daily_loss_dollars=10.0)
    guard.record_fill(_ts(9, 30).date(), -20)  # already past the daily loss limit

    executor.on_bar("SPY", _ts(9, 30), _bar(100, 100.5, 99.5, 100))
    executor.on_bar("SPY", _ts(9, 40), _bar(100, 101, 99, 100.2))
    result = executor.on_bar("SPY", _ts(9, 46), _bar(100, 101.5, 100, 101.5))

    assert "blocked by risk guard" in result
    assert len(broker.log) == 0

from datetime import date

from trading_bot.live.risk_guard import LiveRiskLimits, RiskGuard

DAY1 = date(2024, 1, 2)
DAY2 = date(2024, 1, 3)


def test_approves_within_all_limits():
    guard = RiskGuard(LiveRiskLimits(max_position_dollars=100, max_daily_loss_dollars=150, max_trades_per_day=3))
    approved, reason = guard.approve_trade(DAY1, 80)
    assert approved, reason


def test_rejects_over_position_cap():
    guard = RiskGuard(LiveRiskLimits(max_position_dollars=100))
    approved, reason = guard.approve_trade(DAY1, 150)
    assert not approved
    assert "exceeds hard cap" in reason


def test_rejects_after_max_trades_per_day():
    guard = RiskGuard(LiveRiskLimits(max_position_dollars=100, max_trades_per_day=2))
    guard.record_fill(DAY1, -10)
    guard.record_fill(DAY1, -10)
    approved, reason = guard.approve_trade(DAY1, 50)
    assert not approved
    assert "max trades per day" in reason


def test_daily_loss_kill_switch_blocks_further_trades():
    guard = RiskGuard(LiveRiskLimits(max_position_dollars=100, max_daily_loss_dollars=50, max_trades_per_day=10))
    guard.record_fill(DAY1, -60)
    approved, reason = guard.approve_trade(DAY1, 50)
    assert not approved
    assert "daily loss limit" in reason


def test_limits_reset_on_new_day():
    guard = RiskGuard(LiveRiskLimits(max_position_dollars=100, max_daily_loss_dollars=50, max_trades_per_day=1))
    guard.record_fill(DAY1, -60)
    approved, _ = guard.approve_trade(DAY1, 50)
    assert not approved

    approved, reason = guard.approve_trade(DAY2, 50)
    assert approved, reason

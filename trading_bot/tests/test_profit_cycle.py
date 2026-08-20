from datetime import datetime

from trading_bot.live.broker import DryRunBroker
from trading_bot.live.profit_cycle import ProfitCycleManager, ProfitCycleParams

NOW = datetime(2024, 1, 2, 10, 0)


def test_first_call_enters_position():
    mgr = ProfitCycleManager(ProfitCycleParams(ticker="SPY", principal_dollars=100.0), broker=DryRunBroker())
    result = mgr.on_price(NOW, 100.0)
    assert "bought" in result
    assert mgr.position is not None
    assert mgr.position.shares == 1.0  # $100 / $100 per share
    assert mgr.position.cost_basis == 100.0


def test_holds_below_profit_target():
    mgr = ProfitCycleManager(ProfitCycleParams(profit_take_pct=0.10), broker=DryRunBroker())
    mgr.on_price(NOW, 100.0)
    result = mgr.on_price(NOW, 105.0)  # only +5%
    assert "holding" in result
    assert mgr.position is not None


def test_takes_profit_splits_and_reenters():
    broker = DryRunBroker()
    mgr = ProfitCycleManager(
        ProfitCycleParams(ticker="SPY", principal_dollars=100.0, profit_take_pct=0.10, reinvest_fraction=0.5),
        broker=broker,
        reinvest_ticker_picker=lambda: "VTI",
    )
    mgr.on_price(NOW, 100.0)          # buy 1 share @ 100
    result = mgr.on_price(NOW, 110.0)  # +10% -> sell, profit = $10

    assert "sold SPY" in result
    assert "profit $10.00" in result
    assert mgr.kept_cash == 5.0  # half of $10 profit
    assert len(mgr.reinvested_positions) == 1
    assert mgr.reinvested_positions[0].ticker == "VTI"
    assert mgr.reinvested_positions[0].cost_basis == 5.0

    # next cycle should have re-entered SPY with fresh $100 principal
    assert mgr.position is not None
    assert mgr.position.cost_basis == 100.0


def test_no_reinvest_picker_keeps_all_profit_as_cash():
    mgr = ProfitCycleManager(
        ProfitCycleParams(ticker="SPY", principal_dollars=100.0, profit_take_pct=0.10, reinvest_fraction=0.5),
        broker=DryRunBroker(),
    )
    mgr.on_price(NOW, 100.0)
    mgr.on_price(NOW, 110.0)
    assert mgr.kept_cash == 10.0  # $5 "kept" share + $5 that failed to find a reinvest ticker
    assert mgr.reinvested_positions == []


def test_reinvest_cap_falls_back_to_cash():
    mgr = ProfitCycleManager(
        ProfitCycleParams(ticker="SPY", principal_dollars=100.0, profit_take_pct=0.10,
                           reinvest_fraction=1.0, max_total_reinvested_dollars=3.0),
        broker=DryRunBroker(),
        reinvest_ticker_picker=lambda: "VTI",
    )
    mgr.on_price(NOW, 100.0)
    result = mgr.on_price(NOW, 110.0)  # reinvest_amount = $10, over the $3 cap
    assert "reinvest cap" in result
    assert mgr.reinvested_positions == []
    assert mgr.kept_cash == 10.0


def test_principal_ticker_picker_used_for_entry():
    picks = iter(["NVDA", "AMD"])  # a different pick each cycle
    mgr = ProfitCycleManager(
        ProfitCycleParams(ticker="SPY", principal_dollars=100.0, profit_take_pct=0.10),
        broker=DryRunBroker(),
        principal_ticker_picker=lambda: next(picks, None),
    )
    assert mgr.next_ticker() == "NVDA"
    result = mgr.on_price(NOW, 100.0)
    assert "NVDA" in result
    assert mgr.position.ticker == "NVDA"

    mgr.on_price(NOW, 110.0)  # take profit, re-enter with the next pick
    assert mgr.position.ticker == "AMD"


def test_principal_ticker_picker_falls_back_when_exhausted():
    mgr = ProfitCycleManager(
        ProfitCycleParams(ticker="SPY", principal_dollars=100.0),
        broker=DryRunBroker(),
        principal_ticker_picker=lambda: None,
    )
    assert mgr.next_ticker() == "SPY"


def test_principal_over_hard_ceiling_raises():
    try:
        ProfitCycleManager(ProfitCycleParams(principal_dollars=1000.0, max_principal_dollars=200.0))
        assert False, "expected ValueError"
    except ValueError as e:
        assert "exceeds hard ceiling" in str(e)

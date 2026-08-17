"""Live ORB executor: streams one bar at a time (unlike strategy.generate_trades,
which processes a whole historical day at once) and decides whether to enter,
hold, or exit -- routing every proposed trade through RiskGuard before ever
calling the broker.

Defaults to DryRunBroker. Passing a real broker is a separate, explicit choice
made by the caller -- this module doesn't wire one up itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .broker import Broker, DryRunBroker
from .risk_guard import RiskGuard
from ..strategy import ORBParams


@dataclass
class _TickerState:
    session_day: date | None = None
    range_high: float | None = None
    range_low: float | None = None
    range_locked: bool = False
    position: dict | None = None


@dataclass
class LiveExecutor:
    params: ORBParams
    risk_guard: RiskGuard
    broker: Broker = field(default_factory=DryRunBroker)
    _state: dict[str, _TickerState] = field(default_factory=dict)

    def _ticker_state(self, ticker: str) -> _TickerState:
        return self._state.setdefault(ticker, _TickerState())

    def on_bar(self, ticker: str, timestamp: datetime, bar: dict) -> str:
        """Feed one live bar (open/high/low/close/volume) for `ticker`.

        Returns a short string describing what happened, for logging.
        """
        st = self._ticker_state(ticker)
        today = timestamp.date()

        if st.session_day != today:
            st.session_day = today
            st.range_high = None
            st.range_low = None
            st.range_locked = False
            st.position = None  # any prior position should already be flat by EOD

        session_open = timestamp.replace(hour=9, minute=30, second=0, microsecond=0)

        if not st.range_locked:
            elapsed = (timestamp - session_open).total_seconds() / 60
            if elapsed < self.params.opening_range_minutes:
                st.range_high = bar["high"] if st.range_high is None else max(st.range_high, bar["high"])
                st.range_low = bar["low"] if st.range_low is None else min(st.range_low, bar["low"])
                return "building opening range"
            st.range_locked = True  # this bar is the first one after the opening range -- eligible to enter on

        if st.position is None:
            return self._maybe_enter(ticker, st, timestamp, bar)
        return self._manage_position(ticker, st, timestamp, bar)

    def _maybe_enter(self, ticker: str, st: _TickerState, timestamp: datetime, bar: dict) -> str:
        range_size = st.range_high - st.range_low
        if range_size <= 0:
            return "flat opening range, skipping"

        side = None
        if bar["close"] > st.range_high and self.params.direction in ("both", "long_only"):
            side = "long"
        elif bar["close"] < st.range_low and self.params.direction in ("both", "short_only"):
            side = "short"
        if side is None:
            return "no breakout"

        entry_price = bar["close"]
        stop_price = st.range_low if side == "long" else st.range_high
        target_price = (
            entry_price + self.params.take_profit_r * range_size if side == "long"
            else entry_price - self.params.take_profit_r * range_size
        )

        max_dollars = self.risk_guard.limits.max_position_dollars
        shares = int(max_dollars // entry_price)
        if shares < 1:
            return f"skipped: ${max_dollars:.2f} cap can't buy 1 share of {ticker} at ${entry_price:.2f}"

        proposed_dollars = shares * entry_price
        approved, reason = self.risk_guard.approve_trade(timestamp.date(), proposed_dollars)
        if not approved:
            return f"blocked by risk guard: {reason}"

        order_side = "buy" if side == "long" else "sell_short"
        result = self.broker.place_order(ticker, order_side, shares)
        if not result.accepted:
            return f"broker rejected order: {result.reason}"

        st.position = {
            "side": side, "shares": shares, "entry_price": entry_price,
            "stop_price": stop_price, "target_price": target_price,
        }
        return f"entered {side} {shares} {ticker} @ {entry_price:.2f} (stop {stop_price:.2f}, target {target_price:.2f})"

    def _manage_position(self, ticker: str, st: _TickerState, timestamp: datetime, bar: dict) -> str:
        pos = st.position
        exit_price, exit_reason = None, None

        if pos["side"] == "long":
            if bar["low"] <= pos["stop_price"]:
                exit_price, exit_reason = pos["stop_price"], "stop"
            elif bar["high"] >= pos["target_price"]:
                exit_price, exit_reason = pos["target_price"], "target"
        else:
            if bar["high"] >= pos["stop_price"]:
                exit_price, exit_reason = pos["stop_price"], "stop"
            elif bar["low"] <= pos["target_price"]:
                exit_price, exit_reason = pos["target_price"], "target"

        if exit_price is None and timestamp.time() >= self.params.eod_exit_time:
            exit_price, exit_reason = bar["close"], "eod"

        if exit_price is None:
            return "holding"

        close_side = "sell" if pos["side"] == "long" else "buy_to_cover"
        result = self.broker.place_order(ticker, close_side, pos["shares"])
        pnl = (
            (exit_price - pos["entry_price"]) * pos["shares"] if pos["side"] == "long"
            else (pos["entry_price"] - exit_price) * pos["shares"]
        )
        self.risk_guard.record_fill(timestamp.date(), pnl)
        st.position = None
        accepted_note = "" if result.accepted else f" (broker rejection: {result.reason})"
        return f"exited {ticker} @ {exit_price:.2f} ({exit_reason}), pnl ${pnl:.2f}{accepted_note}"

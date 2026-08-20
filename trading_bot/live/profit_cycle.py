"""Buy-and-hold profit-cycle manager.

Rule: buy a fixed dollar amount of `ticker`; once the position is up
`profit_take_pct`, sell the whole thing; split the realized profit into a
"kept" portion (left as cash -- there is no deposit/withdrawal/transfer
tool available, see docs/live-trading-status.md, so "kept" money is never
moved anywhere, just left uninvested for the user to deal with manually)
and a "reinvest" portion used to buy a different ticker; then immediately
re-buy the original ticker with fresh principal to start the next cycle.

Broker-agnostic (works against any `Broker`, see broker.py). Defaults to
DryRunBroker -- nothing here sends a real order on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from .broker import Broker, DryRunBroker


@dataclass
class ProfitCycleParams:
    ticker: str = "SPY"
    principal_dollars: float = 100.0
    profit_take_pct: float = 0.10
    reinvest_fraction: float = 0.5   # of realized profit; remainder is kept as cash
    max_principal_dollars: float = 200.0        # hard sanity ceiling on principal_dollars
    max_total_reinvested_dollars: float = 500.0  # hard ceiling on cumulative reinvested capital


@dataclass
class CyclePosition:
    ticker: str
    shares: float
    cost_basis: float  # total dollars paid


@dataclass
class ProfitCycleManager:
    params: ProfitCycleParams
    broker: Broker = field(default_factory=DryRunBroker)
    reinvest_ticker_picker: Callable[[], str | None] | None = None
    principal_ticker_picker: Callable[[], str | None] | None = None
    position: CyclePosition | None = field(default=None, init=False)
    reinvested_positions: list[CyclePosition] = field(default_factory=list, init=False)
    kept_cash: float = field(default=0.0, init=False)
    _pending_ticker: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.params.principal_dollars > self.params.max_principal_dollars:
            raise ValueError(
                f"principal_dollars ${self.params.principal_dollars:.2f} exceeds hard ceiling "
                f"${self.params.max_principal_dollars:.2f}"
            )

    def next_ticker(self) -> str:
        """Which ticker `on_price` expects a quote for right now -- call this
        before fetching a quote so you know what to fetch a quote FOR.
        While a position is open, that's always the held ticker. Between
        cycles, if `principal_ticker_picker` is set, it's asked for a fresh
        pick once and cached (falling back to `params.ticker` if it returns
        nothing or raises) so repeated calls -- including the internal one
        `on_price` makes -- can't disagree with each other or re-trigger a
        non-idempotent picker (e.g. a live screener call) twice."""
        if self.position is not None:
            return self.position.ticker
        if self._pending_ticker is not None:
            return self._pending_ticker

        picked = None
        if self.principal_ticker_picker is not None:
            try:
                picked = self.principal_ticker_picker()
            except Exception:
                picked = None
        self._pending_ticker = picked or self.params.ticker
        return self._pending_ticker

    def on_price(self, timestamp: datetime, price: float) -> str:
        """Feed the latest price for whatever `next_ticker()` currently returns."""
        if self.position is None:
            self.params.ticker = self.next_ticker()
            self._pending_ticker = None  # consumed -- next cycle resolves fresh
            return self._enter(price)
        return self._maybe_take_profit(price)

    def _enter(self, price: float) -> str:
        shares = self.params.principal_dollars / price
        result = self.broker.place_order(self.params.ticker, "buy", shares)
        if not result.accepted:
            return f"buy rejected: {result.reason}"
        self.position = CyclePosition(self.params.ticker, shares, self.params.principal_dollars)
        return f"bought {shares:.4f} {self.params.ticker} @ {price:.2f} (${self.params.principal_dollars:.2f})"

    def _maybe_take_profit(self, price: float) -> str:
        pos = self.position
        current_value = pos.shares * price
        gain_pct = (current_value - pos.cost_basis) / pos.cost_basis
        if gain_pct < self.params.profit_take_pct:
            return f"holding {pos.ticker}: {gain_pct:+.2%} (target {self.params.profit_take_pct:.0%})"

        result = self.broker.place_order(pos.ticker, "sell", pos.shares)
        if not result.accepted:
            return f"sell rejected: {result.reason}"

        proceeds = current_value
        profit = proceeds - pos.cost_basis
        reinvest_amount = profit * self.params.reinvest_fraction
        kept_amount = profit - reinvest_amount
        self.kept_cash += kept_amount
        self.position = None

        reinvest_note = self._reinvest(reinvest_amount, price)

        # Next cycle starts immediately with fresh principal. If a ticker
        # picker is set, re-resolve it now that the position is flat -- reuses
        # the just-sold ticker's price as an approximation for the new pick's
        # share count (see _reinvest's docstring note; same known limitation).
        self.params.ticker = self.next_ticker()
        self._pending_ticker = None
        entry_note = self._enter(price)
        return (
            f"sold {pos.ticker} @ {price:.2f} for ${proceeds:.2f} (profit ${profit:.2f}); "
            f"kept ${kept_amount:.2f}{reinvest_note}; next cycle: {entry_note}"
        )

    def _reinvest(self, reinvest_amount: float, price: float) -> str:
        if reinvest_amount <= 0:
            return ""

        already_deployed = sum(p.cost_basis for p in self.reinvested_positions)
        if already_deployed + reinvest_amount > self.params.max_total_reinvested_dollars:
            self.kept_cash += reinvest_amount
            return f", reinvest cap (${self.params.max_total_reinvested_dollars:.2f}) reached -- ${reinvest_amount:.2f} kept as cash instead"

        ticker = self._pick_reinvest_ticker()
        if not ticker:
            self.kept_cash += reinvest_amount
            return f", no reinvest ticker available -- ${reinvest_amount:.2f} kept as cash instead"

        # Reinvest ticker's own price is unknown here (picker returns a symbol,
        # not a quote); approximate using the just-sold ticker's price as a
        # rough share count -- real integration should fetch the actual quote.
        shares = reinvest_amount / price
        result = self.broker.place_order(ticker, "buy", shares)
        if not result.accepted:
            self.kept_cash += reinvest_amount
            return f", reinvest buy failed ({result.reason}) -- ${reinvest_amount:.2f} kept as cash instead"

        self.reinvested_positions.append(CyclePosition(ticker, shares, reinvest_amount))
        return f", reinvested ${reinvest_amount:.2f} into {ticker}"

    def _pick_reinvest_ticker(self) -> str | None:
        if self.reinvest_ticker_picker is None:
            return None
        try:
            return self.reinvest_ticker_picker()
        except Exception:
            return None

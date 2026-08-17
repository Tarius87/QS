"""Hard, non-negotiable risk caps for live execution.

These are deliberately separate from and stricter than the backtest's
`RiskParams` (percent-of-equity sizing) -- they exist to bound worst-case
loss in absolute dollars on a strategy that has NOT been validated against
real market data. Every cap here is a fixed dollar/count limit, not a
percentage, so it can't silently scale up with account size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class LiveRiskLimits:
    max_position_dollars: float = 100.0    # hard cap per trade, regardless of equity or strategy sizing
    max_daily_loss_dollars: float = 150.0  # kill switch: no new trades once today's realized loss hits this
    max_trades_per_day: int = 3


@dataclass
class RiskGuard:
    """Tracks daily state and approves/rejects proposed trades against `limits`."""

    limits: LiveRiskLimits
    _day: date | None = field(default=None, init=False, repr=False)
    _trades_today: int = field(default=0, init=False)
    _daily_pnl: float = field(default=0.0, init=False)

    def _roll_day(self, today: date) -> None:
        if today != self._day:
            self._day = today
            self._trades_today = 0
            self._daily_pnl = 0.0

    def approve_trade(self, today: date, proposed_dollars: float) -> tuple[bool, str]:
        self._roll_day(today)
        if self._daily_pnl <= -self.limits.max_daily_loss_dollars:
            return False, f"daily loss limit reached (${self._daily_pnl:.2f}) -- trading halted for the day"
        if self._trades_today >= self.limits.max_trades_per_day:
            return False, f"max trades per day reached ({self._trades_today})"
        if proposed_dollars > self.limits.max_position_dollars:
            return False, f"position size ${proposed_dollars:.2f} exceeds hard cap ${self.limits.max_position_dollars:.2f}"
        return True, "approved"

    def record_fill(self, today: date, pnl_dollars: float) -> None:
        self._roll_day(today)
        self._trades_today += 1
        self._daily_pnl += pnl_dollars

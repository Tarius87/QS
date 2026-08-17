"""Broker abstraction for live order execution.

No real broker is connected yet. The Robinhood MCP server
(docs/mcp-servers.md) is not attached to this environment's tool set and
its endpoint has not been verified as authentic, so `DryRunBroker` is the
only implementation here. It logs intended orders instead of sending them.

To go live for real: implement a `RobinhoodBroker(Broker)` that calls the
actual, verified Robinhood MCP trading tool, and pass an instance of it to
`LiveExecutor` explicitly. Nothing in this module does that on its own.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OrderResult:
    accepted: bool
    reason: str
    order_id: str | None = None


class Broker(ABC):
    @abstractmethod
    def get_account_equity(self) -> float:
        ...

    @abstractmethod
    def place_order(self, ticker: str, side: str, quantity: float, order_type: str = "market") -> OrderResult:
        ...


@dataclass
class DryRunBroker(Broker):
    """Logs orders instead of sending them. Safe default -- never touches real money."""

    starting_equity: float = 1000.0
    log: list[dict] = field(default_factory=list)

    def get_account_equity(self) -> float:
        return self.starting_equity

    def place_order(self, ticker: str, side: str, quantity: float, order_type: str = "market") -> OrderResult:
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
        }
        self.log.append(entry)
        print(f"[DRY RUN] would {side} {quantity} {ticker} ({order_type}) -- no real order sent")
        return OrderResult(accepted=True, reason="dry_run", order_id=None)

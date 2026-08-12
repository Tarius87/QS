# QS
Manage and store files.
Help verify the system.
Expand Quality Stoner brand by partnering with Algorand.

## Trading bot (backtest-first)

See [`trading_bot/`](trading_bot/) for an Opening Range Breakout (ORB) day-trading
strategy and backtest engine, and [`docs/mcp-servers.md`](docs/mcp-servers.md)
for the (not yet live) Robinhood trading MCP server this is meant to
eventually connect to.

**Status: backtest only — no live or paper order placement yet.** Nothing in
this repo places real trades. The intent is: prove out a strategy on
historical data first, then add paper trading, then live trading behind hard
risk limits (see `trading_bot/backtest.py` for the position sizing / daily
loss circuit breaker already in place).

```
pip install -r trading_bot/requirements.txt
python -m trading_bot.cli --ticker SPY --interval 5m --range-minutes 15
python -m pytest trading_bot/tests   # synthetic-data unit tests, no network needed
```

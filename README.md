# QS
Manage and store files.
Help verify the system.
Expand Quality Stoner brand by partnering with Algorand.

## Trading bot (backtest-first)

See [`trading_bot/`](trading_bot/) for an Opening Range Breakout (ORB) day-trading
strategy and backtest engine, and [`docs/mcp-servers.md`](docs/mcp-servers.md)
for the (not yet live) Robinhood trading MCP server this is meant to
eventually connect to.

**Status: no real order has ever been placed. Nothing in this repo trades
with real money yet.** The strategy has not been validated against real
market data either — the only run so far was against random noise
(`trading_bot/synthetic_check.py`), which is a plumbing check, not evidence
of edge.

```
pip install -r trading_bot/requirements.txt
python -m trading_bot.cli --ticker SPY --interval 5m --range-minutes 15
python -m pytest trading_bot/tests   # synthetic-data unit tests, no network needed
```

### Live execution scaffolding (`trading_bot/live/`)

Built in anticipation of live trading, but **cannot place a real order
today** — there is no broker connected. Specifically:

- `broker.py` — a `Broker` interface and a `DryRunBroker` that logs orders
  instead of sending them. **No real broker implementation exists.** A
  `RobinhoodBroker` would need to be written against the actual MCP tool,
  once one is connected to a session and its endpoint verified as
  authentic (see `docs/mcp-servers.md` — still unresolved).
- `risk_guard.py` — hard, fixed-dollar caps independent of the backtest's
  percent-of-equity sizing, since the strategy is unvalidated: a max
  dollars per position, a max-dollar daily-loss kill switch, and a max
  trades/day. These are non-negotiable gates a proposed trade must pass
  before the executor ever calls the broker.
- `executor.py` — `LiveExecutor` streams one bar at a time, tracks the
  opening range, and decides enter/hold/exit, routing every entry through
  `RiskGuard` first. Defaults to `DryRunBroker`.

What's still missing before this can trade real money:
1. A verified, connected Robinhood (or other) broker implementation of `Broker`
2. A live intraday data feed to call `LiveExecutor.on_bar` with (this
   sandbox can't reach any market data provider — see below)
3. A human decision on the actual dollar values in `LiveRiskLimits` —
   the defaults (`$100`/trade, `$150`/day, 3 trades/day) are placeholders,
   not a recommendation
4. Ideally, real backtest results first — this was explicitly skipped per
   user instruction, not because it doesn't matter

## Signals digest (Congress / Buffett / AI screener)

See [`trading_bot/signals/`](trading_bot/signals/). **Report-only — never
places orders.** Three independent trackers, combined into one printed
report:

- `congress.py` — Senate/House stock disclosures filtered by name (e.g.
  Pelosi). Disclosures lag the actual trade by up to 45 days under the
  STOCK Act. **The President is not covered by this data source** — there
  is no comparable near-real-time trades feed for Trump, so he will not
  show up here regardless of watchlist name.
- `buffett.py` — Berkshire Hathaway 13F filings from SEC EDGAR, diffed
  quarter-over-quarter into new/closed/increased/decreased positions.
  Quarterly, up to a 45-day lag. Reports by issuer name/CUSIP (no
  ticker-mapping dataset used, to avoid mislabeling positions). Set
  `SEC_EDGAR_CONTACT="Your Name your-email@example.com"` before running —
  SEC requires a descriptive User-Agent on EDGAR requests.
- `ai_screener.py` — rules-based screen (52-week-high proximity + volume
  surge + momentum) over an editable watchlist in the file, not open-ended
  "promising stock" discovery.

This sandbox's network policy blocks every data source these modules use
(sec.gov, senate/house disclosure data), so the fetch calls are untested
against the live services — only the parsing/filtering/diffing logic is
covered by unit tests. Run for real from an environment with normal
internet access:

```
python -m trading_bot.signals.digest
```

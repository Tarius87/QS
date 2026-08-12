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

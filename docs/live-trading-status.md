# Live trading status: what's blocking it

Snapshot as of this branch. Nothing below places real trades yet — this
documents exactly why, so it's easy to check off as each piece gets
resolved instead of re-diagnosing from scratch each time.

## 1. Robinhood MCP server is not authenticated

- `robinhood-trading` is registered (`claude mcp add`, done in this
  session's local config), but its status is **"Needs authentication."**
- OAuth requires a browser + a `localhost` redirect callback. This
  session is a non-interactive remote sandbox, so it cannot complete that
  flow — `localhost` here doesn't reach your actual browser, and there is
  no way to hand credentials/codes back to this session to finish it.
- **Fix**: run `claude mcp login robinhood-trading` yourself, either in
  an interactive terminal (locally, where the browser redirect resolves
  naturally) or via `/mcp` inside an interactive Claude Code session. If
  it's meant to work as a claude.ai connector instead, authorize it from
  claude.ai connector settings. Confirm it's done by checking that
  `claude mcp list` no longer shows "Needs authentication."

## 2. No real broker implementation exists

- `trading_bot/live/broker.py` only has `DryRunBroker`, which logs
  intended orders and sends nothing.
- Nothing calls the actual Robinhood MCP trading tools — that code
  (`RobinhoodBroker`) hasn't been written, because there's been no
  authenticated connection to write it against.
- **Fix**: once #1 is resolved and this session (or a new one) can see
  the `robinhood-trading` tools, implement `RobinhoodBroker(Broker)`
  against its real `place_order`/account/quote interface.

## 3. No live market data feed

- `LiveExecutor.on_bar()` needs real-time bars fed in; nothing feeds it
  yet.
- This sandbox's outbound network policy blocks every market-data source
  tried so far: Yahoo Finance, Stooq, Alpha Vantage, Twelve Data,
  Polygon, and SEC EDGAR all return a 403 at the proxy.
- A change to "Full" network access was attempted on the environment,
  but the Yahoo domains were entered into the **Setup script** field
  (which runs shell commands, not a domain allowlist) rather than an
  actual network-access field — that specific attempt didn't take effect
  as intended, and it hasn't been re-verified since.
- **Fix**: either re-check the environment's network access setting is
  actually saved as "Full" (or a correct allowlist) and confirm from a
  **new** session (already-running sessions don't pick up the change),
  or run the data feed from a machine with normal internet access.

## 4. Strategy has never been validated against real data

- The only backtest run so far is `trading_bot/synthetic_check.py`
  against random noise — useful as a plumbing check, not evidence the
  ORB strategy has any edge.
- A real backtest (`python -m trading_bot.cli --ticker SPY ...`) has
  not been run anywhere yet, blocked by the same network restriction as
  #3.
- **Fix**: run it from an environment with real market data access
  (same fix as #3) and share the results.

## 5. Risk limits are placeholders, not reviewed numbers

- `trading_bot/live/risk_guard.py`'s `LiveRiskLimits` defaults
  (`max_position_dollars=100`, `max_daily_loss_dollars=150`,
  `max_trades_per_day=3`) were chosen as reasonable-sounding small
  numbers, not something you've reviewed and approved for your account.
- **Fix**: decide real values before any live run, however small.

## Net effect

All five block real order placement independently — resolving only some
of them still leaves trading impossible. #1–#3 are hard blockers (nothing
can execute without them); #4–#5 are risk/judgment gates that should be
resolved even after #1–#3 are technically fixed.

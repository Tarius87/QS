# Live trading status: what's blocking it

Snapshot as of this branch. Nothing below places real trades yet — this
documents exactly why, so it's easy to check off as each piece gets
resolved instead of re-diagnosing from scratch each time.

## Strategy decision: not day trading

The ORB day-trading strategy (`trading_bot/strategy.py`,
`trading_bot/live/executor.py`) was actually backtested against real SPY
and QQQ data (once network access started working from this session) and
a 72-combination parameter sweep on top of that. Verdict: no real edge —
SPY landed inside the noise floor established by `synthetic_check.py`,
QQQ lost outright, and the few sweep combinations that looked good were
consistent with overfitting to a single ~60-day window, not a durable
edge. **Decision: don't day trade.**

**The active plan is now `trading_bot/live/profit_cycle.py`'s
`ProfitCycleManager`**: buy a fixed dollar amount (default $100), hold it
(no intraday activity), sell the whole position once it's up 10%, split
the profit (half kept as cash, half used to buy a different ticker), then
immediately re-buy to start the next cycle. The ticker to buy each cycle
is chosen by `ai_screener.top_pick()` (momentum screen over
`WATCHLIST`), not a fixed symbol. 31 tests pass, all against
`DryRunBroker` — nothing has bought anything real yet.

A historical sanity run (fixed SPY, before the screener-pick wiring was
added) showed this triggers roughly once every 7-8 months, not
frequently — expectation-setting, not a formal backtest, since buy-and-
hold-until-+10% doesn't have a timing edge to validate the way ORB did.

## 1. Two different Robinhood connections exist; only one is real

- `robinhood-trading` — added via `claude mcp add` / the CLI. Still stuck
  on **"Needs authentication."** OAuth requires a browser + `localhost`
  callback, which this non-interactive sandbox can't complete. This path
  looks like it was the wrong one to begin with.
- `Robinhood` — a separate claude.ai connector that appeared later and
  **is live and authenticated** — confirmed with a real `get_accounts`
  call, which returned two real accounts. Only one of them,
  nicknamed "Agentic," has `agentic_allowed: true` — that's the only
  account any code here could ever act on; the default account is walled
  off by Robinhood's own permission model, not something this repo
  enforces.
- This `Robinhood` connector's tools have been flickering
  (connecting/disconnecting) across this session, which has blocked
  pulling its exact tool schemas (`place_equity_order`,
  `get_equity_quotes`, etc.) to build against.
- **Fix**: next time the `Robinhood` connector's tools are stably
  available, load their schemas and use them — not `robinhood-trading`.

## 2. No real broker implementation exists

- `trading_bot/live/broker.py` only has `DryRunBroker`, which logs
  intended orders and sends nothing. `ProfitCycleManager` and
  `LiveExecutor` both only know this generic interface.
- **Fix**: implement `RobinhoodBroker(Broker)` against the real
  `Robinhood` connector's tools (see #1) once its schema can be read.

## 3. No live quote source wired into ProfitCycleManager

- `ProfitCycleManager.on_price()` needs to be fed a current price for
  whatever `next_ticker()` returns; nothing calls it on a schedule yet.
- Network access for historical/quote data (yfinance) has been working
  from this session as of the last few messages — that part of the
  original blocker may no longer apply. What's still missing is the
  *live* quote lookup (`get_equity_quotes` on the real connector) and
  something to call `on_price()` periodically (this doesn't need to be
  as frequent as ORB's bar-by-bar loop — a daily or even weekly check
  would suit a "wait for +10%" strategy).
- The reinvest-ticker buy also currently approximates the new ticker's
  price using the just-sold ticker's price (see `_reinvest`'s docstring)
  — a real quote lookup is needed there too before any live order.

## 4. Risk parameters are placeholders, not reviewed numbers

- `ProfitCycleParams` defaults (`principal_dollars=100`,
  `profit_take_pct=0.10`, `reinvest_fraction=0.5`,
  `max_principal_dollars=200`, `max_total_reinvested_dollars=500`) match
  what's been discussed, but haven't been given a final explicit go-ahead
  for a real dollar amount going out the door.
- `trading_bot/live/risk_guard.py`'s `LiveRiskLimits` (used by the ORB
  `LiveExecutor`) are no longer the relevant guardrails now that ORB
  isn't the plan — `ProfitCycleParams`'s own ceilings are.

## Net effect

#1–#3 are hard blockers (nothing can execute without them); #4 is a
judgment gate that should be confirmed even after #1–#3 are technically
fixed.

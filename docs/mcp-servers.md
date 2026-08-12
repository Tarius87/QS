# MCP Servers

This document tracks MCP (Model Context Protocol) servers relevant to this
project. Entries here are informational only — none are wired into an active
`.mcp.json` config in this repo. Adding a live connection is a separate,
deliberate step a human should take locally after verifying the endpoint.

## robinhood-trading

- **Transport**: HTTP
- **Endpoint**: `https://agent.robinhood.com/mcp/trading`
- **Purpose**: Exposes Robinhood trading actions (e.g. placing/managing
  orders) to an MCP-compatible agent.
- **Status**: Not enabled in this repository. This server would grant an
  agent the ability to act on a real financial account, so it should only be
  added after the endpoint's authenticity has been verified and with
  explicit human approval at the time of use.

To add it locally once verified, run:

```
claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading
```

This registers the server in your local/user or project Claude Code config
(depending on the `--scope` used) — it does not run automatically just by
being documented here.

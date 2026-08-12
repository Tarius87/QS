"""Consolidated signals digest: congress trades + Buffett/Berkshire 13F
changes + AI stock screen. Prints a report only — never places orders.

Run with: python -m trading_bot.signals.digest
"""

from __future__ import annotations

import pandas as pd

from . import buffett, congress
from .ai_screener import ScreenParams, screen_watchlist

DEFAULT_NAMES = ["Pelosi"]  # Trump is not covered by this data source; see congress.py docstring.


def congress_section(names: list[str] = DEFAULT_NAMES) -> str:
    try:
        df = congress.recent_trades(names)
    except Exception as exc:  # noqa: BLE001
        return f"Congress trades: fetch failed ({exc})"
    if df.empty:
        return "Congress trades: no matching disclosures found."
    cols = [c for c in ["transaction_date", "senator", "representative", "ticker", "asset_description", "type", "chamber"] if c in df.columns]
    return "Congress trades (most recent disclosures):\n" + df[cols].head(20).to_string(index=False)


def buffett_section() -> str:
    try:
        accessions = buffett.latest_13f_accessions(count=2)
        if len(accessions) < 2:
            return "Buffett/Berkshire 13F: not enough filings found to diff."
        curr = buffett.fetch_infotable(accessions[0])
        prev = buffett.fetch_infotable(accessions[1])
    except Exception as exc:  # noqa: BLE001
        return f"Buffett/Berkshire 13F: fetch failed ({exc})"

    diff = buffett.diff_holdings(prev, curr)
    changed = diff[diff["action"] != "unchanged"]
    if changed.empty:
        return "Buffett/Berkshire 13F: no changes between the two most recent filings."
    cols = ["name_of_issuer", "cusip", "action", "prev_shares", "shares", "share_delta"]
    return "Buffett/Berkshire 13F changes (most recent quarter vs prior):\n" + changed[cols].head(20).to_string(index=False)


def ai_screen_section(params: ScreenParams | None = None) -> str:
    try:
        df = screen_watchlist(params=params)
    except Exception as exc:  # noqa: BLE001
        return f"AI stock screen: fetch failed ({exc})"
    if df.empty:
        return "AI stock screen: no watchlist tickers currently meet all criteria."
    return "AI stock screen (watchlist tickers meeting all criteria):\n" + df.to_string(index=False)


def main():
    print("=" * 70)
    print("SIGNALS DIGEST — informational only, no orders placed")
    print("=" * 70)
    for section in (congress_section(), buffett_section(), ai_screen_section()):
        print()
        print(section)


if __name__ == "__main__":
    main()

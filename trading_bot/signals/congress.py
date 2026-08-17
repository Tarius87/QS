"""Congressional stock trade disclosures (Pelosi, and members of Congress
generally). Signal-only: this module never places orders.

Important limits, read before relying on this:
  - Disclosures under the STOCK Act can lag the actual trade by up to 45
    days. This is not a real-time feed.
  - The President is NOT covered by these periodic transaction reports —
    there is no equivalent near-real-time "trades" feed for Trump. His
    disclosure is an annual OGE-278 financial report, far coarser. Don't
    expect this module to surface his trades; it can't.
  - The public data source (*Stock Watcher) endpoints below could not be
    verified from this sandbox (network policy blocks the relevant
    domains). Sanity-check `SENATE_DATA_URL` / `HOUSE_DATA_URL` still
    resolve when you run this for real, and adjust if the project has
    moved.
"""

from __future__ import annotations

import requests
import pandas as pd

SENATE_DATA_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
HOUSE_DATA_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"


def fetch_senate_transactions() -> list[dict]:
    resp = requests.get(SENATE_DATA_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_house_transactions() -> list[dict]:
    resp = requests.get(HOUSE_DATA_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _to_frame(records: list[dict], chamber: str) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df["chamber"] = chamber
    return df


def filter_by_name(records: list[dict], name: str, name_field: str = "senator") -> pd.DataFrame:
    """Pure filter: case-insensitive substring match on `name_field`.

    Works on raw Senate/House Stock Watcher records (list of dicts) so it
    can be unit-tested without any network call.
    """
    df = pd.DataFrame(records)
    if df.empty or name_field not in df.columns:
        return pd.DataFrame()
    mask = df[name_field].astype(str).str.contains(name, case=False, na=False)
    matches = df[mask].copy()
    if "transaction_date" in matches.columns:
        matches = matches.sort_values("transaction_date", ascending=False)
    return matches


def recent_trades(names: list[str], senate_records: list[dict] | None = None,
                   house_records: list[dict] | None = None) -> pd.DataFrame:
    """Combine Senate + House disclosures and filter to `names`.

    Pass pre-fetched `senate_records`/`house_records` for testing; omit to
    fetch live (network required).
    """
    senate_records = senate_records if senate_records is not None else fetch_senate_transactions()
    house_records = house_records if house_records is not None else fetch_house_transactions()

    frames = []
    for name in names:
        s = filter_by_name(senate_records, name, name_field="senator")
        if not s.empty:
            frames.append(_to_frame(s.to_dict("records"), "senate"))
        h = filter_by_name(house_records, name, name_field="representative")
        if not h.empty:
            frames.append(_to_frame(h.to_dict("records"), "house"))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

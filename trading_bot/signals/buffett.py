"""Berkshire Hathaway 13F tracker (Buffett's disclosed holdings). Signal-only:
this module never places orders.

Important limits:
  - 13F filings are quarterly and can lag the actual trades by up to 45 days
    after quarter-end. Not real-time.
  - 13F line items identify securities by CUSIP + issuer name, not ticker.
    There's no free, reliable CUSIP->ticker mapping used here, so results
    are reported by issuer name/CUSIP as filed rather than guessing tickers.
  - SEC EDGAR requires a descriptive User-Agent identifying who's making the
    request (https://www.sec.gov/os/webmaster-faq#developers). Set the
    SEC_EDGAR_CONTACT env var to "Your Name your-email@example.com" before
    fetching live; a placeholder is used otherwise and EDGAR may reject it.
  - This sandbox's network policy blocks sec.gov, so the fetch functions
    here are untested against the live API. The parsing/diff logic is
    covered by unit tests using synthetic filings instead.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import requests
import pandas as pd

BERKSHIRE_CIK = "0001067983"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"
ARCHIVE_FILE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{filename}"


def _headers() -> dict:
    contact = os.environ.get("SEC_EDGAR_CONTACT", "QS trading_bot contact-not-set@example.com")
    return {"User-Agent": contact}


def latest_13f_accessions(cik: str = BERKSHIRE_CIK, count: int = 2) -> list[str]:
    """Return the `count` most recent 13F-HR accession numbers (newest first)."""
    resp = requests.get(SUBMISSIONS_URL.format(cik=cik), headers=_headers(), timeout=30)
    resp.raise_for_status()
    recent = resp.json()["filings"]["recent"]
    accessions = [
        acc for acc, form in zip(recent["accessionNumber"], recent["form"])
        if form == "13F-HR"
    ]
    return accessions[:count]


def fetch_infotable(accession_number: str, cik: str = BERKSHIRE_CIK) -> pd.DataFrame:
    """Fetch and parse the 13F information table for one filing."""
    cik_int = str(int(cik))
    accession_nodash = accession_number.replace("-", "")

    idx_resp = requests.get(
        ARCHIVE_INDEX_URL.format(cik_int=cik_int, accession_nodash=accession_nodash),
        headers=_headers(), timeout=30,
    )
    idx_resp.raise_for_status()
    files = idx_resp.json()["directory"]["item"]
    infotable_name = next(f["name"] for f in files if "infotable" in f["name"].lower() and f["name"].endswith(".xml"))

    xml_resp = requests.get(
        ARCHIVE_FILE_URL.format(cik_int=cik_int, accession_nodash=accession_nodash, filename=infotable_name),
        headers=_headers(), timeout=30,
    )
    xml_resp.raise_for_status()
    return parse_infotable_xml(xml_resp.text)


def parse_infotable_xml(xml_text: str) -> pd.DataFrame:
    """Pure parser: 13F infoTable XML -> DataFrame. Unit-testable without network."""
    root = ET.fromstring(xml_text)
    ns = {"n": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}

    def tag(elem, name):
        return elem.find(f"n:{name}", ns) if ns else elem.find(name)

    rows = []
    entries = root.findall(".//n:infoTable", ns) if ns else root.findall(".//infoTable")
    for entry in entries:
        shares_elem = tag(tag(entry, "shrsOrPrnAmt"), "sshPrnamt")
        rows.append({
            "name_of_issuer": tag(entry, "nameOfIssuer").text,
            "cusip": tag(entry, "cusip").text,
            "value_thousands": float(tag(entry, "value").text),
            "shares": float(shares_elem.text) if shares_elem is not None else None,
        })
    return pd.DataFrame(rows)


def diff_holdings(prev: pd.DataFrame, curr: pd.DataFrame) -> pd.DataFrame:
    """Compare two quarters' holdings by CUSIP and classify each change.

    Pure function, unit-testable with synthetic DataFrames.
    """
    if prev.empty:
        merged = curr.copy()
        merged["prev_shares"] = 0.0
    else:
        merged = curr.merge(
            prev[["cusip", "shares"]].rename(columns={"shares": "prev_shares"}),
            on="cusip", how="outer",
        )
        merged["name_of_issuer"] = merged["name_of_issuer"].fillna(
            merged["cusip"].map(prev.set_index("cusip")["name_of_issuer"]) if not prev.empty else None
        )
        merged["prev_shares"] = merged["prev_shares"].fillna(0.0)
        merged["shares"] = merged["shares"].fillna(0.0)

    merged["share_delta"] = merged["shares"] - merged["prev_shares"]

    def classify(row):
        if row["prev_shares"] == 0 and row["shares"] > 0:
            return "new_position"
        if row["shares"] == 0 and row["prev_shares"] > 0:
            return "closed_position"
        if row["share_delta"] > 0:
            return "increased"
        if row["share_delta"] < 0:
            return "decreased"
        return "unchanged"

    merged["action"] = merged.apply(classify, axis=1)
    return merged.sort_values("share_delta", key=abs, ascending=False)

import pandas as pd

from trading_bot.signals.buffett import diff_holdings, parse_infotable_xml

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>150000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>900000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>BANK OF AMERICA CORP</nameOfIssuer>
    <cusip>060505104</cusip>
    <value>30000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>1000000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
</informationTable>
"""


def test_parse_infotable_xml():
    df = parse_infotable_xml(SAMPLE_XML)
    assert len(df) == 2
    assert set(df["name_of_issuer"]) == {"APPLE INC", "BANK OF AMERICA CORP"}
    aapl = df[df["cusip"] == "037833100"].iloc[0]
    assert aapl["shares"] == 900_000_000
    assert aapl["value_thousands"] == 150_000_000


def test_diff_holdings_classifies_changes():
    prev = pd.DataFrame([
        {"name_of_issuer": "APPLE INC", "cusip": "037833100", "shares": 1_000_000_000, "value_thousands": 1},
        {"name_of_issuer": "OLD CO", "cusip": "999999999", "shares": 500_000, "value_thousands": 1},
    ])
    curr = pd.DataFrame([
        {"name_of_issuer": "APPLE INC", "cusip": "037833100", "shares": 900_000_000, "value_thousands": 1},
        {"name_of_issuer": "NEW CO", "cusip": "111111111", "shares": 200_000, "value_thousands": 1},
    ])

    diff = diff_holdings(prev, curr)
    actions = dict(zip(diff["cusip"], diff["action"]))

    assert actions["037833100"] == "decreased"
    assert actions["999999999"] == "closed_position"
    assert actions["111111111"] == "new_position"


def test_diff_holdings_first_filing_all_new():
    curr = pd.DataFrame([
        {"name_of_issuer": "APPLE INC", "cusip": "037833100", "shares": 900_000_000, "value_thousands": 1},
    ])
    diff = diff_holdings(pd.DataFrame(), curr)
    assert diff.iloc[0]["action"] == "new_position"

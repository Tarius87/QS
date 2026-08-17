from trading_bot.signals.congress import filter_by_name

SENATE_RECORDS = [
    {"senator": "Nancy Pelosi", "ticker": "NVDA", "transaction_date": "2024-01-10", "type": "Purchase"},
    {"senator": "Chuck Schumer", "ticker": "AAPL", "transaction_date": "2024-01-05", "type": "Sale"},
    {"senator": "Nancy Pelosi", "ticker": "MSFT", "transaction_date": "2024-02-01", "type": "Sale"},
]


def test_filter_by_name_matches_case_insensitively():
    result = filter_by_name(SENATE_RECORDS, "pelosi", name_field="senator")
    assert len(result) == 2
    assert set(result["ticker"]) == {"NVDA", "MSFT"}


def test_filter_by_name_sorts_most_recent_first():
    result = filter_by_name(SENATE_RECORDS, "pelosi", name_field="senator")
    dates = result["transaction_date"].tolist()
    assert dates == sorted(dates, reverse=True)


def test_filter_by_name_no_match_returns_empty():
    result = filter_by_name(SENATE_RECORDS, "nobody", name_field="senator")
    assert result.empty


def test_filter_by_name_missing_field_returns_empty():
    result = filter_by_name(SENATE_RECORDS, "pelosi", name_field="representative")
    assert result.empty

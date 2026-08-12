import pandas as pd

from trading_bot.signals.ai_screener import ScreenParams, screen_ticker


def _flat_price_df(days=280, price=100.0, volume=1_000_000):
    idx = pd.date_range("2023-01-01", periods=days, freq="B")
    return pd.DataFrame(
        {"open": price, "high": price, "low": price, "close": price, "volume": volume},
        index=idx,
    )


def test_screen_ticker_passes_all_criteria():
    df = _flat_price_df()
    # Momentum leg: price rises from 100 -> 120 over the last 20 sessions, ending at/near the 52w high.
    df.loc[df.index[-21]:, "close"] = [100 + i * 1.0 for i in range(21)]
    df.loc[df.index[-21]:, "high"] = df.loc[df.index[-21]:, "close"]
    df.loc[df.index[-1], "volume"] = 5_000_000  # surge on the last bar

    result = screen_ticker(df, ScreenParams())
    assert result is not None
    assert result["momentum_pct"] >= 10.0
    assert result["volume_vs_20d_avg"] >= 1.5


def test_screen_ticker_fails_without_momentum():
    df = _flat_price_df()
    df.loc[df.index[-1], "volume"] = 5_000_000  # surge but no momentum or proximity to high
    result = screen_ticker(df, ScreenParams())
    assert result is None


def test_screen_ticker_fails_without_enough_history():
    df = _flat_price_df(days=10)
    result = screen_ticker(df, ScreenParams())
    assert result is None

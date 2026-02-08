"""Unit tests for Yahoo Finance fetcher.

NOTE: Tests that call Yahoo Finance require internet access.
They are marked with @pytest.mark.network so you can skip them
with: pytest -v -m "not network"
"""
import pytest
import pandas as pd
from app.fetcher import get_monthly_prices, get_dividends, fetch_all_tickers, FetcherError


class TestGetMonthlyPrices:
    """Tests for single-ticker price fetching."""

    @pytest.mark.network
    def test_fetch_aapl_returns_data(self):
        """Fetching AAPL returns a non-empty DataFrame."""
        df = get_monthly_prices("AAPL", start_date="2024-01-01", end_date="2024-12-31")
        assert not df.empty
        assert len(df) > 0

    @pytest.mark.network
    def test_returns_expected_columns(self):
        """Result has all required columns."""
        df = get_monthly_prices("AAPL", start_date="2024-01-01", end_date="2024-06-30")
        expected_cols = {"year", "month", "high", "low", "close", "adj_close"}
        assert expected_cols.issubset(set(df.columns))

    @pytest.mark.network
    def test_year_month_values_reasonable(self):
        """Year and month values are within expected range."""
        df = get_monthly_prices("AAPL", start_date="2024-01-01", end_date="2024-06-30")
        assert (df["year"] == 2024).all()
        assert df["month"].min() >= 1
        assert df["month"].max() <= 12

    @pytest.mark.network
    def test_prices_are_positive(self):
        """All price values should be positive."""
        df = get_monthly_prices("AAPL", start_date="2024-01-01", end_date="2024-06-30")
        assert (df["high"] > 0).all()
        assert (df["low"] > 0).all()
        assert (df["close"] > 0).all()

    @pytest.mark.network
    def test_high_greater_equal_low(self):
        """Monthly high should be >= low."""
        df = get_monthly_prices("AAPL", start_date="2024-01-01", end_date="2024-06-30")
        assert (df["high"] >= df["low"]).all()

    @pytest.mark.network
    def test_no_duplicate_year_month(self):
        """No duplicate year+month combinations."""
        df = get_monthly_prices("AAPL", start_date="2023-01-01", end_date="2024-12-31")
        dupes = df.duplicated(subset=["year", "month"], keep=False)
        assert not dupes.any()

    @pytest.mark.network
    def test_invalid_ticker_raises_or_empty(self):
        """Invalid ticker returns empty DataFrame or raises FetcherError."""
        try:
            df = get_monthly_prices("ZZZZXXX123")
            assert df.empty
        except FetcherError:
            pass  # Also acceptable

    @pytest.mark.network
    def test_full_history_has_many_records(self):
        """Full history for a well-known stock should have many months."""
        df = get_monthly_prices("AAPL")
        assert len(df) > 50  # 20 years = ~240 months, but be conservative


class TestGetDividends:
    """Tests for single-ticker dividend fetching."""

    @pytest.mark.network
    def test_fetch_aapl_dividends(self):
        """AAPL pays dividends - should return data."""
        df = get_dividends("AAPL", start_date="2023-01-01", end_date="2024-12-31")
        assert not df.empty

    @pytest.mark.network
    def test_dividend_columns(self):
        """Result has pay_date and amount columns."""
        df = get_dividends("AAPL", start_date="2023-01-01", end_date="2024-12-31")
        assert "pay_date" in df.columns
        assert "amount" in df.columns

    @pytest.mark.network
    def test_dividend_amounts_positive(self):
        """Dividend amounts should be positive."""
        df = get_dividends("AAPL", start_date="2023-01-01", end_date="2024-12-31")
        if not df.empty:
            assert (df["amount"] > 0).all()

    @pytest.mark.network
    def test_no_dividend_ticker(self):
        """A stock that doesn't pay dividends returns empty DataFrame."""
        # AMZN historically doesn't pay dividends (though this could change)
        df = get_dividends("AMZN", start_date="2020-01-01", end_date="2023-12-31")
        # Either empty or very few - just check it doesn't error
        assert isinstance(df, pd.DataFrame)

    @pytest.mark.network
    def test_no_duplicate_pay_dates(self):
        """No duplicate pay dates."""
        df = get_dividends("AAPL", start_date="2020-01-01", end_date="2024-12-31")
        if not df.empty:
            dupes = df.duplicated(subset=["pay_date"], keep=False)
            assert not dupes.any()


class TestFetchAllTickers:
    """Tests for multi-ticker batch fetching."""

    @pytest.mark.network
    def test_fetch_multiple_tickers(self):
        """Fetching multiple tickers returns data for each."""
        results = fetch_all_tickers(["AAPL", "MSFT"], mode="incremental", delay_seconds=0.5)
        assert "AAPL" in results["prices"]
        assert "MSFT" in results["prices"]
        assert "AAPL" in results["dividends"]
        assert "MSFT" in results["dividends"]

    @pytest.mark.network
    def test_errors_captured_not_raised(self):
        """Invalid tickers go to errors dict, don't crash the batch."""
        results = fetch_all_tickers(
            ["AAPL", "ZZZZXXX123"],
            mode="incremental",
            delay_seconds=0.5,
        )
        assert "AAPL" in results["prices"]
        # Invalid ticker either in errors or has empty data
        assert isinstance(results["errors"], dict)

    def test_empty_list_raises(self):
        """Empty ticker list raises FetcherError."""
        with pytest.raises(FetcherError):
            fetch_all_tickers([])

    def test_exceeds_max_tickers_raises(self):
        """Exceeding MAX_TICKERS raises FetcherError."""
        symbols = [f"FAKE{i}" for i in range(51)]
        with pytest.raises(FetcherError):
            fetch_all_tickers(symbols)

    @pytest.mark.network
    def test_incremental_mode_limited_data(self):
        """Incremental mode returns only recent months."""
        results = fetch_all_tickers(["AAPL"], mode="incremental", delay_seconds=0)
        df = results["prices"]["AAPL"]
        if not df.empty:
            assert len(df) <= 3  # At most 2-3 months of data

    @pytest.mark.network
    def test_full_mode_returns_history(self):
        """Full mode returns extensive history."""
        results = fetch_all_tickers(["AAPL"], mode="full", delay_seconds=0)
        df = results["prices"]["AAPL"]
        assert len(df) > 50

    @pytest.mark.network
    def test_result_structure(self):
        """Result has prices, dividends, and errors keys."""
        results = fetch_all_tickers(["AAPL"], mode="incremental", delay_seconds=0)
        assert "prices" in results
        assert "dividends" in results
        assert "errors" in results

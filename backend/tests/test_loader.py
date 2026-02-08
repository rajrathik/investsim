"""Unit tests for database loader.

These tests use in-memory SQLite - no network or SQL Server needed.
"""
import pytest
import pandas as pd
from datetime import date
from app.models import Ticker, MonthlyPrice, Dividend
from app.loader import (
    get_active_tickers,
    get_ticker_id,
    load_prices,
    load_dividends,
    load_all,
)


class TestGetActiveTickers:
    """Tests for retrieving active tickers."""

    def test_returns_active_only(self, db_session):
        """Only active tickers are returned."""
        db_session.add(Ticker(symbol="AAPL", active=True))
        db_session.add(Ticker(symbol="MSFT", active=True))
        db_session.add(Ticker(symbol="GOOG", active=False))
        db_session.commit()

        result = get_active_tickers(db_session)
        assert "AAPL" in result
        assert "MSFT" in result
        assert "GOOG" not in result

    def test_empty_table(self, db_session):
        """Empty tickers table returns empty list."""
        result = get_active_tickers(db_session)
        assert result == []


class TestGetTickerId:
    """Tests for ticker ID lookup."""

    def test_existing_ticker(self, db_session):
        """Returns ID for existing ticker."""
        ticker = Ticker(symbol="AAPL")
        db_session.add(ticker)
        db_session.commit()

        result = get_ticker_id(db_session, "AAPL")
        assert result == ticker.id

    def test_nonexistent_ticker(self, db_session):
        """Returns None for non-existent ticker."""
        result = get_ticker_id(db_session, "ZZZZZ")
        assert result is None

    def test_case_insensitive(self, db_session):
        """Lookup is case-insensitive."""
        db_session.add(Ticker(symbol="AAPL"))
        db_session.commit()

        result = get_ticker_id(db_session, "aapl")
        assert result is not None


class TestLoadPrices:
    """Tests for loading price data."""

    def _setup_ticker(self, db_session, symbol="AAPL"):
        ticker = Ticker(symbol=symbol)
        db_session.add(ticker)
        db_session.commit()
        return ticker

    def _make_prices_df(self, rows):
        return pd.DataFrame(rows, columns=["year", "month", "high", "low", "close", "adj_close"])

    def test_insert_prices(self, db_session):
        """Prices are inserted into the database."""
        self._setup_ticker(db_session)
        df = self._make_prices_df([
            [2024, 1, 195.0, 180.0, 190.0, 189.5],
            [2024, 2, 200.0, 185.0, 195.0, 194.5],
        ])

        counts = load_prices(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 2
        assert counts["updated"] == 0
        assert counts["skipped"] == 0

        assert db_session.query(MonthlyPrice).count() == 2

    def test_full_mode_skips_existing(self, db_session):
        """Full mode skips records that already exist."""
        ticker = self._setup_ticker(db_session)
        db_session.add(MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=195.0, low=180.0, close=190.0
        ))
        db_session.commit()

        df = self._make_prices_df([
            [2024, 1, 999.0, 999.0, 999.0, 999.0],  # Existing - should skip
            [2024, 2, 200.0, 185.0, 195.0, 194.5],   # New - should insert
        ])

        counts = load_prices(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 1
        assert counts["skipped"] == 1

        # Verify original data not overwritten
        existing = db_session.query(MonthlyPrice).filter_by(year=2024, month=1).first()
        assert existing.close == 190.0  # Original value, not 999

    def test_incremental_mode_updates_existing(self, db_session):
        """Incremental mode updates records that already exist."""
        ticker = self._setup_ticker(db_session)
        db_session.add(MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=195.0, low=180.0, close=190.0
        ))
        db_session.commit()

        df = self._make_prices_df([
            [2024, 1, 198.0, 182.0, 196.0, 195.5],  # Updated values
        ])

        counts = load_prices(db_session, "AAPL", df, mode="incremental")
        assert counts["updated"] == 1

        updated = db_session.query(MonthlyPrice).filter_by(year=2024, month=1).first()
        assert updated.close == 196.0
        assert updated.adj_close == 195.5

    def test_empty_dataframe(self, db_session):
        """Empty DataFrame returns zero counts."""
        self._setup_ticker(db_session)
        df = pd.DataFrame()

        counts = load_prices(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 0

    def test_unknown_ticker(self, db_session):
        """Unknown ticker returns error."""
        df = self._make_prices_df([[2024, 1, 195.0, 180.0, 190.0, 189.5]])

        counts = load_prices(db_session, "ZZZZ", df, mode="full")
        assert "error" in counts

    def test_load_twelve_months(self, db_session):
        """Can load a full year of monthly data."""
        self._setup_ticker(db_session)
        rows = [[2024, m, 100.0+m, 90.0+m, 95.0+m, 94.5+m] for m in range(1, 13)]
        df = self._make_prices_df(rows)

        counts = load_prices(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 12
        assert db_session.query(MonthlyPrice).count() == 12


class TestLoadDividends:
    """Tests for loading dividend data."""

    def _setup_ticker(self, db_session, symbol="AAPL"):
        ticker = Ticker(symbol=symbol)
        db_session.add(ticker)
        db_session.commit()
        return ticker

    def _make_divs_df(self, rows):
        return pd.DataFrame(rows, columns=["pay_date", "amount"])

    def test_insert_dividends(self, db_session):
        """Dividends are inserted into the database."""
        self._setup_ticker(db_session)
        df = self._make_divs_df([
            [date(2024, 2, 15), 0.24],
            [date(2024, 5, 16), 0.25],
        ])

        counts = load_dividends(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 2
        assert db_session.query(Dividend).count() == 2

    def test_full_mode_skips_existing(self, db_session):
        """Full mode skips existing dividends."""
        ticker = self._setup_ticker(db_session)
        db_session.add(Dividend(
            ticker_id=ticker.id, pay_date=date(2024, 2, 15), amount=0.24
        ))
        db_session.commit()

        df = self._make_divs_df([
            [date(2024, 2, 15), 0.99],  # Existing - should skip
            [date(2024, 5, 16), 0.25],  # New - should insert
        ])

        counts = load_dividends(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 1
        assert counts["skipped"] == 1

        existing = db_session.query(Dividend).filter_by(pay_date=date(2024, 2, 15)).first()
        assert existing.amount == 0.24  # Original, not 0.99

    def test_incremental_mode_updates_existing(self, db_session):
        """Incremental mode updates existing dividends."""
        ticker = self._setup_ticker(db_session)
        db_session.add(Dividend(
            ticker_id=ticker.id, pay_date=date(2024, 2, 15), amount=0.24
        ))
        db_session.commit()

        df = self._make_divs_df([
            [date(2024, 2, 15), 0.26],  # Updated amount
        ])

        counts = load_dividends(db_session, "AAPL", df, mode="incremental")
        assert counts["updated"] == 1

        updated = db_session.query(Dividend).filter_by(pay_date=date(2024, 2, 15)).first()
        assert updated.amount == 0.26

    def test_empty_dataframe(self, db_session):
        """Empty DataFrame returns zero counts."""
        self._setup_ticker(db_session)
        df = pd.DataFrame()

        counts = load_dividends(db_session, "AAPL", df, mode="full")
        assert counts["inserted"] == 0

    def test_unknown_ticker(self, db_session):
        """Unknown ticker returns error."""
        df = self._make_divs_df([[date(2024, 2, 15), 0.24]])

        counts = load_dividends(db_session, "ZZZZ", df, mode="full")
        assert "error" in counts


class TestLoadAll:
    """Tests for the combined load function."""

    def _setup_ticker(self, db_session, symbol="AAPL"):
        ticker = Ticker(symbol=symbol)
        db_session.add(ticker)
        db_session.commit()
        return ticker

    def test_load_all_combined(self, db_session):
        """Loads both prices and dividends from fetch results."""
        self._setup_ticker(db_session, "AAPL")
        self._setup_ticker(db_session, "MSFT")

        fetch_results = {
            "prices": {
                "AAPL": pd.DataFrame({
                    "year": [2024], "month": [1],
                    "high": [195.0], "low": [180.0],
                    "close": [190.0], "adj_close": [189.5],
                }),
                "MSFT": pd.DataFrame({
                    "year": [2024], "month": [1],
                    "high": [420.0], "low": [400.0],
                    "close": [415.0], "adj_close": [414.5],
                }),
            },
            "dividends": {
                "AAPL": pd.DataFrame({
                    "pay_date": [date(2024, 2, 15)],
                    "amount": [0.24],
                }),
                "MSFT": pd.DataFrame({
                    "pay_date": [date(2024, 3, 14)],
                    "amount": [0.75],
                }),
            },
            "errors": {},
        }

        summary = load_all(db_session, fetch_results, mode="full")
        assert summary["AAPL"]["prices"]["inserted"] == 1
        assert summary["AAPL"]["dividends"]["inserted"] == 1
        assert summary["MSFT"]["prices"]["inserted"] == 1
        assert summary["MSFT"]["dividends"]["inserted"] == 1

        assert db_session.query(MonthlyPrice).count() == 2
        assert db_session.query(Dividend).count() == 2

    def test_load_all_with_fetch_errors(self, db_session):
        """Fetch errors are included in summary."""
        self._setup_ticker(db_session, "AAPL")

        fetch_results = {
            "prices": {
                "AAPL": pd.DataFrame({
                    "year": [2024], "month": [1],
                    "high": [195.0], "low": [180.0],
                    "close": [190.0], "adj_close": [189.5],
                }),
            },
            "dividends": {
                "AAPL": pd.DataFrame(),
            },
            "errors": {
                "BADTICKER": "Failed to fetch",
            },
        }

        summary = load_all(db_session, fetch_results, mode="full")
        assert "error" in summary["BADTICKER"]
        assert summary["AAPL"]["prices"]["inserted"] == 1

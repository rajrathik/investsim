"""Unit tests for database models."""
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Ticker, MonthlyPrice


class TestTickerModel:
    """Tests for the Ticker model."""

    def test_create_ticker(self, db_session):
        """A ticker can be created with symbol and name."""
        ticker = Ticker(symbol="AAPL", name="Apple Inc.")
        db_session.add(ticker)
        db_session.commit()

        result = db_session.query(Ticker).filter_by(symbol="AAPL").first()
        assert result is not None
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.active is True  # default

    def test_ticker_symbol_unique(self, db_session):
        """Duplicate ticker symbols are rejected."""
        db_session.add(Ticker(symbol="AAPL", name="Apple Inc."))
        db_session.commit()

        db_session.add(Ticker(symbol="AAPL", name="Apple Duplicate"))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_ticker_symbol_required(self, db_session):
        """Ticker symbol cannot be null."""
        ticker = Ticker(symbol=None, name="No Symbol")
        db_session.add(ticker)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_ticker_active_default(self, db_session):
        """Active flag defaults to True."""
        ticker = Ticker(symbol="MSFT")
        db_session.add(ticker)
        db_session.commit()

        result = db_session.query(Ticker).filter_by(symbol="MSFT").first()
        assert result.active is True

    def test_ticker_deactivate(self, db_session):
        """A ticker can be deactivated."""
        ticker = Ticker(symbol="MSFT", active=True)
        db_session.add(ticker)
        db_session.commit()

        ticker.active = False
        db_session.commit()

        result = db_session.query(Ticker).filter_by(symbol="MSFT").first()
        assert result.active is False

    def test_ticker_repr(self, db_session):
        """Ticker has a useful string representation."""
        ticker = Ticker(symbol="GOOG", active=True)
        assert "GOOG" in repr(ticker)

    def test_create_multiple_tickers(self, db_session):
        """Multiple distinct tickers can be created."""
        symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA"]
        for s in symbols:
            db_session.add(Ticker(symbol=s))
        db_session.commit()

        count = db_session.query(Ticker).count()
        assert count == 5


class TestMonthlyPriceModel:
    """Tests for the MonthlyPrice model."""

    def _create_ticker(self, db_session, symbol="AAPL"):
        """Helper to create and return a ticker."""
        ticker = Ticker(symbol=symbol, name=f"{symbol} Inc.")
        db_session.add(ticker)
        db_session.commit()
        return ticker

    def test_create_monthly_price(self, db_session):
        """A monthly price record can be created."""
        ticker = self._create_ticker(db_session)
        price = MonthlyPrice(
            ticker_id=ticker.id,
            year=2024, month=1,
            high=195.0, low=180.0, close=190.0,
            dividend=0.24
        )
        db_session.add(price)
        db_session.commit()

        result = db_session.query(MonthlyPrice).first()
        assert result.year == 2024
        assert result.month == 1
        assert result.high == 195.0
        assert result.low == 180.0
        assert result.close == 190.0
        assert result.dividend == 0.24

    def test_no_duplicate_ticker_year_month(self, db_session):
        """Same ticker + year + month combination is rejected."""
        ticker = self._create_ticker(db_session)

        price1 = MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=195.0, low=180.0, close=190.0
        )
        db_session.add(price1)
        db_session.commit()

        price2 = MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=200.0, low=185.0, close=195.0
        )
        db_session.add(price2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_different_months_allowed(self, db_session):
        """Same ticker can have prices for different months."""
        ticker = self._create_ticker(db_session)
        for month in range(1, 13):
            db_session.add(MonthlyPrice(
                ticker_id=ticker.id, year=2024, month=month,
                high=100.0 + month, low=90.0 + month, close=95.0 + month
            ))
        db_session.commit()

        count = db_session.query(MonthlyPrice).filter_by(ticker_id=ticker.id).count()
        assert count == 12

    def test_different_tickers_same_month_allowed(self, db_session):
        """Different tickers can have prices for the same month."""
        t1 = self._create_ticker(db_session, "AAPL")
        t2 = self._create_ticker(db_session, "MSFT")

        db_session.add(MonthlyPrice(
            ticker_id=t1.id, year=2024, month=6,
            high=195.0, low=180.0, close=190.0
        ))
        db_session.add(MonthlyPrice(
            ticker_id=t2.id, year=2024, month=6,
            high=420.0, low=400.0, close=415.0
        ))
        db_session.commit()

        count = db_session.query(MonthlyPrice).count()
        assert count == 2

    def test_dividend_defaults_to_zero(self, db_session):
        """Dividend defaults to 0.0 if not provided."""
        ticker = self._create_ticker(db_session)
        price = MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=3,
            high=150.0, low=140.0, close=145.0
        )
        db_session.add(price)
        db_session.commit()

        result = db_session.query(MonthlyPrice).first()
        assert result.dividend == 0.0

    def test_relationship_ticker_to_prices(self, db_session):
        """Ticker.prices returns related MonthlyPrice records."""
        ticker = self._create_ticker(db_session)
        db_session.add(MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=195.0, low=180.0, close=190.0
        ))
        db_session.add(MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=2,
            high=200.0, low=185.0, close=195.0
        ))
        db_session.commit()

        db_session.refresh(ticker)
        assert len(ticker.prices) == 2

    def test_relationship_price_to_ticker(self, db_session):
        """MonthlyPrice.ticker returns the parent Ticker."""
        ticker = self._create_ticker(db_session)
        price = MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=195.0, low=180.0, close=190.0
        )
        db_session.add(price)
        db_session.commit()

        db_session.refresh(price)
        assert price.ticker.symbol == "AAPL"

    def test_cascade_delete(self, db_session):
        """Deleting a ticker removes its prices."""
        ticker = self._create_ticker(db_session)
        db_session.add(MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1,
            high=195.0, low=180.0, close=190.0
        ))
        db_session.commit()

        db_session.delete(ticker)
        db_session.commit()

        count = db_session.query(MonthlyPrice).count()
        assert count == 0

    def test_price_repr(self, db_session):
        """MonthlyPrice has a useful string representation."""
        ticker = self._create_ticker(db_session)
        price = MonthlyPrice(
            ticker_id=ticker.id, year=2024, month=1, close=190.0
        )
        assert "2024" in repr(price)

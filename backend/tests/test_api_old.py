"""Unit tests for FastAPI endpoints.

Uses TestClient with in-memory SQLite - no network or SQL Server needed.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from datetime import date
from unittest.mock import patch

from app.database import Base
from app.models import Ticker, MonthlyPrice, Dividend
from app.mm_rates import MonthlyMoneyMarketRate, AnnualMoneyMarketRate  # Register all models
from app.api import app, get_db


# --- Test database setup ---
# connect_args allows cross-thread access for SQLite in-memory
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=TEST_ENGINE)

# Create all tables once at module level
Base.metadata.create_all(bind=TEST_ENGINE)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Clean and recreate tables before each test."""
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield


@pytest.fixture
def db():
    """Provide a test database session."""
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def enable_writes():
    """Temporarily enable write API for tests that need it."""
    with patch("app.api.ENABLE_WRITE_API", True):
        yield


def _seed_ticker(db, symbol="XLK", name="Information Technology", active=True):
    ticker = Ticker(symbol=symbol, name=name, active=active)
    db.add(ticker)
    db.commit()
    db.refresh(ticker)
    return ticker


def _seed_prices(db, ticker_id, rows):
    for year, month, high, low, close, adj_close in rows:
        db.add(MonthlyPrice(
            ticker_id=ticker_id, year=year, month=month,
            high=high, low=low, close=close, adj_close=adj_close,
        ))
    db.commit()


def _seed_dividends(db, ticker_id, rows):
    for pay_date, amount in rows:
        db.add(Dividend(ticker_id=ticker_id, pay_date=pay_date, amount=amount))
    db.commit()


# ===========================================
# HEALTH CHECK TESTS
# ===========================================

class TestHealthCheck:

    def test_health_endpoint(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "timestamp" in data
        assert "tickers" in data
        assert "price_records" in data

    def test_health_shows_counts(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [(2024, 1, 200, 190, 195, 194)])
        resp = client.get("/api/health")
        data = resp.json()
        assert data["tickers"] >= 1
        assert data["price_records"] >= 1


# ===========================================
# TICKER ENDPOINT TESTS
# ===========================================

class TestTickerEndpoints:

    def test_list_tickers_empty(self):
        resp = client.get("/api/tickers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_ticker_blocked_when_disabled(self):
        """Write operations return 403 when ENABLE_WRITE_API is False."""
        resp = client.post("/api/tickers", json={"symbol": "XLK", "name": "Info Tech"})
        assert resp.status_code == 403

    def test_create_ticker(self, enable_writes):
        resp = client.post("/api/tickers", json={"symbol": "XLK", "name": "Info Tech"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "XLK"
        assert data["name"] == "Info Tech"
        assert data["active"] is True

    def test_create_ticker_uppercases_symbol(self, enable_writes):
        resp = client.post("/api/tickers", json={"symbol": "xlk"})
        assert resp.status_code == 201
        assert resp.json()["symbol"] == "XLK"

    def test_create_duplicate_ticker(self, db, enable_writes):
        _seed_ticker(db, "XLK")
        resp = client.post("/api/tickers", json={"symbol": "XLK"})
        assert resp.status_code == 409

    def test_create_ticker_max_limit(self, db, enable_writes):
        for i in range(50):
            _seed_ticker(db, f"T{i:03d}")
        resp = client.post("/api/tickers", json={"symbol": "EXTRA"})
        assert resp.status_code == 400
        assert "Maximum" in resp.json()["detail"]

    def test_create_ticker_invalid_symbol(self, enable_writes):
        resp = client.post("/api/tickers", json={"symbol": "123"})
        assert resp.status_code == 422  # Pydantic validation error

    def test_create_ticker_empty_symbol(self, enable_writes):
        resp = client.post("/api/tickers", json={"symbol": ""})
        assert resp.status_code == 422

    def test_create_ticker_too_long_symbol(self, enable_writes):
        resp = client.post("/api/tickers", json={"symbol": "ABCDEFGHIJK"})
        assert resp.status_code == 422

    def test_create_ticker_with_dot(self, enable_writes):
        """Tickers like BRK.B should be valid."""
        resp = client.post("/api/tickers", json={"symbol": "BRK.B"})
        assert resp.status_code == 201
        assert resp.json()["symbol"] == "BRK.B"

    def test_create_ticker_name_too_long(self, enable_writes):
        resp = client.post("/api/tickers", json={"symbol": "XLK", "name": "A" * 201})
        assert resp.status_code == 422

    def test_list_tickers_returns_all(self, db):
        _seed_ticker(db, "XLK")
        _seed_ticker(db, "XLF")
        resp = client.get("/api/tickers")
        assert len(resp.json()) == 2

    def test_list_active_tickers(self, db):
        _seed_ticker(db, "XLK", active=True)
        _seed_ticker(db, "XLF", active=False)
        resp = client.get("/api/tickers/active")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "XLK"

    def test_update_ticker_blocked_when_disabled(self, db):
        _seed_ticker(db, "XLK", name="Old Name")
        resp = client.put("/api/tickers/XLK", json={"name": "New Name"})
        assert resp.status_code == 403

    def test_update_ticker_name(self, db, enable_writes):
        _seed_ticker(db, "XLK", name="Old Name")
        resp = client.put("/api/tickers/XLK", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_ticker_deactivate(self, db, enable_writes):
        _seed_ticker(db, "XLK")
        resp = client.put("/api/tickers/XLK", json={"active": False})
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_update_nonexistent_ticker(self, enable_writes):
        resp = client.put("/api/tickers/ZZZZ", json={"name": "Test"})
        assert resp.status_code == 404

    def test_delete_ticker_blocked_when_disabled(self, db):
        _seed_ticker(db, "XLK")
        resp = client.delete("/api/tickers/XLK")
        assert resp.status_code == 403

    def test_delete_ticker(self, db, enable_writes):
        _seed_ticker(db, "XLK")
        resp = client.delete("/api/tickers/XLK")
        assert resp.status_code == 200

        resp = client.get("/api/tickers")
        assert len(resp.json()) == 0

    def test_delete_nonexistent_ticker(self, enable_writes):
        resp = client.delete("/api/tickers/ZZZZ")
        assert resp.status_code == 404

    def test_delete_ticker_cascades_data(self, db, enable_writes):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [(2024, 1, 200, 190, 195, 194)])
        _seed_dividends(db, ticker.id, [(date(2024, 3, 15), 0.50)])

        resp = client.delete("/api/tickers/XLK")
        assert resp.status_code == 200
        assert db.query(MonthlyPrice).count() == 0
        assert db.query(Dividend).count() == 0


# ===========================================
# PRICE ENDPOINT TESTS
# ===========================================

class TestPriceEndpoints:

    def test_get_prices(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [
            (2024, 1, 200, 190, 195, 194),
            (2024, 2, 210, 195, 205, 204),
            (2024, 3, 215, 200, 210, 209),
        ])

        resp = client.get("/api/prices/XLK")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["year"] == 2024
        assert data[0]["month"] == 1

    def test_get_prices_with_date_filter(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [
            (2024, 1, 200, 190, 195, 194),
            (2024, 6, 220, 210, 215, 214),
            (2024, 12, 230, 220, 225, 224),
        ])

        resp = client.get("/api/prices/XLK?start_year=2024&start_month=6&end_year=2024&end_month=6")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["month"] == 6

    def test_get_prices_nonexistent_ticker(self):
        resp = client.get("/api/prices/ZZZZ")
        assert resp.status_code == 404

    def test_get_prices_case_insensitive(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [(2024, 1, 200, 190, 195, 194)])

        resp = client.get("/api/prices/xlk")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_prices_invalid_month(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/prices/XLK?start_month=13")
        assert resp.status_code == 400

    def test_get_prices_invalid_year(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/prices/XLK?start_year=1800")
        assert resp.status_code == 400

    def test_get_latest_price(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [
            (2024, 1, 200, 190, 195, 194),
            (2024, 6, 220, 210, 215, 214),
            (2025, 1, 240, 230, 235, 234),
        ])

        resp = client.get("/api/prices/XLK/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2025
        assert data["month"] == 1

    def test_get_latest_price_no_data(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/prices/XLK/latest")
        assert resp.status_code == 404


# ===========================================
# DIVIDEND ENDPOINT TESTS
# ===========================================

class TestDividendEndpoints:

    def test_get_dividends(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_dividends(db, ticker.id, [
            (date(2024, 3, 15), 0.50),
            (date(2024, 6, 14), 0.55),
            (date(2024, 9, 13), 0.55),
        ])

        resp = client.get("/api/dividends/XLK")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["amount"] == 0.50

    def test_get_dividends_with_year_filter(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_dividends(db, ticker.id, [
            (date(2023, 6, 15), 0.45),
            (date(2024, 6, 14), 0.55),
            (date(2025, 6, 13), 0.60),
        ])

        resp = client.get("/api/dividends/XLK?start_year=2024&end_year=2024")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["amount"] == 0.55

    def test_get_dividends_nonexistent_ticker(self):
        resp = client.get("/api/dividends/ZZZZ")
        assert resp.status_code == 404

    def test_get_dividends_no_data(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/dividends/XLK")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_dividends_invalid_year(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/dividends/XLK?start_year=1800")
        assert resp.status_code == 400


# ===========================================
# SIMULATION DATA ENDPOINT TESTS
# ===========================================

class TestSimulationDataEndpoint:

    def test_get_simulation_data(self, db):
        ticker = _seed_ticker(db, "XLK", name="Info Tech")
        _seed_prices(db, ticker.id, [
            (2024, 1, 200, 190, 195, 194),
            (2024, 2, 210, 195, 205, 204),
            (2024, 3, 215, 200, 210, 209),
        ])
        _seed_dividends(db, ticker.id, [
            (date(2024, 3, 15), 0.50),
        ])

        resp = client.get("/api/simulation-data/XLK")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "XLK"
        assert data["name"] == "Info Tech"
        assert len(data["monthly_data"]) == 3

        # March should have the dividend
        march = data["monthly_data"][2]
        assert march["year"] == 2024
        assert march["month"] == 3
        assert len(march["dividends"]) == 1
        assert march["dividends"][0]["amount"] == 0.50

        # Jan should have no dividends
        jan = data["monthly_data"][0]
        assert len(jan["dividends"]) == 0

    def test_simulation_data_with_date_range(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [
            (2024, 1, 200, 190, 195, 194),
            (2024, 6, 220, 210, 215, 214),
            (2024, 12, 230, 220, 225, 224),
        ])

        resp = client.get("/api/simulation-data/XLK?start_year=2024&start_month=6&end_year=2024&end_month=6")
        data = resp.json()
        assert len(data["monthly_data"]) == 1
        assert data["monthly_data"][0]["month"] == 6

    def test_simulation_data_nonexistent_ticker(self):
        resp = client.get("/api/simulation-data/ZZZZ")
        assert resp.status_code == 404

    def test_simulation_data_multiple_dividends_in_month(self, db):
        ticker = _seed_ticker(db, "XLK")
        _seed_prices(db, ticker.id, [(2024, 6, 220, 210, 215, 214)])
        _seed_dividends(db, ticker.id, [
            (date(2024, 6, 10), 0.25),
            (date(2024, 6, 20), 0.30),
        ])

        resp = client.get("/api/simulation-data/XLK")
        data = resp.json()
        assert len(data["monthly_data"][0]["dividends"]) == 2

    def test_simulation_data_invalid_month(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/simulation-data/XLK?start_month=0")
        assert resp.status_code == 400


# ===========================================
# BATCH ENDPOINT TESTS
# ===========================================

class TestBatchEndpoints:

    def test_batch_status_initial(self):
        resp = client.get("/api/batch/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_batch_blocked_when_disabled(self):
        resp = client.post("/api/batch/full")
        assert resp.status_code == 403

    def test_batch_full_no_tickers(self, enable_writes):
        resp = client.post("/api/batch/full")
        assert resp.status_code == 400

    def test_batch_incremental_no_tickers(self, enable_writes):
        resp = client.post("/api/batch/incremental")
        assert resp.status_code == 400

    def test_batch_invalid_symbols(self, enable_writes):
        resp = client.post("/api/batch/full", json={"symbols": ["123BAD"]})
        assert resp.status_code == 422

    def test_batch_too_many_symbols(self, enable_writes):
        symbols = [f"T{i:03d}" for i in range(51)]
        resp = client.post("/api/batch/full", json={"symbols": symbols})
        assert resp.status_code == 422


# ===========================================
# ERROR HANDLING TESTS
# ===========================================

class TestErrorHandling:

    def test_invalid_symbol_in_path(self):
        resp = client.get("/api/prices/123")
        assert resp.status_code == 400

    def test_error_response_has_request_id(self):
        resp = client.get("/api/prices/ZZZZ")
        data = resp.json()
        assert "request_id" in data

    def test_response_has_request_id_header(self, db):
        _seed_ticker(db, "XLK")
        resp = client.get("/api/tickers")
        assert "X-Request-ID" in resp.headers

    def test_404_is_structured(self):
        resp = client.get("/api/prices/ZZZZ")
        data = resp.json()
        assert "error" in data
        assert "detail" in data

"""Integration tests for FastAPI endpoints.

Tests against the real SQL Server database with actual data.
No data is modified or deleted - read-only verification.
"""
import pytest
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


# ===========================================
# HEALTH CHECK
# ===========================================

class TestHealthCheck:

    def test_health_endpoint(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        print(f"\n  Database: {data['database']}")
        print(f"  Tickers: {data['tickers']}")
        print(f"  Price records: {data['price_records']}")
        print(f"  Batch status: {data['batch_status']}")


# ===========================================
# TICKER ENDPOINTS (read-only)
# ===========================================

class TestTickerEndpoints:

    def test_list_tickers(self):
        resp = client.get("/api/tickers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  Total tickers: {len(data)}")
        for t in data:
            print(f"    {t['symbol']:8s} {t['name'] or '':30s} active={t['active']}")

    def test_list_active_tickers(self):
        resp = client.get("/api/tickers/active")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  Active tickers: {len(data)}")
        assert all(t["active"] for t in data)

    def test_write_endpoints_blocked(self):
        """POST/PUT/DELETE should return 403 when writes disabled."""
        resp = client.post("/api/tickers", json={"symbol": "TEST"})
        assert resp.status_code == 403

        resp = client.put("/api/tickers/XLK", json={"name": "Test"})
        assert resp.status_code == 403

        resp = client.delete("/api/tickers/XLK")
        assert resp.status_code == 403
        print("\n  All write endpoints correctly blocked (403)")


# ===========================================
# PRICE ENDPOINTS (read-only)
# ===========================================

class TestPriceEndpoints:

    def test_get_prices_xlk(self):
        resp = client.get("/api/prices/XLK")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  XLK total price records: {len(data)}")
        print(f"  First: {data[0]['year']}-{data[0]['month']:02d}")
        print(f"  Last:  {data[-1]['year']}-{data[-1]['month']:02d}")

    def test_get_prices_with_filter(self):
        resp = client.get("/api/prices/XLK?start_year=2024&start_month=1&end_year=2024&end_month=12")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  XLK 2024 price records: {len(data)}")
        for p in data:
            print(f"    {p['year']}-{p['month']:02d}  H={p['high']:.2f}  L={p['low']:.2f}  C={p['close']:.2f}")

    def test_get_latest_price(self):
        resp = client.get("/api/prices/XLK/latest")
        assert resp.status_code == 200
        data = resp.json()
        print(f"\n  XLK latest: {data['year']}-{data['month']:02d} close={data['close']:.2f}")

    def test_get_prices_nonexistent_ticker(self):
        resp = client.get("/api/prices/ZZZZZ")
        assert resp.status_code in (400, 404)

    def test_get_prices_case_insensitive(self):
        resp = client.get("/api/prices/xlk")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_invalid_month_rejected(self):
        resp = client.get("/api/prices/XLK?start_month=13")
        assert resp.status_code == 400

    def test_invalid_year_rejected(self):
        resp = client.get("/api/prices/XLK?start_year=1800")
        assert resp.status_code == 400


# ===========================================
# DIVIDEND ENDPOINTS (read-only)
# ===========================================

class TestDividendEndpoints:

    def test_get_dividends_xlk(self):
        resp = client.get("/api/dividends/XLK")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  XLK total dividends: {len(data)}")
        print(f"  First: {data[0]['pay_date']} ${data[0]['amount']:.4f}")
        print(f"  Last:  {data[-1]['pay_date']} ${data[-1]['amount']:.4f}")

    def test_get_dividends_with_year_filter(self):
        resp = client.get("/api/dividends/XLK?start_year=2024&end_year=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  XLK 2024 dividends: {len(data)}")
        for d in data:
            print(f"    {d['pay_date']}  ${d['amount']:.4f}")

    def test_get_dividends_nonexistent_ticker(self):
        resp = client.get("/api/dividends/ZZZZZ")
        assert resp.status_code in (400, 404)


# ===========================================
# SIMULATION DATA ENDPOINT (read-only)
# ===========================================

class TestSimulationDataEndpoint:

    def test_get_simulation_data_xlk(self):
        resp = client.get("/api/simulation-data/XLK?start_year=2024&start_month=1&end_year=2024&end_month=6")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "XLK"
        assert len(data["monthly_data"]) > 0
        print(f"\n  XLK simulation data (2024 H1): {len(data['monthly_data'])} months")
        for m in data["monthly_data"]:
            div_total = sum(d["amount"] for d in m["dividends"])
            div_str = f"  divs=${div_total:.4f}" if div_total > 0 else ""
            print(f"    {m['year']}-{m['month']:02d}  H={m['high']:.2f}  C={m['close']:.2f}{div_str}")

    def test_simulation_data_nonexistent_ticker(self):
        resp = client.get("/api/simulation-data/ZZZZZ")
        assert resp.status_code in (400, 404)


# ===========================================
# MONEY MARKET RATE ENDPOINTS (read-only)
# ===========================================

class TestMoneyMarketRateEndpoints:

    def test_get_monthly_rates(self):
        resp = client.get("/api/mm-rates/monthly")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  Total monthly MM rates: {len(data)}")
        print(f"  First: {data[0]['year']}-{data[0]['month']:02d}  rate={data[0]['rate']:.2f}%")
        print(f"  Last:  {data[-1]['year']}-{data[-1]['month']:02d}  rate={data[-1]['rate']:.2f}%")

    def test_get_monthly_rates_with_filter(self):
        resp = client.get("/api/mm-rates/monthly?start_year=2024&end_year=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  2024 monthly MM rates: {len(data)}")
        for r in data:
            print(f"    {r['year']}-{r['month']:02d}  {r['rate']:.2f}%")

    def test_get_annual_rates(self):
        resp = client.get("/api/mm-rates/annual")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        print(f"\n  Total annual MM rates: {len(data)}")
        for r in data:
            print(f"    {r['year']}  {r['avg_rate']:.2f}%")

    def test_get_annual_rate_by_year(self):
        resp = client.get("/api/mm-rates/annual/2024")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2024
        print(f"\n  2024 annual avg rate: {data['avg_rate']:.2f}%")

    def test_get_annual_rate_nonexistent_year(self):
        resp = client.get("/api/mm-rates/annual/1900")
        assert resp.status_code == 404


# ===========================================
# BATCH ENDPOINTS (read-only)
# ===========================================

class TestBatchEndpoints:

    def test_batch_status(self):
        resp = client.get("/api/batch/status")
        assert resp.status_code == 200
        data = resp.json()
        print(f"\n  Batch status: {data['status']}")

    def test_batch_write_blocked(self):
        resp = client.post("/api/batch/full")
        assert resp.status_code == 403

        resp = client.post("/api/batch/incremental")
        assert resp.status_code == 403
        print("\n  Batch write endpoints correctly blocked (403)")


# ===========================================
# ERROR HANDLING & VALIDATION
# ===========================================

class TestErrorHandling:

    def test_invalid_symbol_in_path(self):
        resp = client.get("/api/prices/123")
        assert resp.status_code == 400

    def test_error_response_has_request_id(self):
        resp = client.get("/api/prices/ZZZZZ")
        data = resp.json()
        assert "request_id" in data

    def test_response_has_request_id_header(self):
        resp = client.get("/api/tickers")
        assert "X-Request-ID" in resp.headers

    def test_structured_error_response(self):
        resp = client.get("/api/prices/ZZZZZ")
        data = resp.json()
        assert "error" in data
        assert "detail" in data
        assert "request_id" in data

    def test_pydantic_validation(self):
        """Invalid symbols rejected by Pydantic before hitting DB."""
        resp = client.post("/api/tickers", json={"symbol": "123"})
        assert resp.status_code == 422

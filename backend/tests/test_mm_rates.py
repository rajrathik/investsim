"""Unit tests for FRED fetcher and money market rates."""
import pytest
import pandas as pd
from datetime import date
from sqlalchemy.exc import IntegrityError

from app.mm_rates import (
    MonthlyMoneyMarketRate,
    AnnualMoneyMarketRate,
    load_monthly_rates,
    load_annual_averages,
    load_all_rates,
)
from app.fred_fetcher import compute_annual_averages


# ===========================================
# MODEL TESTS
# ===========================================

class TestMonthlyRateModel:

    def test_create_monthly_rate(self, db_session):
        rate = MonthlyMoneyMarketRate(year=2024, month=1, rate=5.33)
        db_session.add(rate)
        db_session.commit()

        result = db_session.query(MonthlyMoneyMarketRate).first()
        assert result.year == 2024
        assert result.month == 1
        assert result.rate == 5.33

    def test_no_duplicate_year_month(self, db_session):
        db_session.add(MonthlyMoneyMarketRate(year=2024, month=1, rate=5.33))
        db_session.commit()

        db_session.add(MonthlyMoneyMarketRate(year=2024, month=1, rate=5.40))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestAnnualRateModel:

    def test_create_annual_rate(self, db_session):
        rate = AnnualMoneyMarketRate(year=2024, avg_rate=5.15)
        db_session.add(rate)
        db_session.commit()

        result = db_session.query(AnnualMoneyMarketRate).first()
        assert result.year == 2024
        assert result.avg_rate == 5.15

    def test_no_duplicate_year(self, db_session):
        db_session.add(AnnualMoneyMarketRate(year=2024, avg_rate=5.15))
        db_session.commit()

        db_session.add(AnnualMoneyMarketRate(year=2024, avg_rate=5.20))
        with pytest.raises(IntegrityError):
            db_session.commit()


# ===========================================
# COMPUTE TESTS
# ===========================================

class TestComputeAverages:

    def test_compute_annual_averages(self):
        df = pd.DataFrame({
            "year": [2023, 2023, 2024, 2024],
            "month": [6, 12, 6, 12],
            "rate": [4.50, 5.00, 5.20, 5.30],
        })

        result = compute_annual_averages(df)
        assert len(result) == 2

        y2023 = result[result["year"] == 2023].iloc[0]
        assert y2023["avg_rate"] == pytest.approx(4.75, abs=0.01)

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        assert compute_annual_averages(df).empty


# ===========================================
# LOADER TESTS
# ===========================================

class TestLoadMonthlyRates:

    def _make_df(self, rows):
        return pd.DataFrame(rows, columns=["year", "month", "rate"])

    def test_insert_monthly_rates(self, db_session):
        df = self._make_df([
            [2024, 1, 5.33],
            [2024, 2, 5.33],
        ])

        counts = load_monthly_rates(db_session, df, mode="full")
        assert counts["inserted"] == 2
        assert db_session.query(MonthlyMoneyMarketRate).count() == 2

    def test_full_mode_skips_existing(self, db_session):
        db_session.add(MonthlyMoneyMarketRate(year=2024, month=1, rate=5.33))
        db_session.commit()

        df = self._make_df([
            [2024, 1, 9.99],  # Existing
            [2024, 2, 5.33],  # New
        ])

        counts = load_monthly_rates(db_session, df, mode="full")
        assert counts["inserted"] == 1
        assert counts["skipped"] == 1

        existing = db_session.query(MonthlyMoneyMarketRate).filter_by(year=2024, month=1).first()
        assert existing.rate == 5.33  # Not overwritten

    def test_incremental_mode_updates_existing(self, db_session):
        db_session.add(MonthlyMoneyMarketRate(year=2024, month=1, rate=5.33))
        db_session.commit()

        df = self._make_df([
            [2024, 1, 5.40],  # Updated
        ])

        counts = load_monthly_rates(db_session, df, mode="incremental")
        assert counts["updated"] == 1

        updated = db_session.query(MonthlyMoneyMarketRate).filter_by(year=2024, month=1).first()
        assert updated.rate == 5.40

    def test_empty_dataframe(self, db_session):
        counts = load_monthly_rates(db_session, pd.DataFrame(), mode="full")
        assert counts["inserted"] == 0


class TestLoadAnnualAverages:

    def test_insert_annual(self, db_session):
        df = pd.DataFrame({"year": [2023, 2024], "avg_rate": [4.75, 5.15]})

        counts = load_annual_averages(db_session, df)
        assert counts["inserted"] == 2

    def test_upsert_annual(self, db_session):
        db_session.add(AnnualMoneyMarketRate(year=2024, avg_rate=5.15))
        db_session.commit()

        df = pd.DataFrame({"year": [2024], "avg_rate": [5.20]})
        counts = load_annual_averages(db_session, df)
        assert counts["updated"] == 1

        result = db_session.query(AnnualMoneyMarketRate).first()
        assert result.avg_rate == 5.20


# ===========================================
# NETWORK TESTS (hit FRED)
# ===========================================

class TestFredFetcher:

    @pytest.mark.network
    def test_fetch_monthly_rates(self):
        from app.fred_fetcher import get_monthly_rates
        df = get_monthly_rates(start_date="2024-01-01", end_date="2024-12-31")
        assert not df.empty
        assert "year" in df.columns
        assert "month" in df.columns
        assert "rate" in df.columns
        assert (df["rate"] > 0).all()
        assert len(df) >= 10  # Should have ~12 months

    @pytest.mark.network
    def test_fetch_incremental(self):
        from app.fred_fetcher import get_monthly_rates_incremental
        df = get_monthly_rates_incremental()
        assert not df.empty
        assert len(df) >= 2  # At least 2 months in 3 month window

    @pytest.mark.network
    def test_full_history_has_many_records(self):
        from app.fred_fetcher import get_monthly_rates
        df = get_monthly_rates()
        assert len(df) > 100  # 20 years of monthly data = ~240

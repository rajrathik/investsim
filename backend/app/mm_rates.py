"""Database models and loader for money market rates."""
import logging
from sqlalchemy import Column, Integer, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import Session
import pandas as pd

from app.database import Base
from app.models import _utcnow

logger = logging.getLogger(__name__)


class MonthlyMoneyMarketRate(Base):
    """Monthly Federal Funds Rate from FRED."""
    __tablename__ = "monthly_mm_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    rate = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_mm_year_month"),
    )

    def __repr__(self):
        return f"<MonthlyMMRate({self.year}-{self.month:02d}, rate={self.rate})>"


class AnnualMoneyMarketRate(Base):
    """Annual average money market rate (computed from monthly)."""
    __tablename__ = "annual_mm_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, unique=True, nullable=False, index=True)
    avg_rate = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self):
        return f"<AnnualMMRate({self.year}, rate={self.avg_rate})>"


# ===========================================
# LOADER FUNCTIONS
# ===========================================

def load_monthly_rates(db: Session, monthly_df: pd.DataFrame, mode: str = "full") -> dict:
    """Load monthly rates into database.

    Args:
        db: Database session
        monthly_df: DataFrame with year, month, rate columns
        mode: 'full' (skip existing) or 'incremental' (upsert)

    Returns:
        Dict with counts: {"inserted": n, "updated": n, "skipped": n}
    """
    if monthly_df.empty:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    for _, row in monthly_df.iterrows():
        year = int(row["year"])
        month = int(row["month"])
        rate = float(row["rate"])

        existing = db.query(MonthlyMoneyMarketRate).filter(
            MonthlyMoneyMarketRate.year == year,
            MonthlyMoneyMarketRate.month == month,
        ).first()

        if existing:
            if mode == "incremental":
                existing.rate = rate
                counts["updated"] += 1
            else:
                counts["skipped"] += 1
        else:
            db.add(MonthlyMoneyMarketRate(year=year, month=month, rate=rate))
            counts["inserted"] += 1

    db.commit()
    logger.info(
        f"Monthly rates: {counts['inserted']}i/{counts['updated']}u/{counts['skipped']}s"
    )
    return counts


def load_annual_averages(db: Session, annual_df: pd.DataFrame) -> dict:
    """Load/update annual average rates. Always upserts."""
    if annual_df.empty:
        return {"inserted": 0, "updated": 0}

    counts = {"inserted": 0, "updated": 0}

    for _, row in annual_df.iterrows():
        year = int(row["year"])
        avg_rate = float(row["avg_rate"])

        existing = db.query(AnnualMoneyMarketRate).filter(
            AnnualMoneyMarketRate.year == year
        ).first()

        if existing:
            existing.avg_rate = avg_rate
            counts["updated"] += 1
        else:
            db.add(AnnualMoneyMarketRate(year=year, avg_rate=avg_rate))
            counts["inserted"] += 1

    db.commit()
    logger.info(f"Annual avg rates: {counts['inserted']}i/{counts['updated']}u")
    return counts


def load_all_rates(db: Session, monthly_df: pd.DataFrame, mode: str = "full") -> dict:
    """Load monthly rates and compute/store annual averages.

    Args:
        db: Database session
        monthly_df: DataFrame from fred_fetcher.get_monthly_rates()
        mode: 'full' or 'incremental'

    Returns:
        Summary dict with monthly and annual counts
    """
    from app.fred_fetcher import compute_annual_averages

    monthly_counts = load_monthly_rates(db, monthly_df, mode)

    # Recompute annual averages from ALL stored monthly data
    all_monthly = db.query(MonthlyMoneyMarketRate).order_by(
        MonthlyMoneyMarketRate.year, MonthlyMoneyMarketRate.month
    ).all()
    all_monthly_df = pd.DataFrame([
        {"year": r.year, "month": r.month, "rate": r.rate} for r in all_monthly
    ])

    annual_df = compute_annual_averages(all_monthly_df)
    annual_counts = load_annual_averages(db, annual_df)

    return {
        "monthly": monthly_counts,
        "annual": annual_counts,
    }

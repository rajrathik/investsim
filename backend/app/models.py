"""Database models for portfolio simulator."""
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Ticker(Base):
    """Stock ticker symbol."""
    __tablename__ = "tickers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    prices = relationship("MonthlyPrice", back_populates="ticker", cascade="all, delete-orphan")
    dividends = relationship("Dividend", back_populates="ticker", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Ticker(symbol='{self.symbol}', active={self.active})>"


class MonthlyPrice(Base):
    """Monthly price data: high, low, close, adjusted close."""
    __tablename__ = "monthly_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationship back to ticker
    ticker = relationship("Ticker", back_populates="prices")

    # Prevent duplicate entries for same ticker + year + month
    __table_args__ = (
        UniqueConstraint("ticker_id", "year", "month", name="uq_ticker_year_month"),
    )

    def __repr__(self):
        return (
            f"<MonthlyPrice(ticker_id={self.ticker_id}, "
            f"{self.year}-{self.month:02d}, close={self.close})>"
        )


class Dividend(Base):
    """Dividend payments with pay date."""
    __tablename__ = "dividends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    pay_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationship back to ticker
    ticker = relationship("Ticker", back_populates="dividends")

    # Prevent duplicate entries for same ticker + pay_date
    __table_args__ = (
        UniqueConstraint("ticker_id", "pay_date", name="uq_ticker_pay_date"),
    )

    def __repr__(self):
        return (
            f"<Dividend(ticker_id={self.ticker_id}, "
            f"pay_date={self.pay_date}, amount={self.amount})>"
        )

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


class SpyDailyPrice(Base):
    """Daily OHLCV price data for SPY (SPDR S&P 500 ETF Trust).

    Standalone table, not tied to the tickers/monthly_prices FK structure.
    Carries its own `ticker` column (redundant while this table only ever
    holds SPY) so it and OefDailyPrice can be combined into one shared
    daily-prices table later without a schema change. For now they stay
    separate, one table per ticker.
    """
    __tablename__ = "spy_daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, default="SPY", index=True)
    price_date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "price_date", name="uq_spy_daily_ticker_date"),
    )

    def __repr__(self):
        return f"<SpyDailyPrice({self.ticker} {self.price_date}, close={self.close})>"


class OefDailyPrice(Base):
    """Daily OHLCV price data for OEF (iShares S&P 100 ETF).

    Mirrors SpyDailyPrice's schema exactly — see its docstring for why the
    two tables stay separate for now despite the shared `ticker` column.
    """
    __tablename__ = "oef_daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, default="OEF", index=True)
    price_date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "price_date", name="uq_oef_daily_ticker_date"),
    )

    def __repr__(self):
        return f"<OefDailyPrice({self.ticker} {self.price_date}, close={self.close})>"


class DailyQuote(Base):
    """One saved price + 52-week range snapshot per ticker per trading day.

    Works for any ticker (not just tickers/monthly_prices ones) -- backs
    GET /api/quotes, which saves a row here every time it fetches a fresh
    (non-cached) quote. quote_date is the ACTUAL last trade date reported
    by Yahoo, not the server's calendar date -- so running this before
    market open just keeps re-saving (overwriting) the prior trading
    day's row until a new day's trade actually posts.
    """
    __tablename__ = "daily_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    quote_date = Column(Date, nullable=False)
    price = Column(Float, nullable=True)
    week52_low = Column(Float, nullable=True)
    week52_high = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "quote_date", name="uq_daily_quote_ticker_date"),
    )

    def __repr__(self):
        return f"<DailyQuote({self.ticker} {self.quote_date}, price={self.price})>"


class EtfDirectoryMonthlyHistory(Base):
    """Monthly high/low/close/dividend history for ETF Directory tickers.

    Standalone table, deliberately isolated from the tickers/monthly_prices/
    dividends pipeline -- the ETF Directory's curated ticker list still
    lives in frontend/etf-directory.js (not the tickers table), and this
    table exists purely to back its 10-year range feature. One row per
    ticker per closed calendar month; the in-progress current month is
    never written here (see loader.get_etf_history_missing_months()).
    """
    __tablename__ = "etf_directory_monthly_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    dividend = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "year", "month", name="uq_etf_dir_hist_ticker_year_month"),
    )

    def __repr__(self):
        return f"<EtfDirectoryMonthlyHistory({self.ticker} {self.year}-{self.month:02d}, close={self.close})>"


class UserLogin(Base):
    """Track user login events from Auth0.

    Each row = one login event.  auth0_user_id is the stable user
    identifier ('sub' claim) for associating future saved simulations.
    """
    __tablename__ = "user_logins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auth0_user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    login_time = Column(DateTime, default=_utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    def __repr__(self):
        return f"<UserLogin(user={self.email}, time={self.login_time})>"


class UserAdmin(Base):
    """Whitelist of users authorized to access the admin dashboard.

    The table is managed manually (INSERT via SQL).
    Admin pages check if the logged-in user's email exists here.
    """
    __tablename__ = "user_admin"

    email = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<UserAdmin(email='{self.email}')>"


class ApiRequestLog(Base):
    """Log every API request for audit and debugging.

    Captures who called what endpoint, when, how long it took,
    and whether it succeeded or failed.
    """
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(8), nullable=False, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    error_detail = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<ApiRequestLog({self.method} {self.path} "
            f"-> {self.status_code}, user={self.user_email})>"
        )


class SavedSimulation(Base):
    """A user's saved portfolio simulation result.

    Each user can save up to 3 simulations.  The id is auto-increment
    and may have gaps after deletions (e.g. 1, 2, 4).  Display numbering
    is handled by the frontend (sort by created_at, display index + 1).
    """
    __tablename__ = "saved_simulations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auth0_user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False)

    # Simulation inputs
    tickers_json = Column(String(2000), nullable=False)   # JSON: {"XLK":60,"XLF":40}
    start_year = Column(Integer, nullable=False)
    end_year = Column(Integer, nullable=False)
    monthly_amount = Column(Float, nullable=False)
    annual_growth = Column(Float, nullable=False, default=0)

    # Simulation results (the 6+ tile values)
    total_invested = Column(Float, nullable=False)
    equity_value = Column(Float, nullable=False)
    dividends_earned = Column(Float, nullable=False)
    cash_accrual = Column(Float, nullable=False)       # divBal (dividends + MM interest)
    mm_earned = Column(Float, nullable=False)           # divBal - tDiv
    portfolio_balance = Column(Float, nullable=False)   # pv + divBal
    total_return_pct = Column(Float, nullable=False)    # ((pv+divBal-tInv)/tInv)*100
    mmf_value = Column(Float, nullable=False)           # mmOnlyBal

    created_at = Column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<SavedSimulation(id={self.id}, user={self.email}, "
            f"balance=${self.portfolio_balance:.0f})>"
        )

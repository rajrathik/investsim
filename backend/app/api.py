"""FastAPI REST API for portfolio simulator.

Endpoints:
  Health:
    GET    /api/health                      - Health check

  Auth (admin only):
    GET    /api/auth/config                 - Auth0 config for frontend SPA (unauthenticated)
    POST   /api/auth/login-event            - Log login event
    GET    /api/admin/write-status          - Check if write API is enabled (unauthenticated)
    GET    /api/admin/verify                - Verify caller is an authorized admin (requires Auth0 token)

  Tickers:
    GET    /api/tickers                     - List all tickers (requires auth)
    GET    /api/tickers/active              - List active tickers only (public)
    POST   /api/tickers                     - Add a new ticker (requires write API enabled)
    PUT    /api/tickers/{symbol}            - Update ticker name/active (requires auth + write)
    DELETE /api/tickers/{symbol}            - Delete ticker and all data (requires auth + write)

  Prices:
    GET    /api/prices/{symbol}             - Get monthly prices for a ticker (public)
    GET    /api/prices/{symbol}/latest      - Get latest month's price (public)

  Dividends:
    GET    /api/dividends/{symbol}          - Get dividends for a ticker (public)

  Simulation Data:
    GET    /api/simulation-data/{symbol}    - Combined prices + dividends for simulation (public)

  Money Market Rates:
    GET    /api/mm-rates/monthly            - Monthly FRED federal funds rates (public)
    GET    /api/mm-rates/annual             - Annual average FRED rates (public)
    GET    /api/mm-rates/annual/{year}      - Rate for a specific year (public)

  Sector Analytics:
    GET    /api/sector-performance          - Annual returns + dividends for sector ETFs (public)
    GET    /api/sector-monthly              - Monthly close prices for sector ETFs (public)

  Batch (requires write API enabled):
    POST   /api/batch/full                  - Full history load for ALL tickers (async)
    POST   /api/batch/full-new              - Full history load for NEW tickers only (async)
    POST   /api/batch/incremental           - Incremental load for recent months (async)
    POST   /api/batch/fred-full             - Full FRED rate history load (async)
    POST   /api/batch/fred-incremental      - Incremental FRED rate load — last 3 months (async)
    GET    /api/batch/status                - Status of last batch run

  Pages (served via static files):
    GET    /                                - Home / landing page (index.html)
    GET    /index.html                      - Home / landing page
    GET    /help.html                       - Redirects to / (legacy alias)
    GET    /admin.html                      - Admin dashboard (Auth0 protected)
    GET    /portfolio-simulator.html        - Asset Allocation Simulator
    GET    /sector-performance.html         - Sector annual returns & dividends
    GET    /correlation.html                - Sector correlation matrix
    GET    /drawdown.html                   - Sector drawdown analysis
    GET    /sector-rotation.html            - Sector rotation rankings
    GET    /dividend-growth.html            - Dividend growth by sector
    GET    /growth-chart.html               - $10K growth chart
    GET    /risk-return.html                - Risk vs return scatter plot
"""
import os
import re
import uuid
import time
import logging
import threading
import traceback
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, text, extract
from pydantic import BaseModel, field_validator
from typing import Optional

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

# Load .env BEFORE importing config so environment variables are available
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

from app.database import SessionLocal, init_db, engine
from app.models import Ticker, MonthlyPrice, Dividend, UserLogin, UserAdmin, ApiRequestLog
from app.config import MAX_TICKERS, ENABLE_WRITE_API
from app.auth import get_current_user

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- Lifespan (replaces deprecated on_event) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database tables verified/created.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title="Portfolio Simulator API",
    description="API for managing stock data and portfolio simulation",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend to connect (adjust origins when deploying)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================
# GLOBAL ERROR HANDLING
# ===========================================

class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: Optional[str] = None


def _extract_email_from_token(request: Request) -> Optional[str]:
    """Extract user email from request for logging (unauthenticated fallback)."""
    return "local@localhost"


def _log_request_to_db(request_id, method, path, status_code,
                       response_time_ms, ip, ua, user_email, error_detail=None):
    """Write API request log to database (fire-and-forget)."""
    try:
        # Skip logging for static files (html, css, js, images)
        if not path.startswith("/api"):
            return
        db = SessionLocal()
        try:
            log = ApiRequestLog(
                request_id=request_id,
                user_email=user_email,
                method=method,
                path=path,
                status_code=status_code,
                response_time_ms=response_time_ms,
                ip_address=ip,
                user_agent=ua[:500] if ua else None,
                error_detail=error_detail[:1000] if error_detail else None,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to log API request to DB: {e}")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request and attach a request ID."""
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start_time = time.time()

    logger.info(f"[{request_id}] {request.method} {request.url.path}")

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    user_email = _extract_email_from_token(request)

    try:
        response = await call_next(request)
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)")
        response.headers["X-Request-ID"] = request_id

        _log_request_to_db(request_id, request.method, request.url.path,
                           response.status_code, elapsed_ms, ip, ua, user_email)

        return response
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] Unhandled error in middleware: {e}")

        _log_request_to_db(request_id, request.method, request.url.path,
                           500, elapsed_ms, ip, ua, user_email, str(e))

        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "detail": "An unexpected error occurred", "request_id": request_id},
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Structured HTTP error responses."""
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "detail": exc.detail, "request_id": request_id},
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors without leaking internals."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"[{request_id}] Database error: {exc}")
    return JSONResponse(
        status_code=503,
        content={"error": "Database Error", "detail": "A database error occurred. Please try again.", "request_id": request_id},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all: never leak stack traces to the client."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"[{request_id}] Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred", "request_id": request_id},
    )


# ===========================================
# BATCH STATUS (thread-safe)
# ===========================================

_batch_lock = threading.Lock()
_batch_status = {
    "last_run": None,
    "mode": None,
    "status": "idle",
    "summary": None,
    "started_at": None,
    "completed_at": None,
    "tickers_requested": [],
}


def _update_batch_status(**kwargs):
    with _batch_lock:
        _batch_status.update(kwargs)


def _get_batch_status():
    with _batch_lock:
        return dict(_batch_status)


# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===========================================
# PYDANTIC MODELS WITH VALIDATION
# ===========================================

# Valid ticker pattern: 1-10 uppercase letters, digits, and dots (e.g. BRK.B)
TICKER_PATTERN = re.compile(r'^[A-Z][A-Z0-9.]{0,9}$')


class TickerCreate(BaseModel):
    symbol: str
    name: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v):
        v = v.upper().strip()
        if not v:
            raise ValueError("Symbol cannot be empty")
        if not TICKER_PATTERN.match(v):
            raise ValueError("Symbol must be 1-10 characters: uppercase letters, digits, dots (e.g. AAPL, BRK.B)")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) > 200:
                raise ValueError("Name must be 200 characters or less")
        return v


class TickerUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) > 200:
                raise ValueError("Name must be 200 characters or less")
        return v


class TickerResponse(BaseModel):
    id: int
    symbol: str
    name: Optional[str]
    active: bool

    class Config:
        from_attributes = True


class PriceResponse(BaseModel):
    year: int
    month: int
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    adj_close: Optional[float]

    class Config:
        from_attributes = True


class DividendResponse(BaseModel):
    pay_date: str
    amount: float

    class Config:
        from_attributes = True


class SimulationPriceRow(BaseModel):
    year: int
    month: int
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    adj_close: Optional[float]
    dividends: list[DividendResponse]


class SimulationDataResponse(BaseModel):
    symbol: str
    name: Optional[str]
    monthly_data: list[SimulationPriceRow]


class BatchRequest(BaseModel):
    symbols: Optional[list[str]] = None  # None = all active tickers
    months: Optional[int] = None  # For incremental: how many months back (default 2)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v):
        if v is not None:
            if len(v) > MAX_TICKERS:
                raise ValueError(f"Maximum {MAX_TICKERS} tickers per batch")
            cleaned = []
            for s in v:
                s = s.upper().strip()
                if not TICKER_PATTERN.match(s):
                    raise ValueError(f"Invalid ticker symbol: {s}")
                cleaned.append(s)
            return cleaned
        return v

    @field_validator("months")
    @classmethod
    def validate_months(cls, v):
        if v is not None:
            if v < 1 or v > 240:
                raise ValueError("Months must be between 1 and 240")
        return v


class BatchResponse(BaseModel):
    status: str
    message: str
    summary: Optional[dict] = None


# ===========================================
# INPUT VALIDATION HELPERS
# ===========================================

def validate_year(year: Optional[int], param_name: str) -> Optional[int]:
    """Validate year is reasonable."""
    if year is not None:
        if year < 1900 or year > 2100:
            raise HTTPException(status_code=400, detail=f"{param_name} must be between 1900 and 2100")
    return year


def validate_month(month: Optional[int], param_name: str) -> Optional[int]:
    """Validate month is 1-12."""
    if month is not None:
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail=f"{param_name} must be between 1 and 12")
    return month


def validate_symbol_path(symbol: str) -> str:
    """Validate and normalize a symbol from URL path."""
    symbol = symbol.upper().strip()
    if not TICKER_PATTERN.match(symbol):
        raise HTTPException(status_code=400, detail=f"Invalid ticker symbol: {symbol}")
    return symbol


def get_ticker_or_404(db: Session, symbol: str) -> Ticker:
    """Get ticker by symbol or raise 404."""
    symbol = validate_symbol_path(symbol)
    ticker = db.query(Ticker).filter(Ticker.symbol == symbol).first()
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")
    return ticker


def require_write_enabled():
    """Block write operations when ENABLE_WRITE_API is False."""
    if not ENABLE_WRITE_API:
        raise HTTPException(
            status_code=403,
            detail="Write operations are disabled. Set ENABLE_WRITE_API=True in config to enable."
        )


# ===========================================
# HEALTH CHECK
# ===========================================

@app.get("/api/health")
def health_check():
    """Health check - verifies API is running and database is reachable."""
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")

    ticker_count = 0
    price_count = 0
    if db_ok:
        try:
            db = SessionLocal()
            ticker_count = db.query(Ticker).count()
            price_count = db.query(MonthlyPrice).count()
            db.close()
        except Exception:
            pass

    status = "healthy" if db_ok else "unhealthy"
    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
        "tickers": ticker_count,
        "price_records": price_count,
        "batch_status": _get_batch_status()["status"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================
# ADMIN ENDPOINTS
# ===========================================

@app.get("/api/admin/write-status")
def admin_write_status():
    """Check if the write API is enabled. Used by admin dashboard."""
    return {"write_enabled": ENABLE_WRITE_API}


@app.get("/api/admin/verify")
def admin_verify(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Verify the logged-in user is an authorized admin.

    Checks the user's email against the user_admin table.
    Returns the user's email and admin status.
    """
    email = (user.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=403, detail="No email associated with this account")

    admin_row = db.query(UserAdmin).filter(
        UserAdmin.email == email
    ).first()

    if not admin_row:
        logger.warning(f"Admin access denied for {email}")
        raise HTTPException(status_code=403, detail="You are not authorized to access the admin dashboard")

    logger.info(f"Admin access granted for {email}")
    return {
        "authorized": True,
        "email": email,
        "name": admin_row.name or user.get("name", ""),
    }


# ===========================================
# AUTH ENDPOINTS
# ===========================================

@app.get("/api/auth/config")
def get_auth_config():
    """Return Auth0 config for frontend SPA SDK initialization.

    Intentionally unauthenticated — frontend needs this before login.
    """
    from app.config import AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE
    return {
        "domain": AUTH0_DOMAIN,
        "clientId": AUTH0_CLIENT_ID,
        "audience": AUTH0_AUDIENCE,
    }


@app.post("/api/auth/login-event")
def log_login_event(request: Request):
    """Log a login event (no-op if no DB table exists)."""
    return {"status": "ok"}


# ===========================================
# TICKER ENDPOINTS
# ===========================================

@app.get("/api/tickers", response_model=list[TickerResponse])
def list_tickers(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all tickers."""
    return db.query(Ticker).order_by(Ticker.symbol).all()


@app.get("/api/tickers/active", response_model=list[TickerResponse])
def list_active_tickers(db: Session = Depends(get_db)):
    """List only active tickers — public, no auth required."""
    return db.query(Ticker).filter(Ticker.active == True).order_by(Ticker.symbol).all()


@app.post("/api/tickers", response_model=TickerResponse, status_code=201)
def create_ticker(data: TickerCreate, db: Session = Depends(get_db)):
    """Add a new ticker.

    No auth required — gated by ENABLE_WRITE_API instead.
    """
    require_write_enabled()
    symbol = data.symbol  # Already validated and uppercased by Pydantic

    # Check max tickers limit
    count = db.query(Ticker).count()
    if count >= MAX_TICKERS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_TICKERS} tickers allowed")

    # Check duplicate
    existing = db.query(Ticker).filter(Ticker.symbol == symbol).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Ticker {symbol} already exists")

    ticker = Ticker(symbol=symbol, name=data.name)
    db.add(ticker)
    db.commit()
    db.refresh(ticker)
    logger.info(f"Created ticker: {symbol}")
    return ticker


@app.put("/api/tickers/{symbol}", response_model=TickerResponse)
def update_ticker(symbol: str, data: TickerUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update ticker name or active status."""
    require_write_enabled()
    ticker = get_ticker_or_404(db, symbol)

    if data.name is not None:
        ticker.name = data.name
    if data.active is not None:
        ticker.active = data.active

    db.commit()
    db.refresh(ticker)
    logger.info(f"Updated ticker: {ticker.symbol} (active={ticker.active})")
    return ticker


@app.delete("/api/tickers/{symbol}", status_code=200)
def delete_ticker(symbol: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a ticker and all its price/dividend data."""
    require_write_enabled()
    ticker = get_ticker_or_404(db, symbol)
    sym = ticker.symbol

    db.delete(ticker)
    db.commit()
    logger.info(f"Deleted ticker: {sym} and all related data")
    return {"message": f"Ticker {sym} and all related data deleted"}


# ===========================================
# PRICE ENDPOINTS
# ===========================================

@app.get("/api/prices/{symbol}", response_model=list[PriceResponse])
def get_prices(
    symbol: str,
    start_year: Optional[int] = Query(None, description="Filter from year"),
    start_month: Optional[int] = Query(None, description="Filter from month (1-12)"),
    end_year: Optional[int] = Query(None, description="Filter to year"),
    end_month: Optional[int] = Query(None, description="Filter to month (1-12)"),
    db: Session = Depends(get_db),
):
    """Get monthly prices for a ticker, optionally filtered by date range."""
    ticker = get_ticker_or_404(db, symbol)

    # Validate inputs
    start_year = validate_year(start_year, "start_year")
    start_month = validate_month(start_month, "start_month")
    end_year = validate_year(end_year, "end_year")
    end_month = validate_month(end_month, "end_month")

    query = db.query(MonthlyPrice).filter(MonthlyPrice.ticker_id == ticker.id)

    if start_year and start_month:
        query = query.filter(
            (MonthlyPrice.year > start_year) |
            ((MonthlyPrice.year == start_year) & (MonthlyPrice.month >= start_month))
        )
    elif start_year:
        query = query.filter(MonthlyPrice.year >= start_year)

    if end_year and end_month:
        query = query.filter(
            (MonthlyPrice.year < end_year) |
            ((MonthlyPrice.year == end_year) & (MonthlyPrice.month <= end_month))
        )
    elif end_year:
        query = query.filter(MonthlyPrice.year <= end_year)

    prices = query.order_by(MonthlyPrice.year, MonthlyPrice.month).all()
    return prices


@app.get("/api/prices/{symbol}/latest", response_model=PriceResponse)
def get_latest_price(symbol: str, db: Session = Depends(get_db)):
    """Get the most recent month's price for a ticker."""
    ticker = get_ticker_or_404(db, symbol)

    price = (
        db.query(MonthlyPrice)
        .filter(MonthlyPrice.ticker_id == ticker.id)
        .order_by(MonthlyPrice.year.desc(), MonthlyPrice.month.desc())
        .first()
    )

    if not price:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker.symbol}")

    return price


# ===========================================
# DIVIDEND ENDPOINTS
# ===========================================

@app.get("/api/dividends/{symbol}", response_model=list[DividendResponse])
def get_dividends(
    symbol: str,
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get dividends for a ticker, optionally filtered by year range."""
    ticker = get_ticker_or_404(db, symbol)

    start_year = validate_year(start_year, "start_year")
    end_year = validate_year(end_year, "end_year")

    query = db.query(Dividend).filter(Dividend.ticker_id == ticker.id)

    if start_year:
        query = query.filter(extract('year', Dividend.pay_date) >= start_year)
    if end_year:
        query = query.filter(extract('year', Dividend.pay_date) <= end_year)

    dividends = query.order_by(Dividend.pay_date).all()

    return [
        DividendResponse(pay_date=d.pay_date.isoformat(), amount=d.amount)
        for d in dividends
    ]


# ===========================================
# SIMULATION DATA ENDPOINT
# ===========================================

@app.get("/api/simulation-data/{symbol}", response_model=SimulationDataResponse)
def get_simulation_data(
    symbol: str,
    start_year: Optional[int] = Query(None),
    start_month: Optional[int] = Query(1),
    end_year: Optional[int] = Query(None),
    end_month: Optional[int] = Query(12),
    db: Session = Depends(get_db),
):
    """Get combined price + dividend data for portfolio simulation.

    Returns monthly prices with any dividends that fell within each month.
    This is the primary endpoint the frontend simulation will use.
    """
    ticker = get_ticker_or_404(db, symbol)

    start_year = validate_year(start_year, "start_year")
    start_month = validate_month(start_month, "start_month")
    end_year = validate_year(end_year, "end_year")
    end_month = validate_month(end_month, "end_month")

    # Get prices
    price_query = db.query(MonthlyPrice).filter(MonthlyPrice.ticker_id == ticker.id)
    if start_year:
        price_query = price_query.filter(
            (MonthlyPrice.year > start_year) |
            ((MonthlyPrice.year == start_year) & (MonthlyPrice.month >= start_month))
        )
    if end_year:
        price_query = price_query.filter(
            (MonthlyPrice.year < end_year) |
            ((MonthlyPrice.year == end_year) & (MonthlyPrice.month <= end_month))
        )
    prices = price_query.order_by(MonthlyPrice.year, MonthlyPrice.month).all()

    # Get all dividends for this ticker
    dividends = db.query(Dividend).filter(Dividend.ticker_id == ticker.id).order_by(Dividend.pay_date).all()

    # Build monthly data with dividends mapped to their month
    monthly_data = []
    for price in prices:
        month_divs = [
            DividendResponse(pay_date=d.pay_date.isoformat(), amount=d.amount)
            for d in dividends
            if d.pay_date.year == price.year and d.pay_date.month == price.month
        ]

        monthly_data.append(SimulationPriceRow(
            year=price.year,
            month=price.month,
            high=price.high,
            low=price.low,
            close=price.close,
            adj_close=price.adj_close,
            dividends=month_divs,
        ))

    return SimulationDataResponse(
        symbol=ticker.symbol,
        name=ticker.name,
        monthly_data=monthly_data,
    )


# ===========================================
# MONEY MARKET RATE ENDPOINTS
# ===========================================

class MonthlyRateResponse(BaseModel):
    year: int
    month: int
    rate: float

    class Config:
        from_attributes = True


class AnnualRateResponse(BaseModel):
    year: int
    avg_rate: float

    class Config:
        from_attributes = True


@app.get("/api/mm-rates/monthly", response_model=list[MonthlyRateResponse])
def get_monthly_mm_rates(
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get monthly average money market rates."""
    from app.mm_rates import MonthlyMoneyMarketRate

    start_year = validate_year(start_year, "start_year")
    end_year = validate_year(end_year, "end_year")

    query = db.query(MonthlyMoneyMarketRate)
    if start_year:
        query = query.filter(MonthlyMoneyMarketRate.year >= start_year)
    if end_year:
        query = query.filter(MonthlyMoneyMarketRate.year <= end_year)

    return query.order_by(MonthlyMoneyMarketRate.year, MonthlyMoneyMarketRate.month).all()


@app.get("/api/mm-rates/annual", response_model=list[AnnualRateResponse])
def get_annual_mm_rates(
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get annual average money market rates."""
    from app.mm_rates import AnnualMoneyMarketRate

    start_year = validate_year(start_year, "start_year")
    end_year = validate_year(end_year, "end_year")

    query = db.query(AnnualMoneyMarketRate)
    if start_year:
        query = query.filter(AnnualMoneyMarketRate.year >= start_year)
    if end_year:
        query = query.filter(AnnualMoneyMarketRate.year <= end_year)

    return query.order_by(AnnualMoneyMarketRate.year).all()


@app.get("/api/mm-rates/annual/{year}", response_model=AnnualRateResponse)
def get_annual_mm_rate_by_year(year: int, db: Session = Depends(get_db)):
    """Get money market rate for a specific year."""
    from app.mm_rates import AnnualMoneyMarketRate

    year = validate_year(year, "year")

    rate = db.query(AnnualMoneyMarketRate).filter(AnnualMoneyMarketRate.year == year).first()
    if not rate:
        raise HTTPException(status_code=404, detail=f"No money market rate for year {year}")
    return rate


# ===========================================
# BATCH ENDPOINTS (async via background thread)
# ===========================================

def _run_batch_in_background(symbols: list[str], mode: str, months: int = None):
    """Run batch fetch+load in a background thread."""
    _update_batch_status(
        status="running",
        mode=mode,
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
        tickers_requested=symbols,
        summary=None,
    )

    try:
        from app.loader import load_all
        from app.fetcher import fetch_all_tickers

        fetch_results = fetch_all_tickers(symbols, mode=mode, delay_seconds=1.0, months=months)

        db = SessionLocal()
        try:
            summary = load_all(db, fetch_results, mode=mode)
        finally:
            db.close()

        _update_batch_status(
            status="completed",
            summary=summary,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"Batch {mode} completed for {len(symbols)} tickers")

    except Exception as e:
        logger.error(f"Batch {mode} failed: {traceback.format_exc()}")
        _update_batch_status(
            status="failed",
            summary={"error": str(e)},
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


def _run_fred_in_background(mode: str):
    """Run FRED rate fetch+load in a background thread."""
    _update_batch_status(
        status="running",
        mode=f"fred-{mode}",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
        tickers_requested=["FRED:FEDFUNDS"],
        summary=None,
    )

    try:
        from app.fred_fetcher import get_monthly_rates, get_monthly_rates_incremental
        from app.mm_rates import load_all_rates

        if mode == "full":
            monthly_df = get_monthly_rates()
        else:
            monthly_df = get_monthly_rates_incremental()

        db = SessionLocal()
        try:
            summary = load_all_rates(db, monthly_df, mode=mode)
        finally:
            db.close()

        _update_batch_status(
            status="completed",
            summary=summary,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"FRED {mode} load completed")

    except Exception as e:
        logger.error(f"FRED {mode} failed: {traceback.format_exc()}")
        _update_batch_status(
            status="failed",
            summary={"error": str(e)},
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


@app.post("/api/batch/full", response_model=BatchResponse)
def run_batch_full(data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger a full history data load (runs in background).

    No auth required — gated by ENABLE_WRITE_API instead.
    """
    require_write_enabled()
    # Check if a batch is already running
    current = _get_batch_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A batch job is already running. Check /api/batch/status")

    from app.loader import get_active_tickers

    symbols = data.symbols
    if not symbols:
        symbols = get_active_tickers(db)

    if not symbols:
        raise HTTPException(status_code=400, detail="No active tickers found")

    # Start background thread
    thread = threading.Thread(target=_run_batch_in_background, args=(symbols, "full"), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Full load started for {len(symbols)} tickers. Check /api/batch/status for progress.",
    )


@app.post("/api/batch/full-new", response_model=BatchResponse)
def run_batch_full_new(db: Session = Depends(get_db)):
    """Trigger a full history load ONLY for tickers that have no price data yet.

    Skips tickers that already have data — safe and efficient for loading
    newly added tickers without re-fetching everything.
    No auth required — gated by ENABLE_WRITE_API instead.
    """
    require_write_enabled()
    current = _get_batch_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A batch job is already running. Check /api/batch/status")

    from app.loader import get_tickers_without_data

    symbols = get_tickers_without_data(db)

    if not symbols:
        return BatchResponse(
            status="skipped",
            message="All active tickers already have price data. Nothing to load.",
        )

    thread = threading.Thread(target=_run_batch_in_background, args=(symbols, "full"), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Full load started for {len(symbols)} new tickers: {', '.join(symbols)}. Check /api/batch/status for progress.",
    )


@app.post("/api/batch/incremental", response_model=BatchResponse)
def run_batch_incremental(data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger an incremental data load (runs in background).

    No auth required — gated by ENABLE_WRITE_API instead.
    """
    require_write_enabled()
    current = _get_batch_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A batch job is already running. Check /api/batch/status")

    from app.loader import get_active_tickers

    symbols = data.symbols
    if not symbols:
        symbols = get_active_tickers(db)

    if not symbols:
        raise HTTPException(status_code=400, detail="No active tickers found")

    months = data.months
    thread = threading.Thread(target=_run_batch_in_background, args=(symbols, "incremental", months), daemon=True)
    thread.start()

    months_msg = f" ({months} months)" if months else ""
    return BatchResponse(
        status="started",
        message=f"Incremental load started for {len(symbols)} tickers{months_msg}. Check /api/batch/status for progress.",
    )


@app.post("/api/batch/fred-full", response_model=BatchResponse)
def run_fred_full():
    """Trigger a full FRED federal funds rate load (runs in background).

    No auth required — gated by ENABLE_WRITE_API instead.
    """
    require_write_enabled()
    current = _get_batch_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A batch job is already running. Check /api/batch/status")

    thread = threading.Thread(target=_run_fred_in_background, args=("full",), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message="FRED full rate load started. Check /api/batch/status for progress.",
    )


@app.post("/api/batch/fred-incremental", response_model=BatchResponse)
def run_fred_incremental():
    """Trigger an incremental FRED rate load (last 3 months, runs in background).

    No auth required — gated by ENABLE_WRITE_API instead.
    """
    require_write_enabled()
    current = _get_batch_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A batch job is already running. Check /api/batch/status")

    thread = threading.Thread(target=_run_fred_in_background, args=("incremental",), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message="FRED incremental rate load started (last 3 months). Check /api/batch/status for progress.",
    )


@app.get("/api/batch/status")
def get_batch_status():
    """Get the status of the last batch run."""
    return _get_batch_status()


# ===========================================
# SECTOR PERFORMANCE (annual returns + dividends from DB)
# ===========================================

@app.get("/api/sector-performance")
def get_sector_performance(
    db: Session = Depends(get_db),
):
    """Compute 20-year annual return & dividend data for all sector ETFs.

    Return = (Dec close[Y] - Dec close[Y-1]) / Dec close[Y-1] * 100
    Dividend = sum of all dividends paid during year Y
    """
    sector_symbols = [
        "XLK", "XLV", "XLF", "XLE", "XLY", "XLP",
        "XLI", "XLB", "XLU", "XLC", "XLRE", "VTI",
    ]

    results = {}
    for sym in sector_symbols:
        ticker = db.query(Ticker).filter(Ticker.symbol == sym).first()
        if not ticker:
            continue

        # December close prices keyed by year
        dec_rows = (
            db.query(MonthlyPrice.year, MonthlyPrice.close)
            .filter(
                and_(
                    MonthlyPrice.ticker_id == ticker.id,
                    MonthlyPrice.month == 12,
                )
            )
            .order_by(MonthlyPrice.year)
            .all()
        )
        dec_map = {y: c for y, c in dec_rows if c is not None}

        # Annual dividend totals
        from sqlalchemy import func as sa_func
        div_rows = (
            db.query(
                extract("year", Dividend.pay_date).label("yr"),
                sa_func.sum(Dividend.amount).label("total"),
            )
            .filter(Dividend.ticker_id == ticker.id)
            .group_by(extract("year", Dividend.pay_date))
            .all()
        )
        div_map = {int(yr): float(total) for yr, total in div_rows}

        yearly = {}
        for y in sorted(dec_map.keys()):
            if y - 1 not in dec_map:
                continue
            prev = dec_map[y - 1]
            curr = dec_map[y]
            yearly[str(y)] = {
                "return": round(((curr - prev) / prev) * 100, 2),
                "dividend": round(div_map.get(y, 0), 2),
                "prev_close": round(prev, 2),
                "close": round(curr, 2),
            }

        results[sym] = {"name": ticker.name, "data": yearly}

    return results


# ===========================================
# SECTOR MONTHLY (all monthly close prices for sector ETFs)
# ===========================================

@app.get("/api/sector-monthly")
def get_sector_monthly(
    db: Session = Depends(get_db),
):
    """Return all monthly close prices for sector ETFs.

    Used by correlation, drawdown, growth-chart, and risk-return pages.
    Returns dict keyed by symbol with name and monthly array of {year, month, close}.
    """
    sector_symbols = [
        "XLK", "XLV", "XLF", "XLE", "XLY", "XLP",
        "XLI", "XLB", "XLU", "XLC", "XLRE", "VTI",
    ]

    results = {}
    for sym in sector_symbols:
        ticker = db.query(Ticker).filter(Ticker.symbol == sym).first()
        if not ticker:
            continue

        rows = (
            db.query(MonthlyPrice.year, MonthlyPrice.month, MonthlyPrice.close)
            .filter(MonthlyPrice.ticker_id == ticker.id)
            .order_by(MonthlyPrice.year, MonthlyPrice.month)
            .all()
        )

        monthly = []
        for y, m, c in rows:
            if c is not None:
                monthly.append({"year": y, "month": m, "close": round(c, 2)})

        # Also include annual dividends for growth calculations
        from sqlalchemy import func as sa_func
        div_rows = (
            db.query(
                extract("year", Dividend.pay_date).label("yr"),
                extract("month", Dividend.pay_date).label("mo"),
                sa_func.sum(Dividend.amount).label("total"),
            )
            .filter(Dividend.ticker_id == ticker.id)
            .group_by(
                extract("year", Dividend.pay_date),
                extract("month", Dividend.pay_date),
            )
            .all()
        )
        monthly_divs = {}
        for yr, mo, total in div_rows:
            monthly_divs[f"{int(yr)}-{int(mo)}"] = round(float(total), 4)

        results[sym] = {
            "name": ticker.name,
            "monthly": monthly,
            "monthly_dividends": monthly_divs,
        }

    return results


# ===========================================
# SERVE FRONTEND (must be LAST — catch-all)
# ===========================================

_frontend_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend"

if _frontend_dir.exists():
    @app.get("/")
    def serve_index():
        """Serve the home/landing page at root."""
        return FileResponse(str(_frontend_dir / "index.html"))

    @app.get("/index.html")
    def serve_index_html():
        """Serve the home/landing page."""
        return FileResponse(str(_frontend_dir / "index.html"))

    @app.get("/help.html")
    def serve_help():
        """Legacy alias — redirects to home page."""
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")

    @app.get("/simulator-guide.html")
    def serve_simulator_guide():
        """Serve the simulator how-it-works guide page."""
        return FileResponse(str(_frontend_dir / "simulator-guide.html"))

    @app.get("/admin.html")
    def serve_admin():
        """Serve the admin dashboard page (Auth0 protected)."""
        return FileResponse(str(_frontend_dir / "admin.html"))

    @app.get("/sector-performance.html")
    def serve_sector_performance():
        """Serve the sector performance page."""
        return FileResponse(str(_frontend_dir / "sector-performance.html"))

    @app.get("/correlation.html")
    def serve_correlation():
        return FileResponse(str(_frontend_dir / "correlation.html"))

    @app.get("/drawdown.html")
    def serve_drawdown():
        return FileResponse(str(_frontend_dir / "drawdown.html"))

    @app.get("/sector-rotation.html")
    def serve_sector_rotation():
        return FileResponse(str(_frontend_dir / "sector-rotation.html"))

    @app.get("/dividend-growth.html")
    def serve_dividend_growth():
        return FileResponse(str(_frontend_dir / "dividend-growth.html"))

    @app.get("/growth-chart.html")
    def serve_growth_chart():
        return FileResponse(str(_frontend_dir / "growth-chart.html"))

    @app.get("/risk-return.html")
    def serve_risk_return():
        return FileResponse(str(_frontend_dir / "risk-return.html"))

    app.mount("/", StaticFiles(directory=str(_frontend_dir)), name="frontend")

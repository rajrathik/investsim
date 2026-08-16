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
    POST   /api/tickers                     - Add a new ticker (requires auth + write API enabled)
    PUT    /api/tickers/{symbol}            - Update ticker name/active (requires auth + write)
    DELETE /api/tickers/{symbol}            - Delete ticker and all data (requires auth + write)

  Prices:
    GET    /api/prices/{symbol}             - Get monthly prices for a ticker (public)
    GET    /api/prices/{symbol}/latest      - Get latest month's price (public)

  Dividends:
    GET    /api/dividends/{symbol}          - Get dividends for a ticker (public)

  Current Quotes:
    GET    /api/quotes?symbols=A,B,C        - Current price + 52w range for any tickers (public, cached 15min)

  Simulation Data:
    GET    /api/simulation-data/{symbol}    - Combined prices + dividends for simulation (public)

  Money Market Rates:
    GET    /api/mm-rates/monthly            - Monthly FRED federal funds rates (public)
    GET    /api/mm-rates/annual             - Annual average FRED rates (public)
    GET    /api/mm-rates/annual/{year}      - Rate for a specific year (public)

  Sector Analytics:
    GET    /api/sector-performance          - Annual returns + dividends for sector ETFs (public)
    GET    /api/sector-monthly              - Monthly close prices for sector ETFs (public)

  Batch (requires auth + write API enabled):
    POST   /api/batch/full                  - Full history load for ALL tickers (async)
    POST   /api/batch/full-new              - Full history load for NEW tickers only (async)
    POST   /api/batch/incremental           - Incremental load for recent months (async)
    POST   /api/batch/fred-full             - Full FRED rate history load (async)
    POST   /api/batch/fred-incremental      - Incremental FRED rate load — last 3 months (async)
    GET    /api/batch/status                - Status of last batch run

  Daily Price Tables (SPY / OEF):
    POST   /api/batch/daily-prices/{ticker}/full         - One-time full history load (auth + write, async)
    POST   /api/batch/daily-prices/{ticker}/incremental   - Append missing days only (auth + write, async)
    GET    /api/batch/daily-prices/status                 - Status of last daily-price load
    GET    /api/daily-prices/stats                        - Row count + date range per ticker (public)

  ETF Directory Monthly History (isolated table, one ticker at a time):
    POST   /api/batch/etf-history/full           - One-time full history load, all 81 tickers (auth + write, async)
    POST   /api/batch/etf-history/incremental     - Append missing closed months only (auth + write, async)
    GET    /api/batch/etf-history/status          - Status of last ETF history load
    GET    /api/etf-directory/history-stats       - Row count + ticker coverage + date range (public)
    GET    /api/etf-directory/10yr-range          - 10yr high/low + price-then-vs-now per ticker (public)
    GET    /api/etf-directory/history-summary     - All range periods (1y/5y/10y/max) + sparkline paths (public)

  Rate Limits (per IP):
    Default:  60 requests/minute for all endpoints
    Reads:    30/minute for expensive sector-performance and sector-monthly queries
    Writes:   10/minute for ticker CRUD and simulation saves
    Batch:    5/minute for batch data load endpoints
    Tracking: 30/minute for pageview tracking

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
import json
import uuid
import time
import logging
import threading
import traceback
from datetime import datetime, date, timedelta, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
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
from app.models import Ticker, MonthlyPrice, Dividend, UserLogin, UserAdmin, ApiRequestLog, SavedSimulation, StackEarnSavingsTier, StackEarnGoalTier, SpyDailyPrice, OefDailyPrice
from app.config import MAX_TICKERS, ENABLE_WRITE_API, ALLOWED_ORIGINS
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


# ===========================================
# RATE LIMITING (slowapi)
# ===========================================
# Default: 60 requests/minute per IP for all endpoints.
# Tighter limits on write/auth endpoints to prevent abuse.
# Override per-route with @limiter.limit("N/minute") decorator.

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Allow frontend to connect (adjust origins when deploying)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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


# ===========================================
# DAILY PRICE TABLES (SPY / OEF) — separate status tracker so a daily-price
# load never clobbers the Yahoo/FRED batch status panel above.
# ===========================================

DAILY_PRICE_MODELS = {
    "SPY": SpyDailyPrice,
    "OEF": OefDailyPrice,
}

_daily_lock = threading.Lock()
_daily_status = {
    "ticker": None,
    "mode": None,
    "status": "idle",
    "summary": None,
    "started_at": None,
    "completed_at": None,
}


def _update_daily_status(**kwargs):
    with _daily_lock:
        _daily_status.update(kwargs)


def _get_daily_status():
    with _daily_lock:
        return dict(_daily_status)


def _run_daily_load_in_background(ticker: str, mode: str):
    """Fetch + append daily prices for one ticker in a background thread.

    mode='full': everything Yahoo has (one-time initial load).
    mode='incremental': only the days after whatever's already on file
    (max(price_date) + 1 day through today) -- append-only, no updates.
    """
    _update_daily_status(
        ticker=ticker,
        mode=mode,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
        summary=None,
    )

    try:
        from app.fetcher import get_daily_prices
        from app.loader import load_daily_prices, get_max_daily_date

        model = DAILY_PRICE_MODELS[ticker]
        db = SessionLocal()
        try:
            start_date = None
            if mode == "incremental":
                max_date = get_max_daily_date(db, model, ticker)
                if max_date is None:
                    # Nothing on file yet -- behave like a full load.
                    start_date = None
                else:
                    next_day = max_date + timedelta(days=1)
                    if next_day > date.today():
                        summary = {"inserted": 0, "skipped": 0, "note": "Already up to date"}
                        _update_daily_status(
                            status="completed",
                            summary=summary,
                            completed_at=datetime.now(timezone.utc).isoformat(),
                        )
                        return
                    start_date = next_day.isoformat()

            prices_df = get_daily_prices(ticker, start_date=start_date, end_date=None)
            summary = load_daily_prices(db, model, ticker, prices_df)
        finally:
            db.close()

        _update_daily_status(
            status="completed",
            summary=summary,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"Daily {mode} load completed for {ticker}: {summary}")

    except Exception as e:
        logger.error(f"Daily {mode} load failed for {ticker}: {traceback.format_exc()}")
        _update_daily_status(
            status="failed",
            summary={"error": str(e)},
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


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


def require_admin(user: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Verify the caller is an authorized admin (Auth0 token + user_admin whitelist).

    Use as a dependency on any endpoint that should be admin-only:
        user: dict = Depends(require_admin)
    A valid Auth0 token alone is NOT enough — the token's email must also
    appear in the user_admin table. Any signed-in public user has a valid
    token, so endpoints gated only by get_current_user are reachable by
    anyone with an account, not just admins.
    """
    email = (user.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=403, detail="No email associated with this account")

    admin_row = db.query(UserAdmin).filter(UserAdmin.email == email).first()
    if not admin_row:
        logger.warning(f"Admin access denied for {email}")
        raise HTTPException(status_code=403, detail="You are not authorized to access the admin dashboard")

    logger.info(f"Admin access granted for {email}")
    return {**user, "admin_name": admin_row.name or user.get("name", "")}


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
def admin_verify(user: dict = Depends(require_admin)):
    """Verify the logged-in user is an authorized admin.

    Checks the user's email against the user_admin table.
    Returns the user's email and admin status.
    """
    return {
        "authorized": True,
        "email": (user.get("email") or "").lower().strip(),
        "name": user.get("admin_name", ""),
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


class LoginEventBody(BaseModel):
    auth0_user_id: str
    email: Optional[str] = None
    name: Optional[str] = None


@app.post("/api/auth/login-event")
@limiter.limit("10/minute")
def log_login_event(body: LoginEventBody, request: Request, db: Session = Depends(get_db)):
    """Log a public user login event into user_logins table."""
    try:
        row = UserLogin(
            auth0_user_id=body.auth0_user_id,
            email=body.email,
            name=body.name,
            ip_address=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:500],
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        # Non-critical — don't fail the login flow
        pass
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
@limiter.limit("10/minute")
def create_ticker(data: TickerCreate, request: Request, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Add a new ticker. Requires Auth0 token + ENABLE_WRITE_API."""
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
@limiter.limit("10/minute")
def update_ticker(symbol: str, data: TickerUpdate, request: Request, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Update ticker name or active status. Requires Auth0 token + ENABLE_WRITE_API."""
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
@limiter.limit("10/minute")
def delete_ticker(symbol: str, request: Request, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Delete a ticker and all its price/dividend data. Requires Auth0 token + ENABLE_WRITE_API."""
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
# CURRENT QUOTES (price + 52-week range) — for ETF Directory and similar
# pages that need a live snapshot for tickers outside the tickers/
# monthly_prices system. Cached in-memory per-symbol so repeat page loads
# don't re-hit Yahoo every time.
# ===========================================

_quote_cache_lock = threading.Lock()
_quote_cache = {}  # symbol -> {"data": {...}, "fetched_at": datetime}
QUOTE_CACHE_TTL_SECONDS = 900  # 15 minutes


@app.get("/api/quotes")
@limiter.limit("20/minute")
def get_quotes(request: Request, symbols: str, db: Session = Depends(get_db)):
    """Current price + 52-week range for a comma-separated list of tickers.

    Public, read-only. Not tied to the tickers/monthly_prices tables --
    works for any valid Yahoo symbol. Symbols that fail to resolve are
    simply omitted from the response, not errored.

    Every fresh (non-cached) fetch is also saved to daily_quotes, keyed by
    (ticker, actual trade date) -- see fetcher.get_current_quotes() for why
    that's the real trade date and not the server's calendar date. Repeat
    calls before a new trading day just overwrite the same saved row.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(symbol_list) > 100:
        raise HTTPException(status_code=400, detail="Max 100 symbols per request")

    from app.fetcher import get_current_quotes
    from app.loader import save_daily_quotes

    now = datetime.now(timezone.utc)
    results = {}
    to_fetch = []

    with _quote_cache_lock:
        for sym in symbol_list:
            cached = _quote_cache.get(sym)
            if cached and (now - cached["fetched_at"]).total_seconds() < QUOTE_CACHE_TTL_SECONDS:
                results[sym] = cached["data"]
            else:
                to_fetch.append(sym)

    if to_fetch:
        fresh = get_current_quotes(to_fetch)
        with _quote_cache_lock:
            for sym, data in fresh.items():
                _quote_cache[sym] = {"data": data, "fetched_at": now}
                results[sym] = data
        if fresh:
            save_daily_quotes(db, fresh)

    return results


# ===========================================
# ETF DIRECTORY MONTHLY HISTORY (isolated from every other pipeline --
# see EtfDirectoryMonthlyHistory's docstring in models.py). One admin
# button walks the curated ticker list ONE SECURITY AT A TIME (not
# parallel) for the initial full backfill; a separate button appends only
# the closed months missing since each ticker's last load.
# ===========================================

_etf_history_lock = threading.Lock()
_etf_history_status = {
    "mode": None,
    "status": "idle",
    "summary": None,
    "started_at": None,
    "completed_at": None,
    "current_ticker": None,
    "progress": None,
}


def _update_etf_history_status(**kwargs):
    with _etf_history_lock:
        _etf_history_status.update(kwargs)


def _get_etf_history_status():
    with _etf_history_lock:
        return dict(_etf_history_status)


def _run_etf_history_in_background(mode: str):
    """Full or incremental load of etf_directory_monthly_history, one
    ticker at a time (sequential, 1s pause between each -- matches the
    existing fetch_all_tickers rate-limiting convention).
    """
    from app.fetcher import get_monthly_prices, get_dividends
    from app.loader import get_etf_directory_tickers, get_max_etf_month, load_etf_monthly_history

    _update_etf_history_status(
        mode=mode, status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None, summary=None, current_ticker=None, progress=None,
    )

    tickers = get_etf_directory_tickers()
    today = date.today()
    summary = {}

    try:
        db = SessionLocal()
        try:
            for i, ticker in enumerate(tickers):
                _update_etf_history_status(current_ticker=ticker, progress=f"{i+1}/{len(tickers)}")

                start_date = None
                if mode == "incremental":
                    last = get_max_etf_month(db, ticker)
                    if last is not None:
                        y, m = last
                        next_month, next_year = (m + 1, y) if m < 12 else (1, y + 1)
                        # If the next month we'd need is this calendar month or later,
                        # there's nothing to fetch -- the current month is never brought
                        # in, so >= (not >) is the correct "nothing missing" check.
                        if (next_year, next_month) >= (today.year, today.month):
                            summary[ticker] = {"inserted": 0, "skipped": 0, "note": "already up to date"}
                            continue
                        start_date = date(next_year, next_month, 1).isoformat()
                    # last is None -> no history yet for this ticker; fall through
                    # to a full fetch (start_date stays None) same as a first load.

                try:
                    prices_df = get_monthly_prices(ticker, start_date=start_date, end_date=None)
                    divs_df = get_dividends(ticker, start_date=start_date, end_date=None)
                except Exception as e:
                    summary[ticker] = {"error": str(e)}
                    logger.error(f"ETF history fetch failed for {ticker}: {e}")
                    if i < len(tickers) - 1:
                        time.sleep(1.0)
                    continue

                # Never write the current, still-in-progress calendar month.
                if not prices_df.empty:
                    prices_df = prices_df[
                        ~((prices_df["year"] == today.year) & (prices_df["month"] == today.month))
                    ]

                summary[ticker] = load_etf_monthly_history(db, ticker, prices_df, divs_df)

                if i < len(tickers) - 1:
                    time.sleep(1.0)
        finally:
            db.close()

        _update_etf_history_status(
            status="completed", summary=summary, current_ticker=None, progress=None,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"ETF directory history {mode} load completed for {len(tickers)} tickers")

    except Exception as e:
        logger.error(f"ETF directory history {mode} load failed: {traceback.format_exc()}")
        _update_etf_history_status(
            status="failed", summary={"error": str(e)}, current_ticker=None, progress=None,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


@app.post("/api/batch/etf-history/full", response_model=BatchResponse)
@limiter.limit("5/minute")
def run_etf_history_full(request: Request, user: dict = Depends(require_admin)):
    """One-time full history load for every ETF Directory ticker, one
    security at a time. Runs in background; poll /api/batch/etf-history/status.
    """
    require_write_enabled()
    current = _get_etf_history_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="An ETF history load is already running. Check /api/batch/etf-history/status")

    thread = threading.Thread(target=_run_etf_history_in_background, args=("full",), daemon=True)
    thread.start()

    return BatchResponse(status="started", message="Full ETF directory history load started. Check /api/batch/etf-history/status for progress.")


@app.post("/api/batch/etf-history/incremental", response_model=BatchResponse)
@limiter.limit("5/minute")
def run_etf_history_incremental(request: Request, user: dict = Depends(require_admin)):
    """Append missing closed months for every ETF Directory ticker, one
    security at a time. Never writes the current in-progress month.
    """
    require_write_enabled()
    current = _get_etf_history_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="An ETF history load is already running. Check /api/batch/etf-history/status")

    thread = threading.Thread(target=_run_etf_history_in_background, args=("incremental",), daemon=True)
    thread.start()

    return BatchResponse(status="started", message="Incremental ETF directory history load started. Check /api/batch/etf-history/status for progress.")


@app.get("/api/batch/etf-history/status")
def get_etf_history_status():
    """Get the status of the last ETF directory history load."""
    return _get_etf_history_status()


@app.get("/api/etf-directory/history-stats")
def get_etf_directory_history_stats(db: Session = Depends(get_db)):
    """Row count, ticker coverage, and date range for etf_directory_monthly_history."""
    from app.loader import get_etf_history_stats
    return get_etf_history_stats(db)


@app.get("/api/etf-directory/history-summary")
@limiter.limit("30/minute")
def get_etf_directory_history_summary(request: Request, symbols: str, db: Session = Depends(get_db)):
    """High/low/return + sparkline path for every range period (1y/5y/10y/max)
    in one call, from etf_directory_monthly_history. Public, read-only.

    Deliberately returns all periods at once: the underlying data only changes
    when the monthly history load runs, so the frontend caches this for the
    session and range-chip switching costs no network.
    """
    from app.loader import get_etf_history_summary

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(symbol_list) > 100:
        raise HTTPException(status_code=400, detail="Max 100 symbols per request")

    return get_etf_history_summary(db, symbol_list)


@app.get("/api/etf-directory/10yr-range")
@limiter.limit("30/minute")
def get_etf_directory_10yr_range(request: Request, symbols: str, db: Session = Depends(get_db)):
    """10-year high/low range + price-then-vs-now comparison for a batch of
    tickers, computed from etf_directory_monthly_history. Public, read-only.
    Tickers with no history loaded yet are simply omitted from the response.
    """
    from app.loader import get_etf_10yr_range

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(symbol_list) > 100:
        raise HTTPException(status_code=400, detail="Max 100 symbols per request")

    return get_etf_10yr_range(db, symbol_list)


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


def _run_fred_in_background(mode: str, months: int = None):
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
            monthly_df = get_monthly_rates_incremental(months=months or 3)

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
@limiter.limit("5/minute")
def run_batch_full(request: Request, user: dict = Depends(require_admin), data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger a full history data load (runs in background).
    Requires Auth0 token + ENABLE_WRITE_API.
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
@limiter.limit("5/minute")
def run_batch_full_new(request: Request, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Trigger a full history load ONLY for tickers that have no price data yet.

    Skips tickers that already have data — safe and efficient for loading
    newly added tickers without re-fetching everything.
    Requires Auth0 token + ENABLE_WRITE_API.
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
@limiter.limit("5/minute")
def run_batch_incremental(request: Request, user: dict = Depends(require_admin), data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger an incremental data load (runs in background).
    Requires Auth0 token + ENABLE_WRITE_API.
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
@limiter.limit("5/minute")
def run_fred_full(request: Request, user: dict = Depends(require_admin)):
    """Trigger a full FRED federal funds rate load (runs in background).
    Requires Auth0 token + ENABLE_WRITE_API.
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
@limiter.limit("5/minute")
def run_fred_incremental(request: Request, user: dict = Depends(require_admin), data: BatchRequest = BatchRequest()):
    """Trigger an incremental FRED rate load (runs in background).
    Same "months" field as the Yahoo incremental batch (default 3 if omitted).
    Requires Auth0 token + ENABLE_WRITE_API.
    """
    require_write_enabled()
    current = _get_batch_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A batch job is already running. Check /api/batch/status")

    thread = threading.Thread(target=_run_fred_in_background, args=("incremental", data.months), daemon=True)
    thread.start()

    months_msg = f" (last {data.months} months)" if data.months else " (last 3 months)"
    return BatchResponse(
        status="started",
        message=f"FRED incremental rate load started{months_msg}. Check /api/batch/status for progress.",
    )


def _run_current_month_in_background(symbols: list[str]):
    """Fetch+load just the current calendar month, across Yahoo tickers AND FRED,
    in one job. Safe to re-run any day of the month — each run overwrites the
    same current-month row with the latest data; it settles into the final
    value once the month actually closes. Runs in a background thread.
    """
    _update_batch_status(
        status="running",
        mode="current-month",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
        tickers_requested=symbols + ["FRED:FEDFUNDS"],
        summary=None,
    )

    try:
        from app.loader import load_all
        from app.fetcher import fetch_all_tickers
        from app.fred_fetcher import get_monthly_rates_current_month
        from app.mm_rates import load_all_rates

        # --- Tickers (Yahoo) ---
        fetch_results = fetch_all_tickers(symbols, mode="current-month", delay_seconds=1.0)

        db = SessionLocal()
        try:
            # Loader upserts by (year, month) regardless of how the date
            # window was chosen — "incremental" mode here just means
            # update-if-exists, which is what we want for a live current-month row.
            ticker_summary = load_all(db, fetch_results, mode="incremental")

            # --- FRED ---
            fred_df = get_monthly_rates_current_month()
            if fred_df.empty:
                fred_summary = {"note": "No FRED observation published yet for the current month"}
            else:
                fred_summary = load_all_rates(db, fred_df, mode="incremental")
        finally:
            db.close()

        _update_batch_status(
            status="completed",
            summary={"tickers": ticker_summary, "fred": fred_summary},
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Current-month load completed")

    except Exception as e:
        logger.error(f"Current-month load failed: {traceback.format_exc()}")
        _update_batch_status(
            status="failed",
            summary={"error": str(e)},
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


@app.post("/api/batch/current-month", response_model=BatchResponse)
@limiter.limit("5/minute")
def run_batch_current_month(request: Request, user: dict = Depends(require_admin), data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger a current-calendar-month load across all active tickers AND FRED
    (runs in background). Safe to re-run repeatedly through the month — each
    run overwrites the same current-month row with the latest data.
    Requires Auth0 token + ENABLE_WRITE_API.
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

    thread = threading.Thread(target=_run_current_month_in_background, args=(symbols,), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Current-month load started for {len(symbols)} tickers + FRED. Check /api/batch/status for progress.",
    )


@app.get("/api/batch/status")
def get_batch_status():
    """Get the status of the last batch run."""
    return _get_batch_status()


# ===========================================
# DAILY PRICE TABLES (SPY / OEF)
# ===========================================

def _validate_daily_ticker(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if ticker not in DAILY_PRICE_MODELS:
        raise HTTPException(
            status_code=404,
            detail=f"No daily-prices table for '{ticker}'. Available: {', '.join(DAILY_PRICE_MODELS)}",
        )
    return ticker


@app.post("/api/batch/daily-prices/{ticker}/full", response_model=BatchResponse)
@limiter.limit("5/minute")
def run_daily_full(ticker: str, request: Request, user: dict = Depends(require_admin)):
    """One-time full history load for a daily-prices table (SPY or OEF).

    Fetches everything Yahoo has for the ticker and inserts every row;
    existing dates are skipped, never overwritten. Runs in background.
    """
    ticker = _validate_daily_ticker(ticker)
    require_write_enabled()
    current = _get_daily_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A daily-price load is already running. Check /api/batch/daily-prices/status")

    thread = threading.Thread(target=_run_daily_load_in_background, args=(ticker, "full"), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Full history load started for {ticker}. Check /api/batch/daily-prices/status for progress.",
    )


@app.post("/api/batch/daily-prices/{ticker}/incremental", response_model=BatchResponse)
@limiter.limit("10/minute")
def run_daily_incremental(ticker: str, request: Request, user: dict = Depends(require_admin)):
    """Append missing days for a daily-prices table (SPY or OEF).

    Looks at MAX(price_date) already on file and fetches only the days
    after it, through today -- e.g. miss 6 days, running this loads
    exactly those 6. Append-only: never updates an existing row. Runs
    in background.
    """
    ticker = _validate_daily_ticker(ticker)
    require_write_enabled()
    current = _get_daily_status()
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="A daily-price load is already running. Check /api/batch/daily-prices/status")

    thread = threading.Thread(target=_run_daily_load_in_background, args=(ticker, "incremental"), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Missing-days load started for {ticker}. Check /api/batch/daily-prices/status for progress.",
    )


@app.get("/api/batch/daily-prices/status")
def get_daily_status():
    """Get the status of the last daily-price load (SPY/OEF)."""
    return _get_daily_status()


@app.get("/api/daily-prices/stats")
def get_daily_price_stats_all(db: Session = Depends(get_db)):
    """Row count + date range on file for every daily-prices table."""
    from app.loader import get_daily_price_stats
    return {
        ticker: get_daily_price_stats(db, model, ticker)
        for ticker, model in DAILY_PRICE_MODELS.items()
    }


# ===========================================
# UPDATE ALL — the whole routine behind one button
#
# Every step here already existed as its own admin button. What was missing
# was the order, which lived in whoever was clicking. This runs them
# sequentially in one background thread; a step starts only once the previous
# one has finished, and a failure stops the run rather than carrying on.
#
# UPDATE_ALL_STEPS below is the single source of truth: the orchestrator
# iterates it, and admin.html renders its help panel from the same list. The
# documentation cannot drift from what actually runs.
# ===========================================

UPDATE_ALL_RECENT_MONTHS = 12

# One line per table on what actually lives in it. Rendered next to every
# table name in the help panel so the routine reads as a data flow -- source,
# what gets written, and what that table is for -- rather than a list of
# names you have to already know.
TABLE_NOTES = {
    "monthly_prices":
        "One row per ticker per month: high, low, close, adjusted close. The backbone "
        "of every simulation — buys happen at the monthly high.",
    "dividends":
        "Cash dividends per ticker per month. Held as cash in simulations and earning "
        "the money-market rate, never reinvested.",
    "monthly_mm_rates":
        "Federal funds rate by month. Doubles as the risk-free benchmark and the rate "
        "idle dividend cash earns.",
    "annual_mm_rates":
        "The same rate series rolled up to calendar years.",
    "spy_daily_prices":
        "Daily open/high/low/close/volume for SPY back to 1993-01-29. Standalone table, "
        "one ticker.",
    "oef_daily_prices":
        "The same, for OEF back to 2000-10-27.",
    "etf_directory_monthly_history":
        "Monthly closes for all 81 ETF directory tickers, 1996 to last closed month. "
        "Powers the sparklines and position-in-range bars on the directory page.",
    "damodaran_annual_returns":
        "One row per year since 1928: S&P 500, small cap, T-bill, 10-year T-bond, Baa "
        "corporate, real estate, gold. Powers the rolling-returns page.",
    "shiller_market_data":
        "Monthly S&P 500 data since January 1871 including calculated total return. "
        "Powers Monte Carlo, S&P 500 History, the Historical Simulator, both extremes "
        "pages and downturns & recovery.",
    "stack_earn_savings_tiers":
        "Savings rate tiers for the Stack & Earn calculator.",
    "stack_earn_goal_tiers":
        "Goal rate tiers for the Stack & Earn calculator.",
    "tickers":
        "The list of securities everything else keys off. Symbol, name, active flag.",
}

UPDATE_ALL_STEPS = [
    {
        "key": "new-tickers",
        "label": "Load new tickers",
        "endpoint": "/api/batch/full-new",
        "source": "Yahoo Finance",
        "tables": ["monthly_prices", "dividends"],
        "writes": "Insert only",
        "description": (
            "Pulls complete history for any ticker that has no price data yet. "
            "Tickers that already have data are skipped entirely, so this usually "
            "does nothing — it matters on the first run after you add a symbol."
        ),
    },
    {
        "key": "recent-months",
        "label": f"Refresh the last {UPDATE_ALL_RECENT_MONTHS} months",
        "endpoint": "/api/batch/incremental",
        "source": "Yahoo Finance",
        "tables": ["monthly_prices", "dividends"],
        "writes": "Overwrites existing rows",
        "description": (
            f"Re-fetches the last {UPDATE_ALL_RECENT_MONTHS} months for every active "
            "ticker and overwrites what is on file. This is the step that corrects "
            "revised or bad recent data."
        ),
    },
    {
        "key": "current-month",
        "label": "Load the current month, all sources",
        "endpoint": "/api/batch/current-month",
        "source": "Yahoo Finance + FRED",
        "tables": ["monthly_prices", "dividends", "monthly_mm_rates"],
        "writes": "Overwrites the current-month row",
        "description": (
            "The in-progress month is a live candle — it changes every day until the "
            "month closes. This overwrites the current-month row for every ticker, "
            "plus FRED. Safe to re-run any day of the month."
        ),
    },
    {
        "key": "spy-daily",
        "label": "SPY daily prices — missing days",
        "endpoint": "/api/batch/daily-prices/SPY/incremental",
        "source": "Yahoo Finance",
        "tables": ["spy_daily_prices"],
        "writes": "Append only",
        "description": (
            "Looks at the most recent price_date on file and appends only the days "
            "after it, through today. Never rewrites an existing day."
        ),
    },
    {
        "key": "oef-daily",
        "label": "OEF daily prices — missing days",
        "endpoint": "/api/batch/daily-prices/OEF/incremental",
        "source": "Yahoo Finance",
        "tables": ["oef_daily_prices"],
        "writes": "Append only",
        "description": "Identical behaviour to the SPY step, against the OEF table.",
    },
    {
        "key": "etf-history",
        "label": "ETF directory monthly history — missing months",
        "endpoint": "/api/batch/etf-history/incremental",
        "source": "Yahoo Finance",
        "tables": ["etf_directory_monthly_history"],
        "writes": "Append only",
        "description": (
            "Appends closed months for every ETF directory ticker, one security at a "
            "time. Deliberately never writes the current in-progress month."
        ),
    },
    {
        "key": "fred",
        "label": "FRED federal funds rate",
        "endpoint": "/api/batch/fred-incremental",
        "source": "FRED (St. Louis Fed)",
        "tables": ["monthly_mm_rates", "annual_mm_rates"],
        "writes": "Overwrites existing rows",
        "description": "Re-fetches the last 3 months of the federal funds rate series and upserts.",
    },
    {
        "key": "damodaran",
        "label": "Damodaran annual returns",
        "endpoint": "/api/admin/damodaran-returns/sync",
        "source": "Aswath Damodaran / NYU Stern",
        "tables": ["damodaran_annual_returns"],
        "writes": "Overwrites existing rows",
        "description": (
            "Re-reads the NYU Stern table and upserts by year. Existing years are "
            "updated in place; a new year appears each January."
        ),
    },
]

# Sources the routine deliberately does not touch. Surfaced in the help panel
# so the gap is visible rather than assumed -- Shiller in particular is a
# manual spreadsheet load and will silently fall behind.
UPDATE_ALL_EXCLUDED = [
    {
        "label": "Shiller monthly market data",
        "tables": ["shiller_market_data"],
        "source": "Robert Shiller / shillerdata.com",
        "reason": (
            "Manual spreadsheet load. Download ie_data.xls, then run "
            "backend/onetime/load_shiller_data.py. No API exists, and inputdata/ is "
            "gitignored, so this can only be done locally. Powers six pages."
        ),
    },
    {
        "label": "Full 30-year history reload",
        "tables": ["monthly_prices", "dividends"],
        "source": "Yahoo Finance",
        "reason": "Slow and rarely needed. Stays a separate, explicitly confirmed button.",
    },
    {
        "label": "Stack & Earn rates",
        "tables": ["stack_earn_savings_tiers", "stack_earn_goal_tiers"],
        "source": "Entered by hand",
        "reason": "Edited through the Rate Management card, not fetched from anywhere.",
    },
    {
        "label": "Ticker list",
        "tables": ["tickers"],
        "source": "Entered by hand",
        "reason": "Read only. The routine never adds or removes a symbol.",
    },
]

_update_all_lock = threading.Lock()
_update_all_status = {
    "status": "idle",          # idle | running | completed | failed
    "started_at": None,
    "completed_at": None,
    "current_step": None,
    "step_index": 0,
    "total_steps": len(UPDATE_ALL_STEPS),
    "steps": [],
}


def _update_update_all_status(**kwargs):
    with _update_all_lock:
        _update_all_status.update(kwargs)


def _get_update_all_status():
    with _update_all_lock:
        return dict(_update_all_status)


def _batch_summary_or_raise():
    """Sub-jobs report through the shared batch status rather than returning.
    Pull the result off it and turn a failure into an exception the
    orchestrator can stop on."""
    st = _get_batch_status()
    if st.get("status") == "failed":
        raise RuntimeError(str((st.get("summary") or {}).get("error", "step failed")))
    return st.get("summary")


def _active_symbols():
    from app.loader import get_active_tickers
    db = SessionLocal()
    try:
        return get_active_tickers(db)
    finally:
        db.close()


def _step_new_tickers():
    from app.loader import get_tickers_without_data
    db = SessionLocal()
    try:
        symbols = get_tickers_without_data(db)
    finally:
        db.close()
    if not symbols:
        return {"note": "All active tickers already have price data — nothing to load."}
    _run_batch_in_background(symbols, "full")
    return _batch_summary_or_raise()


def _step_recent_months():
    symbols = _active_symbols()
    if not symbols:
        raise RuntimeError("No active tickers found")
    _run_batch_in_background(symbols, "incremental", UPDATE_ALL_RECENT_MONTHS)
    return _batch_summary_or_raise()


def _step_current_month():
    symbols = _active_symbols()
    if not symbols:
        raise RuntimeError("No active tickers found")
    _run_current_month_in_background(symbols)
    return _batch_summary_or_raise()


def _step_daily(ticker: str):
    _run_daily_load_in_background(ticker, "incremental")
    st = _get_daily_status()
    if st.get("status") == "failed":
        raise RuntimeError(str((st.get("summary") or {}).get("error", f"{ticker} daily load failed")))
    return st.get("summary")


def _step_etf_history():
    _run_etf_history_in_background("incremental")
    st = _get_etf_history_status()
    if st.get("status") == "failed":
        raise RuntimeError(str((st.get("summary") or {}).get("error", "ETF history load failed")))
    return st.get("summary")


def _step_fred():
    _run_fred_in_background("incremental", None)
    return _batch_summary_or_raise()


def _step_damodaran():
    db = SessionLocal()
    try:
        return _sync_damodaran_core(db)
    finally:
        db.close()


UPDATE_ALL_RUNNERS = {
    "new-tickers": _step_new_tickers,
    "recent-months": _step_recent_months,
    "current-month": _step_current_month,
    "spy-daily": lambda: _step_daily("SPY"),
    "oef-daily": lambda: _step_daily("OEF"),
    "etf-history": _step_etf_history,
    "fred": _step_fred,
    "damodaran": _step_damodaran,
}


def _run_update_all_in_background():
    """Run every step in UPDATE_ALL_STEPS in order, one at a time."""
    now = lambda: datetime.now(timezone.utc).isoformat()
    results = []

    _update_update_all_status(
        status="running", started_at=now(), completed_at=None,
        current_step=None, step_index=0, steps=[],
    )

    for i, meta in enumerate(UPDATE_ALL_STEPS, start=1):
        key = meta["key"]
        entry = {
            "key": key, "label": meta["label"], "tables": meta["tables"],
            "status": "running", "started_at": now(), "completed_at": None,
            "summary": None, "error": None,
        }
        results.append(entry)
        _update_update_all_status(
            current_step=key, step_index=i, steps=[dict(r) for r in results],
        )

        try:
            entry["summary"] = UPDATE_ALL_RUNNERS[key]()
            entry["status"] = "completed"
            entry["completed_at"] = now()
        except Exception as e:
            logger.error(f"Update All failed at step '{key}': {traceback.format_exc()}")
            entry["status"] = "failed"
            entry["error"] = str(e)
            entry["completed_at"] = now()
            _update_update_all_status(
                status="failed", current_step=key, completed_at=now(),
                steps=[dict(r) for r in results],
            )
            return

        _update_update_all_status(steps=[dict(r) for r in results])

    _update_update_all_status(
        status="completed", current_step=None, completed_at=now(),
        steps=[dict(r) for r in results],
    )
    logger.info(f"Update All completed — {len(UPDATE_ALL_STEPS)} steps")


@app.post("/api/batch/update-all", response_model=BatchResponse)
@limiter.limit("2/minute")
def run_update_all(request: Request, user: dict = Depends(require_admin)):
    """Run the whole data-refresh routine, one step at a time.
    Requires Auth0 token + ENABLE_WRITE_API.
    """
    require_write_enabled()

    if _get_update_all_status()["status"] == "running":
        raise HTTPException(status_code=409, detail="Update All is already running. Check /api/batch/update-all/status")

    # Any individually-started job would have its status clobbered by the
    # steps below, and would race them for the same tables.
    for label, getter in (
        ("A batch job", _get_batch_status),
        ("A daily-price load", _get_daily_status),
        ("An ETF history load", _get_etf_history_status),
    ):
        if getter()["status"] == "running":
            raise HTTPException(status_code=409, detail=f"{label} is already running. Wait for it to finish.")

    thread = threading.Thread(target=_run_update_all_in_background, daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Update All started — {len(UPDATE_ALL_STEPS)} steps. Check /api/batch/update-all/status for progress.",
    )


@app.get("/api/batch/update-all/status")
def get_update_all_status():
    """Progress of the current or most recent Update All run."""
    return _get_update_all_status()


@app.get("/api/batch/update-all/steps")
def get_update_all_steps(user: dict = Depends(require_admin)):
    """What Update All runs, in order, and what it deliberately leaves out.
    Same list the orchestrator iterates, so the help panel cannot go stale.
    """
    return {
        "recent_months": UPDATE_ALL_RECENT_MONTHS,
        "steps": UPDATE_ALL_STEPS,
        "excluded": UPDATE_ALL_EXCLUDED,
        "table_notes": TABLE_NOTES,
    }


# ===========================================
# SECTOR PERFORMANCE (annual returns + dividends from DB)
# ===========================================

@app.get("/api/sector-performance")
@limiter.limit("30/minute")
def get_sector_performance(
    request: Request,
    db: Session = Depends(get_db),
):
    """Compute 20-year annual return & dividend data for all sector ETFs.

    Return = (Dec close[Y] - Dec close[Y-1]) / Dec close[Y-1] * 100
    Dividend = sum of all dividends paid during year Y

    The current in-progress year (no December close yet) is included as a
    partial/YTD figure using the latest available month's close instead of
    December. It's flagged with "partial": true and "as_of_month" so the
    frontend can label it — the value updates automatically as more months
    of data get loaded through the year.
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

        # All monthly closes, keyed by year -> {month: close}
        from collections import defaultdict
        month_rows = (
            db.query(MonthlyPrice.year, MonthlyPrice.month, MonthlyPrice.close)
            .filter(MonthlyPrice.ticker_id == ticker.id)
            .order_by(MonthlyPrice.year, MonthlyPrice.month)
            .all()
        )
        year_months: dict = defaultdict(dict)
        for y, m, c in month_rows:
            if c is not None:
                year_months[y][m] = c

        # December close prices keyed by year (used as prior-year baseline)
        dec_map = {y: months[12] for y, months in year_months.items() if 12 in months}

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
        for y in sorted(year_months.keys()):
            if y - 1 not in dec_map:
                continue
            prev = dec_map[y - 1]
            months = year_months[y]

            if 12 in months:
                curr = months[12]
                partial = False
                as_of_month = 12
            else:
                as_of_month = max(months.keys())
                curr = months[as_of_month]
                partial = True

            yearly[str(y)] = {
                "return": round(((curr - prev) / prev) * 100, 2),
                "dividend": round(div_map.get(y, 0), 2),
                "prev_close": round(prev, 2),
                "close": round(curr, 2),
                "partial": partial,
                "as_of_month": as_of_month,
            }

        results[sym] = {"name": ticker.name, "data": yearly}

    return results


# ===========================================
# SECTOR MONTHLY (all monthly close prices for sector ETFs)
# ===========================================

@app.get("/api/sector-monthly")
@limiter.limit("30/minute")
def get_sector_monthly(
    request: Request,
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
# SAVED SIMULATIONS
# ===========================================

MAX_SAVED_SIMULATIONS = 3


class SaveSimulationRequest(BaseModel):
    tickers_json: str
    start_year: int
    end_year: int
    monthly_amount: float
    annual_growth: float = 0
    total_invested: float
    equity_value: float
    dividends_earned: float
    cash_accrual: float
    mm_earned: float
    portfolio_balance: float
    total_return_pct: float
    mmf_value: float

    @field_validator("tickers_json")
    @classmethod
    def validate_tickers_json(cls, v):
        import json
        try:
            parsed = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("tickers_json must be valid JSON")
        if not isinstance(parsed, dict) or not parsed:
            raise ValueError("tickers_json must be a non-empty object")
        return v

    @field_validator("start_year", "end_year")
    @classmethod
    def validate_years(cls, v):
        if v < 1900 or v > 2100:
            raise ValueError("Year must be between 1900 and 2100")
        return v

    @field_validator("monthly_amount")
    @classmethod
    def validate_monthly_amount(cls, v):
        if v <= 0:
            raise ValueError("Monthly amount must be positive")
        return v


class SavedSimulationResponse(BaseModel):
    id: int
    tickers_json: str
    start_year: int
    end_year: int
    monthly_amount: float
    annual_growth: float
    total_invested: float
    equity_value: float
    dividends_earned: float
    cash_accrual: float
    mm_earned: float
    portfolio_balance: float
    total_return_pct: float
    mmf_value: float
    created_at: str

    class Config:
        from_attributes = True


def _sim_to_response(sim: SavedSimulation) -> SavedSimulationResponse:
    """Convert a SavedSimulation ORM object to a response dict."""
    return SavedSimulationResponse(
        id=sim.id,
        tickers_json=sim.tickers_json,
        start_year=sim.start_year,
        end_year=sim.end_year,
        monthly_amount=sim.monthly_amount,
        annual_growth=sim.annual_growth,
        total_invested=sim.total_invested,
        equity_value=sim.equity_value,
        dividends_earned=sim.dividends_earned,
        cash_accrual=sim.cash_accrual,
        mm_earned=sim.mm_earned,
        portfolio_balance=sim.portfolio_balance,
        total_return_pct=sim.total_return_pct,
        mmf_value=sim.mmf_value,
        created_at=sim.created_at.isoformat() if sim.created_at else "",
    )


@app.post("/api/simulations", response_model=SavedSimulationResponse, status_code=201)
@limiter.limit("10/minute")
def save_simulation(
    request: Request,
    data: SaveSimulationRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a portfolio simulation result. Max 3 per user."""
    auth0_user_id = user.get("sub", "")
    email = (user.get("email") or "").lower().strip()
    if not auth0_user_id:
        raise HTTPException(status_code=400, detail="User identity not available")

    count = db.query(SavedSimulation).filter(
        SavedSimulation.auth0_user_id == auth0_user_id
    ).count()
    if count >= MAX_SAVED_SIMULATIONS:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum {MAX_SAVED_SIMULATIONS} saved simulations. Delete one before saving another.",
        )

    sim = SavedSimulation(
        auth0_user_id=auth0_user_id,
        email=email,
        tickers_json=data.tickers_json,
        start_year=data.start_year,
        end_year=data.end_year,
        monthly_amount=data.monthly_amount,
        annual_growth=data.annual_growth,
        total_invested=data.total_invested,
        equity_value=data.equity_value,
        dividends_earned=data.dividends_earned,
        cash_accrual=data.cash_accrual,
        mm_earned=data.mm_earned,
        portfolio_balance=data.portfolio_balance,
        total_return_pct=data.total_return_pct,
        mmf_value=data.mmf_value,
    )
    db.add(sim)
    db.commit()
    db.refresh(sim)
    logger.info(f"Saved simulation {sim.id} for {email}")
    return _sim_to_response(sim)


@app.get("/api/simulations", response_model=list[SavedSimulationResponse])
def list_simulations(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all saved simulations for the current user, ordered by created_at."""
    auth0_user_id = user.get("sub", "")
    sims = (
        db.query(SavedSimulation)
        .filter(SavedSimulation.auth0_user_id == auth0_user_id)
        .order_by(SavedSimulation.created_at)
        .all()
    )
    return [_sim_to_response(s) for s in sims]


@app.delete("/api/simulations/{sim_id}", status_code=200)
def delete_simulation(
    sim_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a saved simulation by its DB id. User can only delete their own."""
    auth0_user_id = user.get("sub", "")
    sim = db.query(SavedSimulation).filter(
        SavedSimulation.id == sim_id,
        SavedSimulation.auth0_user_id == auth0_user_id,
    ).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    db.delete(sim)
    db.commit()
    logger.info(f"Deleted simulation {sim_id} for {user.get('email', 'unknown')}")
    return {"message": f"Simulation {sim_id} deleted"}


# ===========================================
# PAGE VIEW TRACKING (self-hosted, zero cost)
# ===========================================

def _record_pageview(page: str, referrer: Optional[str], ip: Optional[str], user_agent: str):
    try:
        db = SessionLocal()
        try:
            log = ApiRequestLog(
                request_id="pv",
                user_email=None,
                method="PAGEVIEW",
                path=page,
                status_code=200,
                response_time_ms=0,
                ip_address=ip,
                user_agent=user_agent,
                error_detail=referrer,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


@app.post("/api/track/pageview", status_code=204)
@limiter.limit("30/minute")
async def track_pageview(request: Request):
    """Record a page view. Fire-and-forget, never fails the client.

    The body is parsed by hand rather than through a Pydantic model: browsers send
    navigator.sendBeacon string payloads as text/plain, which FastAPI will not hand
    to a body model, so a declared model rejects every beacon with a 422.
    """
    try:
        raw = await request.body()
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    page = payload.get("page")
    page = str(page)[:500] if page else "/"
    referrer = payload.get("referrer")
    referrer = str(referrer)[:500] if referrer else None

    await run_in_threadpool(
        _record_pageview,
        page,
        referrer,
        request.client.host if request.client else None,
        (request.headers.get("user-agent") or "")[:500],
    )
    return


# ===========================================
# SP500 HISTORY (Shiller annual returns + wealth curve)
# ===========================================

@app.get("/api/sp500-annual-returns")
@limiter.limit("30/minute")
def get_sp500_annual_returns(request: Request, db: Session = Depends(get_db)):
    """Compound monthly NominalTotalReturn values from shiller_market_data into annual returns.

    Returns:
      annual  — dict {year: annual_return_%} for complete calendar years
      wealth  — monthly wealth curve [{d: "YYYY-MM", v: dollar_value}, ...] starting at $100
      stats   — summary statistics (median, best/worst year, % positive, etc.)
    """
    from collections import defaultdict

    try:
        rows = db.execute(
            text(
                'SELECT "DataDate", "Year", "Month", "NominalTotalReturn" '
                "FROM shiller_market_data "
                'WHERE "NominalTotalReturn" IS NOT NULL '
                'ORDER BY "DataDate"'
            )
        ).fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="shiller_market_data unavailable — run load_shiller_data.py first.",
        ) from exc

    if not rows:
        return {"annual": {}, "wealth": [], "stats": {}}

    # Group monthly returns by year
    monthly_by_year: dict = defaultdict(list)
    monthly_all: list = []
    for row in rows:
        yr, mo, ret = int(row[1]), int(row[2]), float(row[3])
        monthly_by_year[yr].append(ret)
        monthly_all.append((yr, mo, ret))

    # Annual returns: compound all 12 monthly returns (skip partial years)
    annual: dict = {}
    for yr in sorted(monthly_by_year.keys()):
        months = monthly_by_year[yr]
        if len(months) < 12:
            continue
        compound = 1.0
        for r in months:
            compound *= (1.0 + r)
        annual[yr] = round((compound - 1.0) * 100, 2)

    # Monthly wealth curve starting at $100
    wealth = 100.0
    wealth_curve = []
    for yr, mo, r in monthly_all:
        wealth *= (1.0 + r)
        wealth_curve.append({"d": f"{yr}-{mo:02d}", "v": round(wealth, 2)})

    # Summary stats
    returns_list = list(annual.values())
    stats: dict = {}
    if returns_list:
        n = len(returns_list)
        sorted_ret = sorted(returns_list)
        positive_count = sum(1 for r in returns_list if r > 0)
        mid = n // 2
        median_ret = sorted_ret[mid] if n % 2 == 1 else (sorted_ret[mid - 1] + sorted_ret[mid]) / 2
        mean_ret = sum(returns_list) / n
        best_yr = max(annual, key=annual.get)
        worst_yr = min(annual, key=annual.get)

        decade_map: dict = defaultdict(list)
        for yr, ret in annual.items():
            decade_map[(yr // 10) * 10].append(ret)
        decade_avgs = {d: sum(v) / len(v) for d, v in decade_map.items()}
        best_decade = max(decade_avgs, key=decade_avgs.get)
        worst_decade = min(decade_avgs, key=decade_avgs.get)

        stats = {
            "total_years": n,
            "pct_positive": round(positive_count / n * 100, 1),
            "median": round(median_ret, 1),
            "mean": round(mean_ret, 1),
            "best_year": best_yr,
            "best_return": annual[best_yr],
            "worst_year": worst_yr,
            "worst_return": annual[worst_yr],
            "best_decade": best_decade,
            "best_decade_avg": round(decade_avgs[best_decade], 1),
            "worst_decade": worst_decade,
            "worst_decade_avg": round(decade_avgs[worst_decade], 1),
            "final_wealth": round(wealth, 2),
        }

    return {
        "annual": {str(k): v for k, v in annual.items()},
        "wealth": wealth_curve,
        "stats": stats,
    }


# ===========================================
# SHILLER MONTHLY RETURNS (raw, for Monte Carlo)
# ===========================================

@app.get("/api/shiller-monthly-returns")
@limiter.limit("60/minute")
def get_shiller_monthly_returns(request: Request, db: Session = Depends(get_db)):
    """Return all monthly nominal total returns as a flat array of floats (chronological).
    Used by the client-side Monte Carlo block-bootstrap simulation.
    """
    try:
        rows = db.execute(
            text(
                'SELECT "NominalTotalReturn" '
                "FROM shiller_market_data "
                'WHERE "NominalTotalReturn" IS NOT NULL '
                'ORDER BY "DataDate"'
            )
        ).fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="shiller_market_data unavailable — run load_shiller_data.py first.",
        ) from exc
    return [float(r[0]) for r in rows]


# ===========================================
# EXTREME MONTHS (best / worst single months)
# ===========================================

_MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

@app.get("/api/sp500-extreme-years")
@limiter.limit("60/minute")
def get_sp500_extreme_years(
    request: Request,
    n: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
):
    """Return the N best and N worst full calendar years by compounded NominalTotalReturn."""
    from collections import defaultdict

    try:
        rows = db.execute(
            text(
                'SELECT "Year", "Month", "NominalTotalReturn" '
                "FROM shiller_market_data "
                'WHERE "NominalTotalReturn" IS NOT NULL '
                'ORDER BY "Year", "Month"'
            )
        ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="shiller_market_data unavailable.") from exc

    monthly_by_year: dict = defaultdict(list)
    for row in rows:
        monthly_by_year[int(row[0])].append(float(row[2]))

    annual = {}
    for yr in sorted(monthly_by_year.keys()):
        months = monthly_by_year[yr]
        if len(months) < 12:
            continue
        compound = 1.0
        for r in months:
            compound *= (1.0 + r)
        annual[yr] = compound - 1.0

    sorted_years = sorted(annual.items(), key=lambda x: x[1])
    total = len(sorted_years)
    count = min(n, total)

    def make(yr, ret, rank):
        return {
            "rank": rank,
            "date": str(yr),
            "return_pct": round(ret * 100, 2),
            "end_value": round(10000 * (1 + ret)),
        }

    worst = [make(sorted_years[i][0], sorted_years[i][1], i + 1) for i in range(count)]
    best  = [make(sorted_years[total - 1 - i][0], sorted_years[total - 1 - i][1], i + 1) for i in range(count)]
    return {"worst": worst, "best": best}


# ===========================================
# BAD 5-YEAR STREAKS + RECOVERY
# ===========================================

@app.get("/api/sp500-bad-streaks")
@limiter.limit("60/minute")
def get_sp500_bad_streaks(
    request: Request,
    n: int = Query(10, ge=3, le=20),
    db: Session = Depends(get_db),
):
    """Return the N worst non-overlapping 5-year rolling windows plus the 2 recovery years after each."""
    from collections import defaultdict

    try:
        rows = db.execute(
            text(
                'SELECT "Year", "Month", "NominalTotalReturn" '
                "FROM shiller_market_data "
                'WHERE "NominalTotalReturn" IS NOT NULL '
                'ORDER BY "Year", "Month"'
            )
        ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="shiller_market_data unavailable.") from exc

    monthly_by_year: dict = defaultdict(list)
    for row in rows:
        monthly_by_year[int(row[0])].append(float(row[2]))

    annual: dict = {}
    for yr in sorted(monthly_by_year.keys()):
        months = monthly_by_year[yr]
        if len(months) < 12:
            continue
        compound = 1.0
        for r in months:
            compound *= (1.0 + r)
        annual[yr] = compound - 1.0

    years = sorted(annual.keys())
    period = 5

    # Build all rolling 5-year windows (require consecutive calendar years)
    windows = []
    for i in range(len(years) - period + 1):
        window_years = years[i : i + period]
        if window_years[-1] - window_years[0] != period - 1:
            continue
        compound = 1.0
        for yr in window_years:
            compound *= (1.0 + annual[yr])
        windows.append((window_years[0], window_years[-1], compound - 1.0, window_years))

    # Sort worst first
    windows.sort(key=lambda x: x[2])

    # Greedy pick non-overlapping windows
    picked = []
    used = set()
    for start, end, ret, yrs in windows:
        if any(y in used for y in yrs):
            continue
        picked.append((start, end, ret, yrs))
        used.update(yrs)
        if len(picked) >= n:
            break

    result = []
    for rank, (start, end, ret, yrs) in enumerate(picked, 1):
        yr_detail = [{"year": y, "return_pct": round(annual[y] * 100, 2)} for y in yrs]

        r1_yr = end + 1
        r2_yr = end + 2
        rec1 = (
            {"year": r1_yr, "return_pct": round(annual[r1_yr] * 100, 2), "available": True}
            if r1_yr in annual
            else {"year": r1_yr, "return_pct": None, "available": False}
        )
        rec2 = (
            {"year": r2_yr, "return_pct": round(annual[r2_yr] * 100, 2), "available": True}
            if r2_yr in annual
            else {"year": r2_yr, "return_pct": None, "available": False}
        )

        if rec1["available"] and rec2["available"]:
            rec_combined = round(
                ((1 + annual[r1_yr]) * (1 + annual[r2_yr]) - 1) * 100, 2
            )
        elif rec1["available"]:
            rec_combined = rec1["return_pct"]
        else:
            rec_combined = None

        result.append({
            "rank": rank,
            "start_year": start,
            "end_year": end,
            "return_pct": round(ret * 100, 2),
            "end_value": round(10000 * (1 + ret)),
            "years_detail": yr_detail,
            "recovery_yr1": rec1,
            "recovery_yr2": rec2,
            "recovery_combined_pct": rec_combined,
        })

    return {"periods": result}


@app.get("/api/sp500-extreme-months")
@limiter.limit("60/minute")
def get_sp500_extreme_months(
    request: Request,
    n: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
):
    """Return the N best and N worst single months by NominalTotalReturn."""
    try:
        rows = db.execute(
            text(
                'SELECT "Year", "Month", "NominalTotalReturn" '
                "FROM shiller_market_data "
                'WHERE "NominalTotalReturn" IS NOT NULL '
                'ORDER BY "NominalTotalReturn"'
            )
        ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="shiller_market_data unavailable.") from exc

    def make(r, rank):
        ret = float(r[2])
        mo = int(r[1])
        label = f"{_MONTH_ABBR[mo - 1]} {int(r[0])}"
        return {
            "rank": rank,
            "date": label,
            "return_pct": round(ret * 100, 2),
            "end_value": round(10000 * (1 + ret)),
        }

    total = len(rows)
    count = min(n, total)
    worst = [make(rows[i], i + 1) for i in range(count)]
    best  = [make(rows[total - 1 - i], i + 1) for i in range(count)]
    return {"worst": worst, "best": best}


# ===========================================
# SP500 DCA SIMULATOR (Shiller monthly returns)
# ===========================================

@app.get("/api/sp500-simulate")
@limiter.limit("30/minute")
def get_sp500_simulate(
    request: Request,
    start: int = Query(..., ge=1872, le=2023, description="Start year (inclusive)"),
    end: int = Query(..., ge=1873, le=2024, description="End year (inclusive)"),
    initial: float = Query(10000.0, ge=0, le=10_000_000),
    monthly: float = Query(0.0, ge=0, le=1_000_000),
    db: Session = Depends(get_db),
):
    """DCA simulation using Shiller monthly NominalTotalReturn data.

    Each month: balance = (balance + monthly_contribution) * (1 + NominalTotalReturn)
    Returns year-by-year summary and final stats.
    """
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    try:
        rows = db.execute(
            text(
                'SELECT "Year", "Month", "NominalTotalReturn" '
                "FROM shiller_market_data "
                'WHERE "NominalTotalReturn" IS NOT NULL '
                'AND "Year" >= :yr_start AND "Year" <= :yr_end '
                'ORDER BY "Year", "Month"'
            ),
            {"yr_start": start, "yr_end": end},
        ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="shiller_market_data unavailable.") from exc

    if not rows:
        raise HTTPException(status_code=404, detail=f"No data found for {start}–{end}.")

    # Group months by year; skip any year with < 12 months
    from collections import defaultdict
    months_by_year: dict = defaultdict(list)
    for row in rows:
        yr, mo, ret = int(row[0]), int(row[1]), float(row[2])
        months_by_year[yr].append((mo, ret))

    complete_years = sorted(
        yr for yr, months in months_by_year.items() if len(months) == 12
    )
    if not complete_years:
        raise HTTPException(status_code=404, detail="No complete calendar years in that range.")

    balance = float(initial)
    total_contributed = float(initial)
    yearly = []

    for yr in complete_years:
        start_balance = balance
        annual_factor = 1.0
        for _mo, ret in sorted(months_by_year[yr]):
            balance = (balance + monthly) * (1.0 + ret)
            total_contributed += monthly
            annual_factor *= (1.0 + ret)
        annual_ret_pct = round((annual_factor - 1.0) * 100, 2)
        yearly.append({
            "year": yr,
            "start_balance": round(start_balance, 2),
            "end_balance": round(balance, 2),
            "annual_return_pct": annual_ret_pct,
            "total_contributed": round(total_contributed, 2),
        })

    gain = balance - total_contributed
    gain_pct = (gain / total_contributed * 100) if total_contributed > 0 else 0

    return {
        "years": yearly,
        "stats": {
            "start_year": complete_years[0],
            "end_year": complete_years[-1],
            "num_years": len(complete_years),
            "initial": round(initial, 2),
            "monthly_contribution": round(monthly, 2),
            "total_contributed": round(total_contributed, 2),
            "final_balance": round(balance, 2),
            "total_gain": round(gain, 2),
            "total_gain_pct": round(gain_pct, 1),
        },
    }


# ===========================================
# STACK & EARN — TIERED SAVINGS CALCULATOR
# ===========================================

def _serialize_tier(r):
    return {
        "tier_number": r.tier_number,
        "tier_label": r.tier_label,
        "min_amount": r.min_amount,
        "max_amount": r.max_amount,
        "annual_rate": r.annual_rate,
        "display_rate": getattr(r, "display_rate", 1) if getattr(r, "display_rate", None) is not None else 1,
        "display_upto": getattr(r, "display_upto", 0) if getattr(r, "display_upto", None) is not None else 0,
        "product_type": getattr(r, "product_type", None) or "PurposeSaving",
    }


@app.get("/api/stack-earn/savings-tiers")
@limiter.limit("60/minute")
def get_stack_earn_savings_tiers(request: Request, db: Session = Depends(get_db)):
    """Return tiered interest rates for the savings calculator."""
    rows = db.query(StackEarnSavingsTier).order_by(StackEarnSavingsTier.tier_number).all()
    return [_serialize_tier(r) for r in rows]


@app.get("/api/stack-earn/goal-tiers")
@limiter.limit("60/minute")
def get_stack_earn_goal_tiers(request: Request, db: Session = Depends(get_db)):
    """Return tiered interest rates for the goal calculator."""
    rows = db.query(StackEarnGoalTier).order_by(StackEarnGoalTier.tier_number).all()
    return [_serialize_tier(r) for r in rows]


# ---- Admin CRUD for Stack & Earn tiers ----

class TierUpsert(BaseModel):
    tier_label: str
    min_amount: float
    max_amount: Optional[float] = None
    annual_rate: float
    display_rate: Optional[int] = 1
    display_upto: Optional[int] = 0
    product_type: Optional[str] = "PurposeSaving"


@app.get("/api/admin/stack-earn/savings-tiers")
@limiter.limit("30/minute")
def admin_get_savings_tiers(
    request: Request,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(StackEarnSavingsTier).order_by(StackEarnSavingsTier.tier_number).all()
    return [_serialize_tier(r) for r in rows]


@app.put("/api/admin/stack-earn/savings-tiers/{tier_number}")
@limiter.limit("10/minute")
def admin_update_savings_tier(
    request: Request,
    tier_number: int,
    body: TierUpsert,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_write_enabled()
    row = db.query(StackEarnSavingsTier).filter(StackEarnSavingsTier.tier_number == tier_number).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tier not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(row, field, val)
    db.commit()
    db.refresh(row)
    return _serialize_tier(row)


@app.post("/api/admin/stack-earn/savings-tiers", status_code=201)
@limiter.limit("10/minute")
def admin_create_savings_tier(
    request: Request,
    body: TierUpsert,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_write_enabled()
    # auto-assign next tier_number
    max_num = db.query(StackEarnSavingsTier).count()
    row = StackEarnSavingsTier(tier_number=max_num + 1, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_tier(row)


@app.get("/api/admin/stack-earn/goal-tiers")
@limiter.limit("30/minute")
def admin_get_goal_tiers(
    request: Request,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(StackEarnGoalTier).order_by(StackEarnGoalTier.tier_number).all()
    return [_serialize_tier(r) for r in rows]


@app.put("/api/admin/stack-earn/goal-tiers/{tier_number}")
@limiter.limit("10/minute")
def admin_update_goal_tier(
    request: Request,
    tier_number: int,
    body: TierUpsert,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_write_enabled()
    row = db.query(StackEarnGoalTier).filter(StackEarnGoalTier.tier_number == tier_number).first()
    if not row:
        raise HTTPException(status_code=404, detail="Tier not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(row, field, val)
    db.commit()
    db.refresh(row)
    return _serialize_tier(row)


@app.post("/api/admin/stack-earn/goal-tiers", status_code=201)
@limiter.limit("10/minute")
def admin_create_goal_tier(
    request: Request,
    body: TierUpsert,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_write_enabled()
    max_num = db.query(StackEarnGoalTier).count()
    row = StackEarnGoalTier(tier_number=max_num + 1, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_tier(row)


# ===========================================
# DAMODARAN ANNUAL RETURNS (admin-managed reference data)
# ===========================================

_DAMODARAN_COLS = (
    '"Year", "SP500Return", "SmallCapReturn", "TBill3Month", "TBond10Year", '
    '"BaaCorporateBond", "RealEstate", "Gold", "Source"'
)


def _serialize_damodaran_row(r):
    return {
        "year": r[0],
        "sp500_return": float(r[1]) if r[1] is not None else None,
        "small_cap_return": float(r[2]) if r[2] is not None else None,
        "tbill_3month": float(r[3]) if r[3] is not None else None,
        "tbond_10year": float(r[4]) if r[4] is not None else None,
        "baa_corporate_bond": float(r[5]) if r[5] is not None else None,
        "real_estate": float(r[6]) if r[6] is not None else None,
        "gold": float(r[7]) if r[7] is not None else None,
        "source": r[8],
    }


@app.get("/api/admin/damodaran-returns")
@limiter.limit("30/minute")
def admin_get_damodaran_returns(
    request: Request,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all Damodaran annual return rows, newest year first."""
    try:
        rows = db.execute(
            text(f"SELECT {_DAMODARAN_COLS} FROM damodaran_annual_returns ORDER BY \"Year\" DESC")
        ).fetchall()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="damodaran_annual_returns unavailable.") from exc
    return [_serialize_damodaran_row(r) for r in rows]


class DamodaranRowUpdate(BaseModel):
    sp500_return: float
    small_cap_return: Optional[float] = None
    tbill_3month: Optional[float] = None
    tbond_10year: Optional[float] = None
    baa_corporate_bond: Optional[float] = None
    real_estate: Optional[float] = None
    gold: Optional[float] = None


@app.put("/api/admin/damodaran-returns/{year}")
@limiter.limit("10/minute")
def admin_update_damodaran_return(
    request: Request,
    year: int,
    body: DamodaranRowUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    require_write_enabled()
    result = db.execute(
        text(
            'UPDATE damodaran_annual_returns SET '
            '"SP500Return"=:sp, "SmallCapReturn"=:sc, "TBill3Month"=:tb, "TBond10Year"=:tn, '
            '"BaaCorporateBond"=:baa, "RealEstate"=:re, "Gold"=:gold '
            'WHERE "Year"=:yr'
        ),
        {
            "sp": body.sp500_return, "sc": body.small_cap_return, "tb": body.tbill_3month,
            "tn": body.tbond_10year, "baa": body.baa_corporate_bond, "re": body.real_estate,
            "gold": body.gold, "yr": year,
        },
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Year {year} not found")
    db.commit()
    row = db.execute(
        text(f"SELECT {_DAMODARAN_COLS} FROM damodaran_annual_returns WHERE \"Year\"=:yr"),
        {"yr": year},
    ).fetchone()
    return _serialize_damodaran_row(row)


def _sync_damodaran_core(db: Session) -> dict:
    """Fetch Damodaran's table and upsert by year. Shared by the standalone
    endpoint and by Update All, so both stay identical.

    Raises DamodaranFetchError if the source cannot be read; the caller
    decides whether that is a 502 or a failed step.
    """
    from app.damodaran_fetcher import fetch_damodaran_returns, SOURCE_LABEL, DAMODARAN_URL

    records = fetch_damodaran_returns()

    inserted = 0
    updated = 0
    for rec in records:
        existing = db.execute(
            text('SELECT "Year" FROM damodaran_annual_returns WHERE "Year"=:yr'),
            {"yr": rec["Year"]},
        ).fetchone()
        params = {
            "yr": rec["Year"], "sp": rec["SP500Return"], "sc": rec["SmallCapReturn"],
            "tb": rec["TBill3Month"], "tn": rec["TBond10Year"], "baa": rec["BaaCorporateBond"],
            "re": rec["RealEstate"], "gold": rec["Gold"],
        }
        if existing:
            db.execute(
                text(
                    'UPDATE damodaran_annual_returns SET '
                    '"SP500Return"=:sp, "SmallCapReturn"=:sc, "TBill3Month"=:tb, "TBond10Year"=:tn, '
                    '"BaaCorporateBond"=:baa, "RealEstate"=:re, "Gold"=:gold '
                    'WHERE "Year"=:yr'
                ),
                params,
            )
            updated += 1
        else:
            db.execute(
                text(
                    'INSERT INTO damodaran_annual_returns '
                    '("Year", "SP500Return", "SmallCapReturn", "TBill3Month", "TBond10Year", '
                    '"BaaCorporateBond", "RealEstate", "Gold", "Source", "SourceUrl", "CreatedAt") '
                    'VALUES (:yr, :sp, :sc, :tb, :tn, :baa, :re, :gold, :src, :url, :created)'
                ),
                {**params, "src": SOURCE_LABEL, "url": DAMODARAN_URL,
                 "created": datetime.now(timezone.utc)},
            )
            inserted += 1
    db.commit()

    total = db.execute(text("SELECT COUNT(*) FROM damodaran_annual_returns")).scalar()
    latest_year = db.execute(text('SELECT MAX("Year") FROM damodaran_annual_returns')).scalar()
    return {"inserted": inserted, "updated": updated, "total": total, "latest_year": latest_year}


@app.post("/api/admin/damodaran-returns/sync")
@limiter.limit("5/minute")
def admin_sync_damodaran_returns(
    request: Request,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Fetch the latest table from Damodaran's page (NYU Stern) and upsert by year.

    Existing years are updated in place; new years (e.g. once Damodaran
    publishes the next calendar year, each January) are inserted.
    """
    require_write_enabled()
    from app.damodaran_fetcher import DamodaranFetchError

    try:
        return _sync_damodaran_core(db)
    except DamodaranFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/damodaran-forward-returns")
@limiter.limit("30/minute")
def get_damodaran_forward_returns(request: Request, db: Session = Depends(get_db)):
    """Rolling forward-looking N-year returns (1/3/5/7/10Y) for every year in
    damodaran_annual_returns, computed from S&P 500 annual total returns.

    N-year return for year Y = geometric mean (CAGR) of Y's return and the
    next (N-1) years: [(1+r_Y) * (1+r_Y+1) * ... * (1+r_Y+N-1)]^(1/N) - 1.
    Null when the dataset doesn't have enough future years to fill the window
    (e.g. near the most recent year on record).
    """
    rows = db.execute(
        text('SELECT "Year", "SP500Return" FROM damodaran_annual_returns ORDER BY "Year" ASC')
    ).fetchall()

    if not rows:
        return {"years": [], "source": "Damodaran (NYU Stern)"}

    returns = [float(r[1]) for r in rows]
    years = [int(r[0]) for r in rows]
    n = len(returns)
    windows = (1, 3, 5, 7, 10)

    result = []
    for i in range(n):
        entry = {"year": years[i], "r1": None, "r3": None, "r5": None, "r7": None, "r10": None}
        for w in windows:
            if i + w <= n:
                product = 1.0
                for k in range(w):
                    product *= (1 + returns[i + k])
                cagr = product ** (1.0 / w) - 1
                entry[f"r{w}"] = round(cagr * 100, 2)
        result.append(entry)

    return {"years": result, "source": "Damodaran (NYU Stern)"}


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

    @app.get("/sp500-history.html")
    def serve_sp500_history():
        return FileResponse(str(_frontend_dir / "sp500-history.html"))

    @app.get("/sp500-simulate.html")
    def serve_sp500_simulate():
        return FileResponse(str(_frontend_dir / "sp500-simulate.html"))

    @app.get("/saved-simulations.html")
    def serve_saved_simulations():
        return FileResponse(str(_frontend_dir / "saved-simulations.html"))

    @app.get("/stack-earn.html")
    def serve_stack_earn():
        return FileResponse(str(_frontend_dir / "stack-earn.html"))

    @app.get("/montecarlo.html")
    def serve_montecarlo():
        return FileResponse(str(_frontend_dir / "montecarlo.html"))

    @app.get("/extreme-months.html")
    def serve_extreme_months():
        return FileResponse(str(_frontend_dir / "extreme-months.html"))

    @app.get("/robots.txt")
    def serve_robots():
        return FileResponse(str(_frontend_dir / "robots.txt"), media_type="text/plain")

    @app.get("/sitemap.xml")
    def serve_sitemap():
        return FileResponse(str(_frontend_dir / "sitemap.xml"), media_type="application/xml")

    app.mount("/", StaticFiles(directory=str(_frontend_dir)), name="frontend")

"""FastAPI REST API for portfolio simulator.

Endpoints:
  Health:
    GET    /api/health                   - Health check

  Tickers:
    GET    /api/tickers                  - List all tickers
    GET    /api/tickers/active           - List active tickers only
    POST   /api/tickers                  - Add a new ticker
    PUT    /api/tickers/{symbol}         - Update ticker (name, active)
    DELETE /api/tickers/{symbol}         - Delete ticker and all its data

  Prices:
    GET    /api/prices/{symbol}          - Get monthly prices for a ticker
    GET    /api/prices/{symbol}/latest   - Get latest month's price

  Dividends:
    GET    /api/dividends/{symbol}       - Get dividends for a ticker

  Simulation Data:
    GET    /api/simulation-data/{symbol} - Get combined prices + dividends for simulation

  Batch:
    POST   /api/batch/full               - Trigger full history load (async)
    POST   /api/batch/incremental        - Trigger incremental load (async)
    GET    /api/batch/status             - Get last batch run info
"""
import os
import re
import uuid
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

from app.database import SessionLocal, init_db, engine
from app.models import Ticker, MonthlyPrice, Dividend
from app.config import MAX_TICKERS, ENABLE_WRITE_API

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Load .env
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


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


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request and attach a request ID."""
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    logger.info(f"[{request_id}] {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        logger.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code}")
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        logger.error(f"[{request_id}] Unhandled error in middleware: {e}")
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
# TICKER ENDPOINTS
# ===========================================

@app.get("/api/tickers", response_model=list[TickerResponse])
def list_tickers(db: Session = Depends(get_db)):
    """List all tickers."""
    return db.query(Ticker).order_by(Ticker.symbol).all()


@app.get("/api/tickers/active", response_model=list[TickerResponse])
def list_active_tickers(db: Session = Depends(get_db)):
    """List only active tickers."""
    return db.query(Ticker).filter(Ticker.active == True).order_by(Ticker.symbol).all()


@app.post("/api/tickers", response_model=TickerResponse, status_code=201)
def create_ticker(data: TickerCreate, db: Session = Depends(get_db)):
    """Add a new ticker."""
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
def update_ticker(symbol: str, data: TickerUpdate, db: Session = Depends(get_db)):
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
def delete_ticker(symbol: str, db: Session = Depends(get_db)):
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

def _run_batch_in_background(symbols: list[str], mode: str):
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

        fetch_results = fetch_all_tickers(symbols, mode=mode, delay_seconds=1.0)

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


@app.post("/api/batch/full", response_model=BatchResponse)
def run_batch_full(data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger a full history data load (runs in background)."""
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


@app.post("/api/batch/incremental", response_model=BatchResponse)
def run_batch_incremental(data: BatchRequest = BatchRequest(), db: Session = Depends(get_db)):
    """Trigger an incremental data load (runs in background)."""
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

    thread = threading.Thread(target=_run_batch_in_background, args=(symbols, "incremental"), daemon=True)
    thread.start()

    return BatchResponse(
        status="started",
        message=f"Incremental load started for {len(symbols)} tickers. Check /api/batch/status for progress.",
    )


@app.get("/api/batch/status")
def get_batch_status():
    """Get the status of the last batch run."""
    return _get_batch_status()

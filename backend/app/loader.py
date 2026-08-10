"""Database loader - saves fetched data into the database.

Supports two modes:
  - Full load: inserts all history (skips existing records)
  - Incremental: upserts last 2 months (updates if exists, inserts if new)
"""
import re
import logging
import pathlib
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import pandas as pd

from app.models import Ticker, MonthlyPrice, Dividend, DailyQuote, EtfDirectoryMonthlyHistory

logger = logging.getLogger(__name__)


def _to_float(val):
    """Cast a pandas/numpy scalar to a native Python float (None-safe).

    numpy.float64's repr changed in NumPy 2.0 (now "np.float64(1.23)" instead
    of "1.23"), which psycopg2 falls back to for unregistered types — passing
    a raw numpy value straight into an INSERT/UPDATE corrupts the SQL. Always
    cast DataFrame-sourced numeric values through this before assigning to an
    ORM column or raw SQL param.
    """
    if val is None or (isinstance(val, float) and val != val):  # NaN check
        return None
    return float(val)


def get_active_tickers(db: Session) -> list[str]:
    """Return list of active ticker symbols from the database."""
    tickers = db.query(Ticker.symbol).filter(Ticker.active == True).all()
    return [t.symbol for t in tickers]


def get_tickers_without_data(db: Session) -> list[str]:
    """Return active ticker symbols that have zero price records.

    These are newly added tickers that need a full history load.
    """
    from sqlalchemy import func, outerjoin

    results = (
        db.query(Ticker.symbol, func.count(MonthlyPrice.id).label("cnt"))
        .outerjoin(MonthlyPrice, Ticker.id == MonthlyPrice.ticker_id)
        .filter(Ticker.active == True)
        .group_by(Ticker.symbol)
        .having(func.count(MonthlyPrice.id) == 0)
        .all()
    )
    return [r.symbol for r in results]


def get_ticker_id(db: Session, symbol: str) -> int | None:
    """Get ticker ID by symbol. Returns None if not found."""
    ticker = db.query(Ticker).filter(Ticker.symbol == symbol.upper()).first()
    return ticker.id if ticker else None


def load_prices(db: Session, symbol: str, prices_df: pd.DataFrame, mode: str = "full") -> dict:
    """Load monthly price data into the database.

    Args:
        db: Database session
        symbol: Ticker symbol
        prices_df: DataFrame with year, month, high, low, close, adj_close
        mode: 'full' (skip existing) or 'incremental' (upsert)

    Returns:
        Dict with counts: {"inserted": n, "updated": n, "skipped": n}
    """
    ticker_id = get_ticker_id(db, symbol)
    if ticker_id is None:
        logger.error(f"Ticker {symbol} not found in database")
        return {"inserted": 0, "updated": 0, "skipped": 0, "error": "Ticker not found"}

    if prices_df.empty:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    for _, row in prices_df.iterrows():
        year = int(row["year"])
        month = int(row["month"])

        existing = db.query(MonthlyPrice).filter(
            and_(
                MonthlyPrice.ticker_id == ticker_id,
                MonthlyPrice.year == year,
                MonthlyPrice.month == month,
            )
        ).first()

        if existing:
            if mode == "incremental":
                # Update existing record
                existing.high = _to_float(row.get("high"))
                existing.low = _to_float(row.get("low"))
                existing.close = _to_float(row.get("close"))
                existing.adj_close = _to_float(row.get("adj_close"))
                counts["updated"] += 1
            else:
                # Full mode - skip existing
                counts["skipped"] += 1
        else:
            # Insert new record
            price = MonthlyPrice(
                ticker_id=ticker_id,
                year=year,
                month=month,
                high=_to_float(row.get("high")),
                low=_to_float(row.get("low")),
                close=_to_float(row.get("close")),
                adj_close=_to_float(row.get("adj_close")),
            )
            db.add(price)
            counts["inserted"] += 1

    db.commit()
    logger.info(
        f"Prices for {symbol}: "
        f"{counts['inserted']} inserted, {counts['updated']} updated, {counts['skipped']} skipped"
    )
    return counts


def load_dividends(db: Session, symbol: str, divs_df: pd.DataFrame, mode: str = "full") -> dict:
    """Load dividend data into the database.

    Args:
        db: Database session
        symbol: Ticker symbol
        divs_df: DataFrame with pay_date, amount
        mode: 'full' (skip existing) or 'incremental' (upsert)

    Returns:
        Dict with counts: {"inserted": n, "updated": n, "skipped": n}
    """
    ticker_id = get_ticker_id(db, symbol)
    if ticker_id is None:
        logger.error(f"Ticker {symbol} not found in database")
        return {"inserted": 0, "updated": 0, "skipped": 0, "error": "Ticker not found"}

    if divs_df.empty:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    for _, row in divs_df.iterrows():
        pay_date = row["pay_date"]

        existing = db.query(Dividend).filter(
            and_(
                Dividend.ticker_id == ticker_id,
                Dividend.pay_date == pay_date,
            )
        ).first()

        if existing:
            if mode == "incremental":
                existing.amount = _to_float(row["amount"])
                counts["updated"] += 1
            else:
                counts["skipped"] += 1
        else:
            div = Dividend(
                ticker_id=ticker_id,
                pay_date=pay_date,
                amount=_to_float(row["amount"]),
            )
            db.add(div)
            counts["inserted"] += 1

    db.commit()
    logger.info(
        f"Dividends for {symbol}: "
        f"{counts['inserted']} inserted, {counts['updated']} updated, {counts['skipped']} skipped"
    )
    return counts


def load_all(db: Session, fetch_results: dict, mode: str = "full") -> dict:
    """Load all fetched data into the database.

    Args:
        db: Database session
        fetch_results: Output from fetcher.fetch_all_tickers()
        mode: 'full' or 'incremental'

    Returns:
        Summary dict per symbol with price and dividend counts.
    """
    summary = {}

    for symbol, prices_df in fetch_results["prices"].items():
        price_counts = load_prices(db, symbol, prices_df, mode)
        div_counts = load_dividends(
            db, symbol,
            fetch_results["dividends"].get(symbol, pd.DataFrame()),
            mode,
        )
        summary[symbol] = {
            "prices": price_counts,
            "dividends": div_counts,
        }

    # Include errors from fetch
    for symbol, error in fetch_results.get("errors", {}).items():
        summary[symbol] = {"error": error}

    return summary


# ===========================================
# STANDALONE DAILY PRICE TABLES (SpyDailyPrice, OefDailyPrice, ...)
#
# Insert-only: never touches a row for a date already on file, only adds
# rows for dates that are missing. No update mode -- if Yahoo later revises
# a historical bar, the existing row is left as-is.
# ===========================================

def get_max_daily_date(db: Session, model, ticker: str):
    """Most recent price_date on file for `ticker` in a daily-prices table.

    Returns None if the table has no rows yet for this ticker.
    """
    return db.query(func.max(model.price_date)).filter(model.ticker == ticker).scalar()


def get_daily_price_stats(db: Session, model, ticker: str) -> dict:
    """Row count + date range on file for `ticker` in a daily-prices table."""
    row_count = db.query(func.count(model.id)).filter(model.ticker == ticker).scalar() or 0
    min_date = db.query(func.min(model.price_date)).filter(model.ticker == ticker).scalar()
    max_date = db.query(func.max(model.price_date)).filter(model.ticker == ticker).scalar()
    return {
        "row_count": row_count,
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
    }


def load_daily_prices(db: Session, model, ticker: str, prices_df: pd.DataFrame) -> dict:
    """Append daily price rows into a daily-prices table.

    Args:
        db: Database session
        model: ORM model class (SpyDailyPrice, OefDailyPrice, ...)
        ticker: Ticker symbol to stamp on each row
        prices_df: DataFrame with price_date, open, high, low, close, adj_close, volume

    Returns:
        Dict with counts: {"inserted": n, "skipped": n}
    """
    if prices_df.empty:
        return {"inserted": 0, "skipped": 0}

    existing_dates = {
        row[0] for row in db.query(model.price_date).filter(model.ticker == ticker).all()
    }

    counts = {"inserted": 0, "skipped": 0}
    for _, row in prices_df.iterrows():
        price_date = row["price_date"]

        if price_date in existing_dates:
            counts["skipped"] += 1
            continue

        volume = row.get("volume")
        rec = model(
            ticker=ticker,
            price_date=price_date,
            open=_to_float(row.get("open")),
            high=_to_float(row.get("high")),
            low=_to_float(row.get("low")),
            close=_to_float(row.get("close")),
            adj_close=_to_float(row.get("adj_close")),
            volume=int(volume) if volume is not None and pd.notna(volume) else None,
        )
        db.add(rec)
        existing_dates.add(price_date)
        counts["inserted"] += 1

    db.commit()
    logger.info(f"{ticker} daily prices: {counts['inserted']} inserted, {counts['skipped']} skipped")
    return counts


# ===========================================
# DAILY QUOTES (any ticker, price + 52w range snapshot per trading day)
# ===========================================

def save_daily_quotes(db: Session, quotes: dict) -> dict:
    """Upsert one row per ticker into daily_quotes, keyed by (ticker, quote_date).

    If a row already exists for that ticker+date, it's updated in place
    (price/range overwritten); otherwise a new row is inserted. This is
    the "if quote already written for that date, overwrite it" behavior --
    quote_date comes from fetcher.get_current_quotes(), which reports the
    actual trade date, not the server's calendar date, so repeated saves
    before a new trading day naturally keep overwriting the same row.

    Args:
        db: Database session
        quotes: {symbol: {"quote_date": "YYYY-MM-DD", "price": float,
                 "week52_low": float, "week52_high": float}}

    Returns:
        Dict with counts: {"inserted": n, "updated": n}
    """
    if not quotes:
        return {"inserted": 0, "updated": 0}

    counts = {"inserted": 0, "updated": 0}
    for symbol, q in quotes.items():
        quote_date = q["quote_date"]
        existing = db.query(DailyQuote).filter(
            DailyQuote.ticker == symbol,
            DailyQuote.quote_date == quote_date,
        ).first()

        if existing:
            existing.price = q["price"]
            existing.week52_low = q["week52_low"]
            existing.week52_high = q["week52_high"]
            counts["updated"] += 1
        else:
            db.add(DailyQuote(
                ticker=symbol,
                quote_date=quote_date,
                price=q["price"],
                week52_low=q["week52_low"],
                week52_high=q["week52_high"],
            ))
            counts["inserted"] += 1

    db.commit()
    logger.info(f"Daily quotes saved: {counts['inserted']} inserted, {counts['updated']} updated")
    return counts


# ===========================================
# ETF DIRECTORY MONTHLY HISTORY (isolated -- see EtfDirectoryMonthlyHistory
# docstring for why this stays separate from tickers/monthly_prices)
# ===========================================

def get_etf_directory_tickers() -> list[str]:
    """Read the curated ticker list straight from frontend/etf-directory.js.

    Single source of truth: the category/fund-name/link data lives only in
    that JS file (not database-backed yet), so this parses it at call time
    instead of keeping a second, driftable copy of the ticker list here.
    """
    js_path = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "etf-directory.js"
    text = js_path.read_text(encoding="utf-8")
    # Each curated row looks like: ['Category', 'TICKER', 'Fund Name', 'https://...'],
    tickers = re.findall(r"\[\s*'[^']*',\s*'([A-Z0-9.]+)',\s*'[^']*',\s*'[^']*'\s*\]", text)
    return sorted(set(tickers))


def get_max_etf_month(db: Session, ticker: str):
    """(year, month) of the most recent month on file for a ticker, or None if empty."""
    row = (
        db.query(EtfDirectoryMonthlyHistory.year, EtfDirectoryMonthlyHistory.month)
        .filter(EtfDirectoryMonthlyHistory.ticker == ticker)
        .order_by(EtfDirectoryMonthlyHistory.year.desc(), EtfDirectoryMonthlyHistory.month.desc())
        .first()
    )
    return (row.year, row.month) if row else None


def get_etf_history_stats(db: Session) -> dict:
    """Row count, ticker coverage, and date range across the whole table."""
    total = db.query(func.count(EtfDirectoryMonthlyHistory.id)).scalar() or 0
    tickers_covered = db.query(func.count(func.distinct(EtfDirectoryMonthlyHistory.ticker))).scalar() or 0
    oldest = (
        db.query(EtfDirectoryMonthlyHistory.year, EtfDirectoryMonthlyHistory.month)
        .order_by(EtfDirectoryMonthlyHistory.year.asc(), EtfDirectoryMonthlyHistory.month.asc())
        .first()
    )
    newest = (
        db.query(EtfDirectoryMonthlyHistory.year, EtfDirectoryMonthlyHistory.month)
        .order_by(EtfDirectoryMonthlyHistory.year.desc(), EtfDirectoryMonthlyHistory.month.desc())
        .first()
    )
    return {
        "total_rows": total,
        "tickers_covered": tickers_covered,
        "tickers_expected": len(get_etf_directory_tickers()),
        "oldest_month": f"{oldest.year}-{oldest.month:02d}" if oldest else None,
        "newest_month": f"{newest.year}-{newest.month:02d}" if newest else None,
    }


def _sanitize_monthly_bar(ticker: str, year: int, month: int, high, low, close):
    """Clamp an implausible high/low against that same month's close.

    Found in the wild: Yahoo's monthly-interval endpoint occasionally
    returns a garbage Open/High for one bar even though the daily bars
    for that exact month are completely clean (HDV 2024-09 showed
    high=$117.76 against a close of $23.52 -- daily data confirmed the
    real high was $23.84). A single month's high/low shouldn't be able
    to move >2.5x/<0.4x its own close, so clamp to close instead of
    storing the bad value, and log it so it's visible.
    """
    if close is None or close <= 0:
        return high, low, close
    if high is not None and high > close * 2.5:
        logger.warning(f"{ticker} {year}-{month:02d}: implausible high {high} vs close {close}, clamped to close")
        high = close
    if low is not None and low < close * 0.4:
        logger.warning(f"{ticker} {year}-{month:02d}: implausible low {low} vs close {close}, clamped to close")
        low = close
    return high, low, close


def load_etf_monthly_history(db: Session, ticker: str, prices_df: pd.DataFrame, divs_df: pd.DataFrame) -> dict:
    """Append monthly high/low/close/dividend rows for one ETF Directory ticker.

    Insert-only, same discipline as the daily-price tables: skips any
    (ticker, year, month) already on file, never updates one. The
    in-progress current calendar month must already be filtered out of
    prices_df before calling this (see the batch runner in api.py) --
    this function has no opinion on "closed" vs "open" months, it just
    inserts whatever rows it's handed and skips duplicates.

    Args:
        db: Database session
        ticker: Ticker symbol
        prices_df: DataFrame with year, month, high, low, close (from fetcher.get_monthly_prices)
        divs_df: DataFrame with pay_date, amount (from fetcher.get_dividends)

    Returns:
        Dict with counts: {"inserted": n, "skipped": n}
    """
    if prices_df.empty:
        return {"inserted": 0, "skipped": 0}

    # Aggregate dividends paid within each (year, month) into one total.
    monthly_divs = {}
    if divs_df is not None and not divs_df.empty:
        for _, row in divs_df.iterrows():
            pay_date = row["pay_date"]
            key = (pay_date.year, pay_date.month)
            monthly_divs[key] = monthly_divs.get(key, 0.0) + (_to_float(row["amount"]) or 0.0)

    existing = {
        (r.year, r.month)
        for r in db.query(EtfDirectoryMonthlyHistory.year, EtfDirectoryMonthlyHistory.month)
        .filter(EtfDirectoryMonthlyHistory.ticker == ticker).all()
    }

    counts = {"inserted": 0, "skipped": 0}
    for _, row in prices_df.iterrows():
        year, month = int(row["year"]), int(row["month"])
        if (year, month) in existing:
            counts["skipped"] += 1
            continue
        high, low, close = _sanitize_monthly_bar(
            ticker, year, month,
            _to_float(row.get("high")), _to_float(row.get("low")), _to_float(row.get("close")),
        )
        rec = EtfDirectoryMonthlyHistory(
            ticker=ticker, year=year, month=month,
            high=high, low=low, close=close,
            dividend=round(monthly_divs.get((year, month), 0.0), 6),
        )
        db.add(rec)
        existing.add((year, month))
        counts["inserted"] += 1

    db.commit()
    logger.info(f"{ticker} ETF directory history: {counts['inserted']} inserted, {counts['skipped']} skipped")
    return counts


def get_etf_10yr_range(db: Session, tickers: list[str]) -> dict:
    """10-year high/low range, plus a price-then-vs-now comparison, per
    ticker, from etf_directory_monthly_history. Uses the most recent 120
    months on file (fewer if a ticker has less than 10 years of history
    loaded yet).

    Returns:
        {ticker: {"ten_yr_low": float, "ten_yr_high": float,
                   "months_covered": int, "oldest_month": "YYYY-MM",
                   "price_then": float, "price_now": float,
                   "change_pct": float}}
        Tickers with no history on file are simply omitted.
    """
    results = {}
    for ticker in tickers:
        rows = (
            db.query(EtfDirectoryMonthlyHistory)
            .filter(EtfDirectoryMonthlyHistory.ticker == ticker)
            .order_by(EtfDirectoryMonthlyHistory.year.desc(), EtfDirectoryMonthlyHistory.month.desc())
            .limit(120)
            .all()
        )
        if not rows:
            continue
        highs = [r.high for r in rows if r.high is not None]
        lows = [r.low for r in rows if r.low is not None]
        if not highs or not lows:
            continue

        newest, oldest = rows[0], rows[-1]  # query is newest-first
        price_then, price_now = oldest.close, newest.close
        change_pct = ((price_now / price_then) - 1) * 100 if price_then else None

        results[ticker] = {
            "ten_yr_low": round(min(lows), 2),
            "ten_yr_high": round(max(highs), 2),
            "months_covered": len(rows),
            "oldest_month": f"{oldest.year}-{oldest.month:02d}",
            "price_then": round(price_then, 2) if price_then is not None else None,
            "price_now": round(price_now, 2) if price_now is not None else None,
            "change_pct": round(change_pct, 1) if change_pct is not None else None,
        }
    return results

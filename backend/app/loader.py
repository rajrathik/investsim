"""Database loader - saves fetched data into the database.

Supports two modes:
  - Full load: inserts all history (skips existing records)
  - Incremental: upserts last 2 months (updates if exists, inserts if new)
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_
import pandas as pd

from app.models import Ticker, MonthlyPrice, Dividend

logger = logging.getLogger(__name__)


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
                existing.high = row.get("high")
                existing.low = row.get("low")
                existing.close = row.get("close")
                existing.adj_close = row.get("adj_close")
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
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                adj_close=row.get("adj_close"),
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
                existing.amount = row["amount"]
                counts["updated"] += 1
            else:
                counts["skipped"] += 1
        else:
            div = Dividend(
                ticker_id=ticker_id,
                pay_date=pay_date,
                amount=row["amount"],
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

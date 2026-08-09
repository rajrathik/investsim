"""Yahoo Finance data fetcher.

Fetches monthly price history and dividend data for active tickers.
Two modes:
  - Full history: all available data
  - Incremental: last 2 months only (for ongoing updates)
"""
import time
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import yfinance as yf
import pandas as pd

from app.config import MAX_TICKERS, FULL_HISTORY_YEARS

logger = logging.getLogger(__name__)


class FetcherError(Exception):
    """Raised when fetcher encounters an error."""
    pass


def get_monthly_prices(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Fetch monthly price data for a single ticker.

    Args:
        symbol: Ticker symbol (e.g. 'AAPL')
        start_date: Start date 'YYYY-MM-DD' (None = 20 years ago)
        end_date: End date 'YYYY-MM-DD' (None = today)

    Returns:
        DataFrame with columns: year, month, high, low, close, adj_close
        Empty DataFrame if no data found.
    """
    try:
        # Default to 20 years of history if no start date
        if start_date is None:
            start_date = (date.today() - relativedelta(years=FULL_HISTORY_YEARS)).replace(day=1).isoformat()
        if end_date is None:
            end_date = date.today().isoformat()

        ticker = yf.Ticker(symbol)
        hist = ticker.history(
            start=start_date,
            end=end_date,
            interval="1mo",
            auto_adjust=False,
        )

        if hist.empty:
            logger.warning(f"No price data found for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame({
            "year": hist.index.year,
            "month": hist.index.month,
            "high": hist["High"],
            "low": hist["Low"],
            "close": hist["Close"],
            "adj_close": hist["Adj Close"] if "Adj Close" in hist.columns else hist["Close"],
        })

        # Drop rows where all price columns are NaN
        df = df.dropna(subset=["high", "low", "close"], how="all")

        # Remove duplicates for same year+month (keep last)
        df = df.drop_duplicates(subset=["year", "month"], keep="last")

        df = df.reset_index(drop=True)
        logger.info(f"Fetched {len(df)} monthly price records for {symbol}")
        return df

    except Exception as e:
        logger.error(f"Error fetching prices for {symbol}: {e}")
        raise FetcherError(f"Failed to fetch prices for {symbol}: {e}")


def get_daily_prices(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Fetch daily OHLCV price data for a single ticker.

    Args:
        symbol: Ticker symbol (e.g. 'SPY')
        start_date: Start date 'YYYY-MM-DD' (None + end_date None = max available history)
        end_date: End date 'YYYY-MM-DD' (None = through today)

    Returns:
        DataFrame with columns: price_date, open, high, low, close, adj_close, volume
        Empty DataFrame if no data found.
    """
    try:
        ticker = yf.Ticker(symbol)

        if start_date is None and end_date is None:
            # One-time full load: everything Yahoo has for this ticker.
            hist = ticker.history(period="max", interval="1d", auto_adjust=False)
        else:
            hist = ticker.history(start=start_date, end=end_date, interval="1d", auto_adjust=False)

        if hist.empty:
            logger.warning(f"No daily price data found for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame({
            "price_date": hist.index.date,
            "open": hist["Open"],
            "high": hist["High"],
            "low": hist["Low"],
            "close": hist["Close"],
            "adj_close": hist["Adj Close"] if "Adj Close" in hist.columns else hist["Close"],
            "volume": hist["Volume"] if "Volume" in hist.columns else None,
        })

        # Drop rows where all price columns are NaN
        df = df.dropna(subset=["open", "high", "low", "close"], how="all")

        # Remove duplicates for same date (keep last)
        df = df.drop_duplicates(subset=["price_date"], keep="last")

        df = df.reset_index(drop=True)
        logger.info(f"Fetched {len(df)} daily price records for {symbol}")
        return df

    except Exception as e:
        logger.error(f"Error fetching daily prices for {symbol}: {e}")
        raise FetcherError(f"Failed to fetch daily prices for {symbol}: {e}")


def get_dividends(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Fetch dividend history for a single ticker.

    Args:
        symbol: Ticker symbol (e.g. 'AAPL')
        start_date: Start date 'YYYY-MM-DD' (None = 20 years ago)
        end_date: End date 'YYYY-MM-DD' (None = today)

    Returns:
        DataFrame with columns: pay_date, amount
        Empty DataFrame if no dividends found.
    """
    try:
        # Default to 20 years of history if no start date
        if start_date is None:
            start_date = (date.today() - relativedelta(years=FULL_HISTORY_YEARS)).replace(day=1).isoformat()
        if end_date is None:
            end_date = date.today().isoformat()

        ticker = yf.Ticker(symbol)
        divs = ticker.dividends

        if divs.empty:
            logger.warning(f"No dividend data found for {symbol}")
            return pd.DataFrame()

        # Filter by date range if specified
        if start_date:
            divs = divs[divs.index >= start_date]
        if end_date:
            divs = divs[divs.index <= end_date]

        if divs.empty:
            return pd.DataFrame()

        df = pd.DataFrame({
            "pay_date": divs.index.date,
            "amount": divs.values,
        })

        # Remove duplicates for same date (keep last)
        df = df.drop_duplicates(subset=["pay_date"], keep="last")
        df = df.reset_index(drop=True)

        logger.info(f"Fetched {len(df)} dividend records for {symbol}")
        return df

    except Exception as e:
        logger.error(f"Error fetching dividends for {symbol}: {e}")
        raise FetcherError(f"Failed to fetch dividends for {symbol}: {e}")


def fetch_all_tickers(
    symbols: list[str],
    mode: str = "full",
    delay_seconds: float = 1.0,
    months: int = None,
) -> dict:
    """Fetch price and dividend data for multiple tickers.

    Args:
        symbols: List of ticker symbols
        mode: 'full' for all history, 'incremental' for last N months
        delay_seconds: Pause between tickers to avoid rate limiting
        months: For incremental mode, how many months back (default 2)

    Returns:
        Dict with structure:
        {
            "prices": {symbol: DataFrame, ...},
            "dividends": {symbol: DataFrame, ...},
            "errors": {symbol: error_message, ...}
        }
    """
    if len(symbols) > MAX_TICKERS:
        raise FetcherError(f"Too many tickers: {len(symbols)} (max {MAX_TICKERS})")

    if len(symbols) == 0:
        raise FetcherError("No tickers provided")

    # Calculate date range for incremental mode
    start_date = None
    end_date = None
    if mode == "incremental":
        today = date.today()
        incr_months = months if months else 2
        start_date = (today - relativedelta(months=incr_months)).replace(day=1).isoformat()
        end_date = today.isoformat()
        logger.info(f"Incremental mode: {start_date} to {end_date} ({incr_months} months)")
    elif mode == "current-month":
        # Pinned to the 1st of the current calendar month through today.
        # Yahoo's monthly bar for an in-progress month is a live candle, so
        # this returns exactly one row per ticker (the current month) —
        # never touches any other month's data.
        today = date.today()
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()
        logger.info(f"Current-month mode: {start_date} to {end_date}")

    results = {
        "prices": {},
        "dividends": {},
        "errors": {},
    }

    for i, symbol in enumerate(symbols):
        symbol = symbol.upper().strip()
        logger.info(f"Fetching {symbol} ({i+1}/{len(symbols)})...")

        try:
            prices_df = get_monthly_prices(symbol, start_date, end_date)
            results["prices"][symbol] = prices_df

            divs_df = get_dividends(symbol, start_date, end_date)
            results["dividends"][symbol] = divs_df

        except FetcherError as e:
            results["errors"][symbol] = str(e)
            logger.error(f"Skipping {symbol}: {e}")

        # Rate limiting - pause between tickers (skip after last one)
        if i < len(symbols) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    successful = len(results["prices"])
    failed = len(results["errors"])
    logger.info(f"Fetch complete: {successful} succeeded, {failed} failed")

    return results

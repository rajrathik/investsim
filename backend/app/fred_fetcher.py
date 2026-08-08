"""FRED data fetcher for money market rates.

Fetches monthly Federal Funds Rate from FRED (Federal Reserve Economic Data).
Series: FEDFUNDS - Effective Federal Funds Rate (monthly)

This serves as a proxy for money market account rates.

Two modes:
  - Full history: all available data
  - Incremental: last 3 months
"""
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd

from app.config import FULL_HISTORY_YEARS

logger = logging.getLogger(__name__)

# FRED CSV download URL (no API key needed)
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SERIES = "FEDFUNDS"


class FredFetcherError(Exception):
    """Raised when FRED fetcher encounters an error."""
    pass


def get_monthly_rates(start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Fetch monthly Federal Funds Rate from FRED.

    Args:
        start_date: Start date 'YYYY-MM-DD' (None = FULL_HISTORY_YEARS ago)
        end_date: End date 'YYYY-MM-DD' (None = today)

    Returns:
        DataFrame with columns: year, month, rate
        Empty DataFrame if no data found.
    """
    try:
        if start_date is None:
            start_date = (date.today() - relativedelta(years=FULL_HISTORY_YEARS)).replace(day=1).isoformat()
        if end_date is None:
            end_date = date.today().isoformat()

        url = (
            f"{FRED_CSV_URL}?id={FRED_SERIES}"
            f"&cosd={start_date}&coed={end_date}"
        )

        logger.info(f"Fetching FRED data: {FRED_SERIES} from {start_date} to {end_date}")

        df = pd.read_csv(url, parse_dates=["observation_date"])

        if df.empty:
            logger.warning("No FRED data returned")
            return pd.DataFrame()

        # Handle missing values (FRED uses '.' for missing)
        df[FRED_SERIES] = pd.to_numeric(df[FRED_SERIES], errors="coerce")
        df = df.dropna(subset=[FRED_SERIES])

        result = pd.DataFrame({
            "year": df["observation_date"].dt.year,
            "month": df["observation_date"].dt.month,
            "rate": df[FRED_SERIES].values,
        })

        result = result.drop_duplicates(subset=["year", "month"], keep="last")

        # FRED's CSV endpoint silently ignores cosd/coed and returns the FULL
        # series when the requested window contains zero published
        # observations (e.g. asking for a month FRED hasn't published yet).
        # Always re-enforce the window client-side so callers get an empty
        # DataFrame in that case instead of the entire history.
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        obs_period = pd.to_datetime(result["year"].astype(str) + "-" + result["month"].astype(str) + "-01")
        result = result[(obs_period >= start_ts.replace(day=1)) & (obs_period <= end_ts)]

        result = result.reset_index(drop=True)

        logger.info(f"Fetched {len(result)} monthly rate records from FRED")
        return result

    except Exception as e:
        logger.error(f"Error fetching FRED data: {e}")
        raise FredFetcherError(f"Failed to fetch FRED data: {e}")


def get_monthly_rates_incremental(months: int = 3) -> pd.DataFrame:
    """Fetch the last N months of rates for incremental update (default 3)."""
    start_date = (date.today() - relativedelta(months=months)).replace(day=1).isoformat()
    end_date = date.today().isoformat()
    return get_monthly_rates(start_date=start_date, end_date=end_date)


def get_monthly_rates_current_month() -> pd.DataFrame:
    """Fetch just the current calendar month's rate, if FRED has published it yet.

    FRED publishes FEDFUNDS as a monthly average AFTER the month closes (with a
    short lag into the following month) — so this commonly returns an empty
    DataFrame mid-month. That's expected, not an error.
    """
    today = date.today()
    start_date = today.replace(day=1).isoformat()
    end_date = today.isoformat()
    return get_monthly_rates(start_date=start_date, end_date=end_date)


def compute_annual_averages(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Compute annual average rates from monthly data.

    Args:
        monthly_df: DataFrame with year, month, rate columns

    Returns:
        DataFrame with columns: year, avg_rate
    """
    if monthly_df.empty:
        return pd.DataFrame()

    annual = (
        monthly_df.groupby("year")["rate"]
        .mean()
        .round(4)
        .reset_index()
        .rename(columns={"rate": "avg_rate"})
    )

    logger.info(f"Computed {len(annual)} annual average rates")
    return annual

"""Batch runner - fetch Yahoo Finance data and load into database.

Usage:
    python run_batch.py full          # One-time full history load
    python run_batch.py incremental   # Ongoing: last 2 months, upsert
"""
import sys
import os
import logging

# Load .env
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

from app.database import SessionLocal
from app.loader import get_active_tickers, load_all
from app.fetcher import fetch_all_tickers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("full", "incremental"):
        print("Usage: python run_batch.py [full|incremental]")
        print("  full         - Load all available history for active tickers")
        print("  incremental  - Load last 2 months and merge with existing data")
        sys.exit(1)

    mode = sys.argv[1]
    logger.info(f"Starting batch run in '{mode}' mode")

    # Get active tickers from database
    db = SessionLocal()
    try:
        symbols = get_active_tickers(db)
        if not symbols:
            logger.error("No active tickers found! Add tickers to the 'tickers' table first.")
            sys.exit(1)

        logger.info(f"Found {len(symbols)} active tickers: {', '.join(symbols)}")

        # Fetch from Yahoo Finance
        logger.info("Fetching data from Yahoo Finance...")
        fetch_results = fetch_all_tickers(symbols, mode=mode, delay_seconds=1.0)

        # Load into database
        logger.info("Loading data into database...")
        summary = load_all(db, fetch_results, mode=mode)

        # Print summary
        print("\n" + "=" * 60)
        print(f"BATCH LOAD SUMMARY ({mode.upper()} MODE)")
        print("=" * 60)
        for symbol, details in summary.items():
            if "error" in details:
                print(f"  {symbol:6s}  ERROR: {details['error']}")
            else:
                p = details["prices"]
                d = details["dividends"]
                print(
                    f"  {symbol:6s}  Prices: {p['inserted']}i/{p['updated']}u/{p['skipped']}s  "
                    f"Dividends: {d['inserted']}i/{d['updated']}u/{d['skipped']}s"
                )
        print("=" * 60)

        errors = fetch_results.get("errors", {})
        if errors:
            print(f"\nErrors ({len(errors)}):")
            for sym, err in errors.items():
                print(f"  {sym}: {err}")

    finally:
        db.close()

    logger.info("Batch run complete.")


if __name__ == "__main__":
    main()

"""Batch runner for FRED money market rates.

Usage:
    python run_fred_batch.py full          # One-time full history load
    python run_fred_batch.py incremental   # Ongoing: last 3 months, upsert
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
from app.fred_fetcher import get_monthly_rates, get_monthly_rates_incremental
from app.mm_rates import load_all_rates

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("full", "incremental"):
        print("Usage: python run_fred_batch.py [full|incremental]")
        print("  full         - Load all available history of money market rates")
        print("  incremental  - Load last 3 months and merge with existing data")
        sys.exit(1)

    mode = sys.argv[1]
    logger.info(f"Starting FRED batch run in '{mode}' mode")

    # Fetch from FRED
    if mode == "full":
        monthly_df = get_monthly_rates()
    else:
        monthly_df = get_monthly_rates_incremental()

    logger.info(f"Fetched {len(monthly_df)} monthly rate records")

    # Load into database
    db = SessionLocal()
    try:
        summary = load_all_rates(db, monthly_df, mode=mode)

        print("\n" + "=" * 60)
        print(f"FRED RATES LOAD SUMMARY ({mode.upper()} MODE)")
        print("=" * 60)
        for category, counts in summary.items():
            parts = []
            for key, val in counts.items():
                parts.append(f"{val}{key[0]}")
            print(f"  {category:10s}  {'/'.join(parts)}")
        print("=" * 60)

    finally:
        db.close()

    logger.info("FRED batch run complete.")


if __name__ == "__main__":
    main()

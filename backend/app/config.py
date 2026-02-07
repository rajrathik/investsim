"""Application configuration."""
import os

# Database URL - swap to PostgreSQL later:
# DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/portfolio"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///portfolio.db"
)

# Ticker limits
MAX_TICKERS = 50

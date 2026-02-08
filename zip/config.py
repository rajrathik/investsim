"""Application configuration."""
import os

# SQL Server connection settings
DB_SERVER = os.getenv("DB_SERVER", "REDACTED-DB-HOST")
DB_NAME = os.getenv("DB_NAME", "REDACTED-DB-NAME")
DB_USER = os.getenv("DB_USER", "REDACTED-DB-USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # Set via .env or environment variable
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

# SQLAlchemy connection URL for SQL Server
DATABASE_URL = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}"
    f"?driver={DB_DRIVER.replace(' ', '+')}"
)

# For unit tests - use SQLite in-memory
TEST_DATABASE_URL = "sqlite:///:memory:"

# Ticker limits
MAX_TICKERS = 50

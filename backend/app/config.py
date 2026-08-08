"""Application configuration."""
import os

# ---------------------------------------------------------------------------
# Database type: "postgres" or "sqlserver"
# Flip this single value in .env to switch the entire backend.
# ---------------------------------------------------------------------------
DB_TYPE = os.getenv("DB_TYPE", "postgres").strip().lower()

# --- SQL Server settings (used when DB_TYPE=sqlserver) --------------------
DB_SERVER = os.getenv("DB_SERVER", "")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # Set via .env or environment variable
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

SQLSERVER_URL = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}"
    f"?driver={DB_DRIVER.replace(' ', '+')}"
)

# --- PostgreSQL settings (used when DB_TYPE=postgres) ---------------------
POSTGRES_URL = os.getenv("POSTGRES_URL", "")

# --- Active DATABASE_URL based on DB_TYPE ---------------------------------
if DB_TYPE == "sqlserver":
    DATABASE_URL = SQLSERVER_URL
else:
    DATABASE_URL = POSTGRES_URL

# For unit tests - use SQLite in-memory
TEST_DATABASE_URL = "sqlite:///:memory:"

# Ticker limits
MAX_TICKERS = 50

# How many years of history to fetch in full mode
FULL_HISTORY_YEARS = 30

# Set to True when ready to allow POST/PUT/DELETE from API
# Reads from .env: ENABLE_WRITE_API=True
ENABLE_WRITE_API = os.getenv("ENABLE_WRITE_API", "False").strip().lower() in ("true", "1", "yes")

# CORS allowed origins (comma-separated)
# Default "*" allows all — lock down for production via .env or Railway variables
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

# Auth0 settings
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ALGORITHMS = os.getenv("AUTH0_ALGORITHMS", "RS256").split(",")

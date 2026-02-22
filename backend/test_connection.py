"""Test database connection and create tables.

Supports both SQL Server (DB_TYPE=sqlserver) and PostgreSQL (DB_TYPE=postgres).
"""
import sys
import os

# Load .env for password
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

from app.config import DATABASE_URL, DB_TYPE
from app.database import engine, init_db, SessionLocal
from app.models import Ticker, MonthlyPrice, Dividend
from app.mm_rates import MonthlyMoneyMarketRate, AnnualMoneyMarketRate
from sqlalchemy import inspect, text

# Mask password in URL for display
display_url = DATABASE_URL
if "@" in display_url:
    pre, post = display_url.split("@", 1)
    # Mask everything after last : in the pre-@ portion (the password)
    idx = pre.rfind(":")
    if idx != -1:
        display_url = pre[:idx] + ":***@" + post

print(f"DB Type:  {DB_TYPE}")
print(f"URL:      {display_url}")
print()

# Test connection — version query differs per dialect
try:
    with engine.connect() as conn:
        if DB_TYPE == "sqlserver":
            result = conn.execute(text("SELECT @@VERSION"))
        else:
            result = conn.execute(text("SELECT version()"))
        version = result.scalar()
        print(f"Connected! Database version:\n{version}\n")
except Exception as e:
    print(f"CONNECTION FAILED: {e}")
    sys.exit(1)

# Create tables
print("Creating tables...")
init_db()

# Verify tables
inspector = inspect(engine)
for table in inspector.get_table_names():
    print(f"\n=== {table} ===")
    for col in inspector.get_columns(table):
        print(f"  {col['name']:15} {str(col['type']):20} nullable={col['nullable']}")

# Check row counts
db = SessionLocal()
print(f"\nTickers count:        {db.query(Ticker).count()}")
print(f"Monthly Prices count: {db.query(MonthlyPrice).count()}")
print(f"Dividends count:      {db.query(Dividend).count()}")
print(f"Monthly MM Rates:     {db.query(MonthlyMoneyMarketRate).count()}")
print(f"Annual MM Rates:      {db.query(AnnualMoneyMarketRate).count()}")
db.close()

print("\nAll good! Database is ready.")

"""Test SQL Server connection and create tables."""
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

from app.config import DATABASE_URL, DB_SERVER, DB_NAME, DB_USER
from app.database import engine, init_db, SessionLocal
from app.models import Ticker, MonthlyPrice, Dividend
from app.mm_rates import MonthlyMoneyMarketRate, AnnualMoneyMarketRate
from sqlalchemy import inspect, text

print(f"Server:   {DB_SERVER}")
print(f"Database: {DB_NAME}")
print(f"User:     {DB_USER}")
print(f"URL:      {DATABASE_URL.replace(os.getenv('DB_PASSWORD', ''), '***')}")
print()

# Test connection
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT @@VERSION"))
        version = result.scalar()
        print(f"Connected! SQL Server version:\n{version}\n")
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

"""
One-time migration: add display_rate, display_upto, product_type columns
to stack_earn_savings_tiers and stack_earn_goal_tiers tables.

Run once on each DB (SQL Server local + Railway PostgreSQL).

Usage:
    cd C:/Raj/python/portfolio-simulator/backend
    ../venv/Scripts/python onetime/migrate_stack_earn_add_columns.py

To run against Railway PostgreSQL, set POSTGRES_URL in backend/.env and
set DB_TYPE=postgres before running.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env before importing config so os.getenv picks up local settings
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.config import DB_TYPE, DATABASE_URL
from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

TABLES = ["stack_earn_savings_tiers", "stack_earn_goal_tiers"]

if DB_TYPE == "postgres":
    ALTER_STMTS = [
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS display_rate INTEGER DEFAULT 1",
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS display_upto INTEGER DEFAULT 0",
        "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS product_type VARCHAR(100) DEFAULT 'PurposeSaving'",
    ]
else:
    # SQL Server: no IF NOT EXISTS — wrap in existence check
    ALTER_STMTS = [
        (
            "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('{table}') AND name = 'display_rate') "
            "ALTER TABLE {table} ADD display_rate INT DEFAULT 1"
        ),
        (
            "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('{table}') AND name = 'display_upto') "
            "ALTER TABLE {table} ADD display_upto INT DEFAULT 0"
        ),
        (
            "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('{table}') AND name = 'product_type') "
            "ALTER TABLE {table} ADD product_type NVARCHAR(100) DEFAULT 'PurposeSaving'"
        ),
    ]

# Backfill NULLs after column creation
BACKFILL_STMTS = [
    "UPDATE {table} SET display_rate = 1 WHERE display_rate IS NULL",
    "UPDATE {table} SET display_upto = 0 WHERE display_upto IS NULL",
    "UPDATE {table} SET product_type = 'PurposeSaving' WHERE product_type IS NULL",
]

with engine.begin() as conn:
    for table in TABLES:
        print(f"\n--- {table} ---")
        for tmpl in ALTER_STMTS:
            stmt = tmpl.format(table=table)
            print(f"  {stmt[:80]}…" if len(stmt) > 80 else f"  {stmt}")
            conn.execute(text(stmt))
        for tmpl in BACKFILL_STMTS:
            stmt = tmpl.format(table=table)
            print(f"  {stmt}")
            conn.execute(text(stmt))

print("\nMigration complete.")

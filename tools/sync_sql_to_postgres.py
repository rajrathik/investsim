"""Sync SQL Server data to PostgreSQL (Railway).

Reads from your local SQL Server and writes to a Railway PostgreSQL database.
Creates tables in PostgreSQL if they don't exist. Upserts all data.

Usage:
    cd C:\\Raj\\python\\portfolio-simulator
    venv\\Scripts\\python tools\\sync_sql_to_postgres.py

    # Or sync specific tables only:
    venv\\Scripts\\python tools\\sync_sql_to_postgres.py --tables tickers monthly_prices dividends

    # Dry run (show counts, don't write):
    venv\\Scripts\\python tools\\sync_sql_to_postgres.py --dry-run

    # Show row counts on both sides:
    venv\\Scripts\\python tools\\sync_sql_to_postgres.py --status

Required environment variables (set in backend\\.env or system env):
    POSTGRES_URL  = postgresql://user:pass@host:port/dbname
                    (Railway provides this as DATABASE_URL on the PostgreSQL service)

SQL Server connection uses existing settings from backend\\.env:
    DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, DB_DRIVER
"""

import os
import sys
import argparse
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Load .env before anything else
# ---------------------------------------------------------------------------
_env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Build connection URLs
# ---------------------------------------------------------------------------

# Source: SQL Server (local)
_DB_SERVER   = os.getenv("DB_SERVER", "REDACTED-DB-HOST")
_DB_NAME     = os.getenv("DB_NAME", "REDACTED-DB-NAME")
_DB_USER     = os.getenv("DB_USER", "REDACTED-DB-USER")
_DB_PASSWORD = os.getenv("DB_PASSWORD", "")
_DB_DRIVER   = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

SQL_SERVER_URL = (
    f"mssql+pyodbc://{_DB_USER}:{_DB_PASSWORD}@{_DB_SERVER}/{_DB_NAME}"
    f"?driver={_DB_DRIVER.replace(' ', '+')}"
)

# Target: PostgreSQL (Railway)
POSTGRES_URL = os.getenv("POSTGRES_URL", "")

# Allow --help to work without POSTGRES_URL
if not POSTGRES_URL and "--help" not in sys.argv and "-h" not in sys.argv:
    print("ERROR: POSTGRES_URL environment variable is not set.")
    print()
    print("Set it in backend\\.env:")
    print("    POSTGRES_URL=postgresql://user:pass@host:port/dbname")
    print()
    print("Railway provides this as DATABASE_URL on your PostgreSQL service.")
    print("Copy it from Railway dashboard > PostgreSQL > Connect > Connection URL")
    sys.exit(1)


# ---------------------------------------------------------------------------
# SQLAlchemy setup — two separate engines (deferred until actually needed)
# ---------------------------------------------------------------------------
from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

# Engines created lazily so --help works without valid connection strings
src_engine = None
dst_engine = None


def _init_engines():
    """Create database engines. Called once before any DB operations."""
    global src_engine, dst_engine
    if src_engine is None:
        src_engine = create_engine(SQL_SERVER_URL, echo=False)
    if dst_engine is None:
        if not POSTGRES_URL:
            print("ERROR: POSTGRES_URL is not set.")
            sys.exit(1)
        dst_engine = create_engine(POSTGRES_URL, echo=False)


# ---------------------------------------------------------------------------
# Model definitions (mirrors backend/app/models.py + mm_rates.py)
# These are independent of the backend models — same schema, separate Base
# so we can create_all on the Postgres engine without touching SQL Server.
# ---------------------------------------------------------------------------
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint
)


def _utcnow():
    return datetime.now(timezone.utc)


class Ticker(Base):
    __tablename__ = "tickers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)


class MonthlyPrice(Base):
    __tablename__ = "monthly_prices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("ticker_id", "year", "month", name="uq_ticker_year_month"),
    )


class Dividend(Base):
    __tablename__ = "dividends"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    pay_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("ticker_id", "pay_date", name="uq_ticker_pay_date"),
    )


class MonthlyMoneyMarketRate(Base):
    __tablename__ = "monthly_mm_rates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    rate = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_mm_year_month"),
    )


class AnnualMoneyMarketRate(Base):
    __tablename__ = "annual_mm_rates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, unique=True, nullable=False, index=True)
    avg_rate = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, nullable=False)


class UserLogin(Base):
    __tablename__ = "user_logins"
    id = Column(Integer, primary_key=True, autoincrement=True)
    auth0_user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    login_time = Column(DateTime, default=_utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)


class UserAdmin(Base):
    __tablename__ = "user_admin"
    email = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=True)


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(8), nullable=False, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    error_detail = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class SavedSimulation(Base):
    __tablename__ = "saved_simulations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    auth0_user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    tickers_json = Column(String(2000), nullable=False)
    start_year = Column(Integer, nullable=False)
    end_year = Column(Integer, nullable=False)
    monthly_amount = Column(Float, nullable=False)
    annual_growth = Column(Float, nullable=False, default=0)
    total_invested = Column(Float, nullable=False)
    equity_value = Column(Float, nullable=False)
    dividends_earned = Column(Float, nullable=False)
    cash_accrual = Column(Float, nullable=False)
    mm_earned = Column(Float, nullable=False)
    portfolio_balance = Column(Float, nullable=False)
    total_return_pct = Column(Float, nullable=False)
    mmf_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class StackEarnSavingsTier(Base):
    __tablename__ = "stack_earn_savings_tiers"
    tier_number = Column(Integer, primary_key=True)
    tier_label  = Column(String(50), nullable=False)
    min_amount  = Column(Float, nullable=False)
    max_amount  = Column(Float, nullable=True)
    annual_rate = Column(Float, nullable=False)


class StackEarnGoalTier(Base):
    __tablename__ = "stack_earn_goal_tiers"
    tier_number = Column(Integer, primary_key=True)
    tier_label  = Column(String(50), nullable=False)
    min_amount  = Column(Float, nullable=False)
    max_amount  = Column(Float, nullable=True)
    annual_rate = Column(Float, nullable=False)


# ---------------------------------------------------------------------------
# Sync order: parent tables first (tickers before prices/dividends)
# ---------------------------------------------------------------------------

# Tables that hold the core market data (what you'd sync regularly)
DATA_TABLES = [
    ("tickers",           Ticker),
    ("monthly_prices",    MonthlyPrice),
    ("dividends",         Dividend),
    ("monthly_mm_rates",  MonthlyMoneyMarketRate),
    ("annual_mm_rates",   AnnualMoneyMarketRate),
    ("user_admin",              UserAdmin),
    ("stack_earn_savings_tiers", StackEarnSavingsTier),
    ("stack_earn_goal_tiers",    StackEarnGoalTier),
]

# Tables that hold transactional/log data (optional, large, slow)
LOG_TABLES = [
    ("user_logins",       UserLogin),
    ("api_request_logs",  ApiRequestLog),
    ("saved_simulations", SavedSimulation),
]

ALL_TABLES = DATA_TABLES + LOG_TABLES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(engine, name):
    """Quote an identifier for the engine's dialect.
    SQL Server uses [brackets], PostgreSQL uses "double quotes"."""
    if engine.dialect.name == "mssql":
        return f"[{name}]"
    return f'"{name}"'


def get_row_count(engine, table_name):
    """Get row count for a table. Returns 0 if table doesn't exist."""
    insp = inspect(engine)
    if table_name not in insp.get_table_names():
        return -1  # table doesn't exist
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {_q(engine, table_name)}"))
        return result.scalar()


def get_column_names(engine, table_name):
    """Get column names for a table."""
    insp = inspect(engine)
    return [col["name"] for col in insp.get_columns(table_name)]


def read_all_rows(engine, table_name, columns):
    """Read all rows from a table as list of dicts."""
    # Quote column names to handle reserved words (e.g. "close" in SQL Server)
    cols = ", ".join(_q(engine, c) for c in columns)
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT {cols} FROM {_q(engine, table_name)} ORDER BY 1"))
        return [dict(zip(columns, row)) for row in result]


def sync_table(table_name, model_class, dry_run=False):
    """Sync one table from SQL Server to PostgreSQL.

    Strategy:
    - If Postgres table is empty: bulk INSERT all rows
    - If Postgres table has data: TRUNCATE and re-INSERT (full replace)

    This is a simple full-sync approach. For large log tables,
    you might want incremental sync later.
    """
    print(f"\n{'='*60}")
    print(f"  Syncing: {table_name}")
    print(f"{'='*60}")

    # Get source count
    src_count = get_row_count(src_engine, table_name)
    if src_count == -1:
        print(f"  SKIP: Table '{table_name}' does not exist in SQL Server")
        return {"table": table_name, "status": "skipped", "reason": "not in source"}
    print(f"  Source (SQL Server): {src_count:,} rows")

    # Get target count
    dst_count = get_row_count(dst_engine, table_name)
    if dst_count == -1:
        print(f"  Target (PostgreSQL): table does not exist — will be created")
    else:
        print(f"  Target (PostgreSQL): {dst_count:,} rows")

    if src_count == 0:
        print(f"  SKIP: Source table is empty, nothing to sync")
        return {"table": table_name, "status": "skipped", "reason": "source empty"}

    if dry_run:
        print(f"  DRY RUN: Would sync {src_count:,} rows")
        return {"table": table_name, "status": "dry-run", "rows": src_count}

    # --- Read all rows from source ---
    start = time.time()
    src_columns = get_column_names(src_engine, table_name)
    # Only sync columns that exist in the PostgreSQL model
    model_columns = {c.name for c in model_class.__table__.columns}
    sync_columns = [c for c in src_columns if c in model_columns]
    if set(sync_columns) != set(src_columns):
        skipped = set(src_columns) - model_columns
        print(f"  Note: skipping columns not in model: {skipped}")
    print(f"  Reading from SQL Server...", end=" ", flush=True)
    rows = read_all_rows(src_engine, table_name, sync_columns)
    print(f"got {len(rows):,} rows in {time.time()-start:.1f}s")

    if not rows:
        print(f"  SKIP: No rows returned")
        return {"table": table_name, "status": "skipped", "reason": "no rows"}

    # --- Write to PostgreSQL ---
    start = time.time()
    print(f"  Writing to PostgreSQL...", end=" ", flush=True)

    with dst_engine.begin() as conn:
        # Truncate if table has data (full replace)
        insp = inspect(dst_engine)
        if table_name in insp.get_table_names():
            # Disable FK checks temporarily for truncate
            if table_name in ("tickers",):
                # For parent tables, truncate children first
                for child in ("monthly_prices", "dividends"):
                    if child in insp.get_table_names():
                        conn.execute(text(f"TRUNCATE TABLE {child} CASCADE"))
            conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))

        # Bulk insert in batches of 1000
        batch_size = 1000
        table_obj = model_class.__table__
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            conn.execute(table_obj.insert(), batch)

        # Reset auto-increment sequence to max(id) + 1
        if "id" in sync_columns:
            max_id = max(r.get("id", 0) for r in rows) or 0
            seq_name = f"{table_name}_id_seq"
            try:
                conn.execute(text(f"SELECT setval('{seq_name}', {max_id}, true)"))
            except Exception:
                pass  # sequence might not exist for tables with non-serial PKs

    elapsed = time.time() - start
    print(f"wrote {len(rows):,} rows in {elapsed:.1f}s")

    # Verify
    final_count = get_row_count(dst_engine, table_name)
    match = "OK" if final_count == src_count else f"MISMATCH (expected {src_count})"
    print(f"  Verify: PostgreSQL now has {final_count:,} rows — {match}")

    return {
        "table": table_name,
        "status": "synced",
        "rows": len(rows),
        "seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync SQL Server data to Railway PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/sync_sql_to_postgres.py                  # Sync all data tables
  python tools/sync_sql_to_postgres.py --all            # Sync ALL tables (including logs)
  python tools/sync_sql_to_postgres.py --tables tickers monthly_prices
  python tools/sync_sql_to_postgres.py --dry-run        # Show what would happen
  python tools/sync_sql_to_postgres.py --status         # Compare row counts
        """,
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Specific table names to sync (default: core data tables only)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync ALL tables including logs (user_logins, api_request_logs, saved_simulations)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without writing anything",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show row counts on both databases and exit",
    )

    args = parser.parse_args()

    # Initialize database engines
    _init_engines()

    # --- Header ---
    print()
    print("=" * 60)
    print("  SQL Server  -->  PostgreSQL  Sync Tool")
    print("=" * 60)

    # --- Test connections ---
    print()
    print("Testing connections...")

    try:
        with src_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"  SQL Server:  Connected ({_DB_SERVER}/{_DB_NAME})")
    except Exception as e:
        print(f"  SQL Server:  FAILED — {e}")
        sys.exit(1)

    try:
        with dst_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # Mask password in URL for display
        display_url = POSTGRES_URL
        if "@" in display_url:
            pre = display_url.split("://")[0]
            post = display_url.split("@")[1]
            display_url = f"{pre}://***@{post}"
        print(f"  PostgreSQL:  Connected ({display_url})")
    except Exception as e:
        print(f"  PostgreSQL:  FAILED — {e}")
        sys.exit(1)

    # --- Create all tables in PostgreSQL (if not exist) ---
    print()
    print("Ensuring PostgreSQL tables exist...")
    Base.metadata.create_all(bind=dst_engine)
    insp = inspect(dst_engine)
    pg_tables = insp.get_table_names()
    print(f"  Tables in PostgreSQL: {', '.join(sorted(pg_tables))}")

    # --- Status mode ---
    if args.status:
        print()
        print(f"{'Table':<25} {'SQL Server':>12} {'PostgreSQL':>12} {'Match':>8}")
        print("-" * 60)
        for table_name, _ in ALL_TABLES:
            src = get_row_count(src_engine, table_name)
            dst = get_row_count(dst_engine, table_name)
            src_str = f"{src:,}" if src >= 0 else "N/A"
            dst_str = f"{dst:,}" if dst >= 0 else "N/A"
            match = "Yes" if src == dst else "NO"
            if src < 0 or dst < 0:
                match = "-"
            print(f"  {table_name:<23} {src_str:>12} {dst_str:>12} {match:>8}")
        print()
        return

    # --- Determine which tables to sync ---
    if args.tables:
        # User specified specific tables
        table_map = {name: cls for name, cls in ALL_TABLES}
        tables_to_sync = []
        for t in args.tables:
            if t not in table_map:
                print(f"ERROR: Unknown table '{t}'. Valid: {', '.join(table_map.keys())}")
                sys.exit(1)
            tables_to_sync.append((t, table_map[t]))
    elif args.all:
        tables_to_sync = ALL_TABLES
    else:
        tables_to_sync = DATA_TABLES

    table_names = [t[0] for t in tables_to_sync]
    print(f"\nTables to sync: {', '.join(table_names)}")

    if args.dry_run:
        print("MODE: Dry run (no writes)")

    # --- Sync each table ---
    results = []
    total_start = time.time()

    for table_name, model_class in tables_to_sync:
        result = sync_table(table_name, model_class, dry_run=args.dry_run)
        results.append(result)

    # --- Summary ---
    total_elapsed = time.time() - total_start
    print()
    print("=" * 60)
    print("  SYNC COMPLETE")
    print("=" * 60)
    total_rows = sum(r.get("rows", 0) for r in results)
    synced = sum(1 for r in results if r["status"] == "synced")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"  Tables synced:  {synced}")
    print(f"  Tables skipped: {skipped}")
    print(f"  Total rows:     {total_rows:,}")
    print(f"  Total time:     {total_elapsed:.1f}s")
    print()


if __name__ == "__main__":
    main()

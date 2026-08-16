"""
Loader: Shiller S&P 500 historical data

Source:  https://shillerdata.com/  -- the "U.S. Stock Markets 1871-Present and
         CAPE Ratio" link on that page downloads ie_data.xls.
File:    inputdata/ie_data.xls  (sheet: Data)   [inputdata/ is gitignored]
Target:  shiller_market_data table (SQL Server and/or PostgreSQL)

No API exists for this data -- the spreadsheet is downloaded by hand, which is
why this table is the one source Update All cannot refresh. It powers six
pages: Monte Carlo, S&P 500 History, the Historical Simulator, both extremes
pages, and downturns & recovery.

ROUTINE UPDATE (safe -- appends only, never touches existing history):
    venv\\Scripts\\python backend\\onetime\\load_shiller_data.py --append --db both

Other modes:
    ... --dry-run     parse and report, write nothing
    ... --db postgres target Railway only
    ... --truncate    delete all rows and reload from scratch. Only when
                      history is corrupt, or Shiller revised past months.

Requires: xlrd  (pip install xlrd)
"""

import os
import sys
import argparse
from datetime import date, datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate project root and load backend/.env before any other imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]   # backend/onetime/ -> root
ENV_FILE = PROJECT_ROOT / "backend" / ".env"

if ENV_FILE.exists():
    with open(ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Imports after env load
# ---------------------------------------------------------------------------
try:
    import xlrd
except ImportError:
    print("ERROR: xlrd not installed.  Run:  pip install xlrd")
    sys.exit(1)

from sqlalchemy import (
    Column, Integer, SmallInteger, Numeric, Date, DateTime,
    UniqueConstraint, text, create_engine, inspect as sa_inspect
)
from sqlalchemy.orm import declarative_base, Session

# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------
Base = declarative_base()


class ShillerMarketData(Base):
    """
    Monthly S&P 500 market data compiled by Robert Shiller (shillerdata.com).
    Source file: ie_data.xls, sheet 'Data'.  Covers Jan 1871 to present.

    DATA DICTIONARY
    ---------------
    DataDate               First day of the month this row represents (YYYY-MM-01)
    Year                   Calendar year (integer, for easy filtering)
    Month                  Calendar month 1-12 (integer, for easy filtering)
    SpPrice                S&P Composite nominal price (monthly average closing price)
    Dividend               S&P Composite dividend, 12-month trailing total, annualized
    Earnings               S&P Composite earnings, 12-month trailing total, annualized
    Cpi                    U.S. Consumer Price Index (all urban consumers, not seasonally adjusted)
    LongInterestRate       10-year U.S. Treasury yield (GS10), expressed as percent (e.g. 4.21 = 4.21%)
    RealPrice              S&P price adjusted to current dollars using CPI deflation
    RealDividend           Dividend adjusted to current dollars using CPI
    RealTotalReturnPrice   Cumulative real total return index — price + reinvested dividends,
                           both inflation-adjusted. Starts at 100 in Jan 1871. Large cumulative value.
    RealEarnings           Earnings adjusted to current dollars using CPI
    RealScaledEarnings     10-year average of real earnings — the denominator used to compute CAPE.
                           Large cumulative value following CPI growth.
    Cape                   Cyclically Adjusted Price/Earnings ratio (Shiller P/E10).
                           = RealPrice / RealScaledEarnings.
                           NULL for first ~10 years (insufficient earnings history).
    TrCape                 Total-Return CAPE — same concept using the total-return price series.
                           NULL for first ~10 years.
    ExcessCapeYield        Risk premium proxy: 1/CAPE minus real long-term bond yield.
                           Positive means equities appear cheap relative to bonds.
    MonthlyBondReturn      Monthly total return of the 10-year U.S. Treasury bond (price + coupon).
    RealBondReturn         Cumulative real total return of 10-year Treasury (inflation-adjusted).
                           Large cumulative value.
    TenYearStockRealReturn Annualized real stock return over the following 10 years (forward-looking).
                           NULL near the end of the series (future not yet known).
    TenYearBondRealReturn  Annualized real bond return over the following 10 years (forward-looking).
                           NULL near the end of the series.
    TenYearExcessRealReturn 10-year annualized excess real return = stocks minus bonds.
                           NULL near the end of the series.
    NominalTotalReturn     Monthly nominal total return (price gain + dividend income).
                           Formula: (P_t / P_t-1 - 1) + (D_t / 12) / P_t-1
                           Where P = SpPrice, D = Dividend (annualized, so /12 for monthly).
                           NULL for the first row (no prior price). Expressed as decimal
                           (e.g. 0.012 = 1.2% return that month). Calculated column —
                           not sourced from the Excel file.
    """
    __tablename__ = "shiller_market_data"

    Id                      = Column(Integer,       primary_key=True, autoincrement=True)
    DataDate                = Column(Date,          nullable=False)
    Year                    = Column(SmallInteger,  nullable=False)
    Month                   = Column(SmallInteger,  nullable=False)
    SpPrice                 = Column(Numeric(20, 8), nullable=True)
    Dividend                = Column(Numeric(20, 8), nullable=True)
    Earnings                = Column(Numeric(20, 8), nullable=True)
    Cpi                     = Column(Numeric(20, 8), nullable=True)
    LongInterestRate        = Column(Numeric(20, 8), nullable=True)
    RealPrice               = Column(Numeric(20, 8), nullable=True)
    RealDividend            = Column(Numeric(20, 8), nullable=True)
    RealTotalReturnPrice    = Column(Numeric(24, 8), nullable=True)   # large cumulative index
    RealEarnings            = Column(Numeric(20, 8), nullable=True)
    RealScaledEarnings      = Column(Numeric(24, 8), nullable=True)   # large cumulative value
    Cape                    = Column(Numeric(20, 8), nullable=True)
    TrCape                  = Column(Numeric(20, 8), nullable=True)
    ExcessCapeYield         = Column(Numeric(20, 8), nullable=True)
    MonthlyBondReturn       = Column(Numeric(20, 8), nullable=True)
    RealBondReturn          = Column(Numeric(20, 8), nullable=True)
    TenYearStockRealReturn  = Column(Numeric(20, 8), nullable=True)
    TenYearBondRealReturn   = Column(Numeric(20, 8), nullable=True)
    TenYearExcessRealReturn = Column(Numeric(20, 8), nullable=True)
    NominalTotalReturn      = Column(Numeric(20, 8), nullable=True)   # calculated, not from Excel
    CreatedAt               = Column(DateTime, nullable=False,
                                     default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("Year", "Month", name="uq_shiller_year_month"),
    )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_shiller_date(val):
    """
    Convert Shiller decimal date (e.g. 1871.01) to (year, month, date).
    Decimal format is YYYY.MM  — e.g. 2025.1 = Oct 2025, 2025.12 = Dec 2025.
    Returns None if val is not a valid date.
    """
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return None
    if fval < 1800 or fval > 2200:
        return None
    year = int(fval)
    month = round((fval - year) * 100)
    if month < 1 or month > 12:
        return None
    return year, month, date(year, month, 1)


def _to_decimal(val):
    """Return float or None — treats 'NA', '', and non-numeric as NULL."""
    if val is None or val == "" or val == "NA":
        return None
    try:
        result = float(val)
        return result if result == result else None   # NaN check
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Excel reader
# ---------------------------------------------------------------------------
# Column index mapping in ie_data.xls sheet 'Data' (0-based)
#   0  Date (decimal YYYY.MM)
#   1  SpPrice          - S&P Composite nominal price
#   2  Dividend         - Dividend (annualised)
#   3  Earnings         - Earnings (annualised)
#   4  CPI
#   5  DateFraction     - SKIP (just the decimal year fraction, not useful)
#   6  LongInterestRate - GS10 10-yr Treasury
#   7  RealPrice
#   8  RealDividend
#   9  RealTotalReturnPrice
#  10  RealEarnings
#  11  RealScaledEarnings
#  12  Cape (P/E10)
#  13  BLANK            - SKIP (empty separator column)
#  14  TrCape
#  15  BLANK            - SKIP (empty separator column)
#  16  ExcessCapeYield
#  17  MonthlyBondReturn
#  18  RealBondReturn
#  19  TenYearStockRealReturn
#  20  TenYearBondRealReturn
#  21  TenYearExcessRealReturn

def read_excel(file_path):
    """Read ie_data.xls and return a list of dicts ready for insert."""
    wb = xlrd.open_workbook(str(file_path))
    ws = wb.sheet_by_name("Data")

    print(f"  Sheet 'Data': {ws.nrows} rows × {ws.ncols} cols")

    records = []
    skipped_header  = 0
    skipped_footer  = 0
    skipped_nodate  = 0

    for i in range(ws.nrows):
        row = ws.row_values(i)

        # Skip the 8 header/title rows (rows 0-7)
        if i < 8:
            skipped_header += 1
            continue

        # Skip rows where the date cell is not a valid decimal year
        parsed = _parse_shiller_date(row[0])
        if parsed is None:
            skipped_footer += 1
            continue

        year, month, data_date = parsed

        records.append({
            "DataDate":                 data_date,
            "Year":                     year,
            "Month":                    month,
            "SpPrice":                  _to_decimal(row[1]),
            "Dividend":                 _to_decimal(row[2]),
            "Earnings":                 _to_decimal(row[3]),
            "Cpi":                      _to_decimal(row[4]),
            # row[5] DateFraction — skipped
            "LongInterestRate":         _to_decimal(row[6]),
            "RealPrice":                _to_decimal(row[7]),
            "RealDividend":             _to_decimal(row[8]),
            "RealTotalReturnPrice":     _to_decimal(row[9]),
            "RealEarnings":             _to_decimal(row[10]),
            "RealScaledEarnings":       _to_decimal(row[11]),
            "Cape":                     _to_decimal(row[12]),
            # row[13] blank — skipped
            "TrCape":                   _to_decimal(row[14]),
            # row[15] blank — skipped
            "ExcessCapeYield":          _to_decimal(row[16]),
            "MonthlyBondReturn":        _to_decimal(row[17]),
            "RealBondReturn":           _to_decimal(row[18]),
            "TenYearStockRealReturn":   _to_decimal(row[19]),
            "TenYearBondRealReturn":    _to_decimal(row[20]),
            "TenYearExcessRealReturn":  _to_decimal(row[21]),
        })

    print(f"  Skipped: {skipped_header} header rows, {skipped_footer} footer/note rows")
    print(f"  Data rows parsed: {len(records)}")

    # Calculate NominalTotalReturn = (P_t/P_t-1 - 1) + (D_t/12) / P_t-1
    # First row is always NULL — no prior price available
    null_count = 0
    for i, rec in enumerate(records):
        if i == 0:
            rec["NominalTotalReturn"] = None
            null_count += 1
            continue
        p_t  = rec["SpPrice"]
        p_t1 = records[i - 1]["SpPrice"]
        d_t  = rec["Dividend"]
        if p_t is not None and p_t1 is not None and p_t1 != 0 and d_t is not None:
            rec["NominalTotalReturn"] = (p_t / p_t1 - 1) + (d_t / 12) / p_t1
        else:
            rec["NominalTotalReturn"] = None
            null_count += 1
    print(f"  NominalTotalReturn computed ({len(records) - null_count} values, {null_count} NULL)")

    return records


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _build_engine(db_type):
    if db_type == "postgres":
        url = os.getenv("POSTGRES_URL", "")
        if not url:
            print("ERROR: POSTGRES_URL not set in backend/.env")
            sys.exit(1)
        return create_engine(url, echo=False)
    else:
        server   = os.getenv("DB_SERVER", "")
        database = os.getenv("DB_NAME", "REDACTED-DB-NAME")
        user     = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASSWORD", "")
        driver   = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        url = (f"mssql+pyodbc://{user}:{password}@{server}/{database}"
               f"?driver={driver.replace(' ', '+')}")
        return create_engine(url, echo=False)


def _add_column_if_missing(engine, col_name, col_ddl_pg, col_ddl_ss):
    """ALTER TABLE to add a column if it doesn't already exist."""
    dialect = engine.dialect.name
    insp = sa_inspect(engine)
    existing_cols = [c["name"] for c in insp.get_columns("shiller_market_data")]
    if col_name in existing_cols:
        return False   # already there
    print(f"  Column '{col_name}' not found — adding via ALTER TABLE...")
    ddl = col_ddl_pg if dialect == "postgresql" else col_ddl_ss
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print(f"  Column '{col_name}' added.")
    return True   # was missing, now added


def _max_ym_on_file(engine):
    """Newest (Year, Month) already loaded, as Year*100+Month. None if empty."""
    col_y, col_m = ('"Year"', '"Month"') if engine.dialect.name == "postgresql" else ("Year", "Month")
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT MAX({col_y} * 100 + {col_m}) FROM shiller_market_data")
        ).scalar()


def load_to_db(records, engine, truncate=False, dry_run=False, append=False):
    """Create table, then insert.

    append=True is the routine path: look at the newest (Year, Month) already
    on file and insert only the months after it. Settled history is never
    deleted, updated or re-read -- the same shape as the daily-price loaders.
    Shiller revises recent months occasionally; if you need those corrections
    rather than just new months, that is what --truncate is for.
    """
    dialect = engine.dialect.name

    # Create table if not exists
    Base.metadata.create_all(bind=engine)
    print(f"  Table 'shiller_market_data' ready ({dialect})")

    # Migrate: add NominalTotalReturn column if table existed before this feature
    col_added = _add_column_if_missing(
        engine,
        "NominalTotalReturn",
        'ALTER TABLE shiller_market_data ADD COLUMN "NominalTotalReturn" NUMERIC(20, 8) NULL',
        "ALTER TABLE shiller_market_data ADD NominalTotalReturn NUMERIC(20, 8) NULL",
    )

    # Check existing rows
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT COUNT(*) FROM shiller_market_data")
        ).scalar()
    print(f"  Existing rows: {existing:,}")

    # --- Append: keep only months newer than the newest on file ---
    if append and existing > 0 and not truncate:
        max_ym = _max_ym_on_file(engine)
        if max_ym is None:
            print("  Table is empty — appending everything")
        else:
            before = len(records)
            records = [r for r in records if r["Year"] * 100 + r["Month"] > max_ym]
            newest = f"{max_ym // 100}-{max_ym % 100:02d}"
            print(f"  Newest on file: {newest}")
            print(f"  New months in file: {len(records):,} (of {before:,} total)")
            if not records:
                print("  Already up to date — nothing to append.")
                return

    if dry_run:
        print(f"  DRY RUN: would insert/update {len(records):,} rows (skipping actual write)")
        return

    if truncate and existing > 0:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM shiller_market_data"))
        print(f"  Truncated {existing:,} existing rows")
        existing = 0

    if existing > 0 and not truncate and not append:
        if col_added:
            # Column was just added — update existing rows with computed values
            print(f"  Updating NominalTotalReturn for {existing:,} existing rows...")
            if dialect == "postgresql":
                update_sql = text(
                    'UPDATE shiller_market_data SET "NominalTotalReturn" = :val '
                    'WHERE "Year" = :year AND "Month" = :month'
                )
            else:
                update_sql = text(
                    "UPDATE shiller_market_data SET NominalTotalReturn = :val "
                    "WHERE Year = :year AND Month = :month"
                )
            with engine.begin() as conn:
                for rec in records:
                    conn.execute(update_sql, {
                        "val":   rec["NominalTotalReturn"],
                        "year":  rec["Year"],
                        "month": rec["Month"],
                    })
            print(f"  NominalTotalReturn updated for all rows.")
        else:
            print(f"  Table already has data. Use --truncate to reload. Skipping insert.")
        return

    # Bulk insert in batches
    BATCH = 500
    inserted = 0
    with Session(engine) as session:
        for start in range(0, len(records), BATCH):
            batch = records[start : start + BATCH]
            session.bulk_insert_mappings(ShillerMarketData, batch)
            inserted += len(batch)
            print(f"  Inserted {inserted:,}/{len(records):,}...", end="\r")
        session.commit()

    print(f"\n  Done — {inserted:,} rows inserted into shiller_market_data")

    # Reset sequence for PostgreSQL (sequence name uses PascalCase Id)
    if dialect == "postgresql":
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    'SELECT setval(\'shiller_market_data_"Id"_seq\', '
                    '(SELECT MAX("Id") FROM shiller_market_data), true)'
                ))
        except Exception:
            pass  # sequence already correct after bulk insert; non-fatal


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Load Shiller ie_data.xls into shiller_market_data table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load into SQL Server (uses DB_TYPE from .env, default sqlserver)
  venv\\Scripts\\python backend\\onetime\\load_shiller_data.py

  # Load into PostgreSQL
  venv\\Scripts\\python backend\\onetime\\load_shiller_data.py --db postgres

  # Load into both databases
  venv\\Scripts\\python backend\\onetime\\load_shiller_data.py --db both

  # Preview without writing
  venv\\Scripts\\python backend\\onetime\\load_shiller_data.py --dry-run

  # ROUTINE UPDATE -- append only the months not yet on file, both databases.
  # Never deletes or rewrites existing history.
  venv\\Scripts\\python backend\\onetime\\load_shiller_data.py --append --db both

  # Reload from scratch (drops existing rows first). Only if history is
  # corrupt, or Shiller revised past months and you want those corrections.
  venv\\Scripts\\python backend\\onetime\\load_shiller_data.py --truncate
        """
    )
    parser.add_argument(
        "--db",
        choices=["sqlserver", "postgres", "both"],
        default=os.getenv("DB_TYPE", "sqlserver").strip().lower(),
        help="Target database (default: DB_TYPE from .env)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse the file and show counts without writing to DB"
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Insert only months newer than the newest on file. Never deletes or "
             "updates existing rows -- the routine way to bring Shiller current."
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Delete existing rows before inserting (full reload). Only needed if "
             "history is corrupt or Shiller revised past months."
    )
    parser.add_argument(
        "--file",
        default=str(PROJECT_ROOT / "inputdata" / "ie_data.xls"),
        help="Path to ie_data.xls (default: inputdata/ie_data.xls)"
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Shiller Data Loader")
    print("=" * 60)
    print(f"  File:     {file_path}")
    print(f"  Target:   {args.db}")
    print(f"  Mode:     {'append' if args.append else ('truncate+reload' if args.truncate else 'insert-if-empty')}")
    print(f"  Dry run:  {args.dry_run}")
    print()

    # Read Excel
    print("Reading Excel file...")
    records = read_excel(file_path)
    print()

    if args.dry_run:
        print("DRY RUN — sample of first 3 records:")
        for r in records[:3]:
            print(" ", r)
        print()

    # Determine which DBs to load
    targets = []
    if args.db == "both":
        targets = ["sqlserver", "postgres"]
    else:
        targets = [args.db]

    for db_type in targets:
        print(f"--- Loading into {db_type} ---")
        engine = _build_engine(db_type)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"  Connected to {db_type}")
        except Exception as e:
            print(f"  FAILED to connect to {db_type}: {e}")
            continue
        load_to_db(records, engine, truncate=args.truncate, dry_run=args.dry_run, append=args.append)
        print()

    print("=" * 60)
    print("  Complete")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()

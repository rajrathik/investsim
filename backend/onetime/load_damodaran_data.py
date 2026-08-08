"""
One-time loader: Damodaran annual asset-class returns (Aswath Damodaran, NYU Stern)
Source:  https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html
File:    inputdata/damodaran_annual_returns.csv
Target:  damodaran_annual_returns table (SQL Server and/or PostgreSQL)

Run from the project root:
    venv\\Scripts\\python backend\\onetime\\load_damodaran_data.py
    venv\\Scripts\\python backend\\onetime\\load_damodaran_data.py --db postgres
    venv\\Scripts\\python backend\\onetime\\load_damodaran_data.py --db sqlserver
    venv\\Scripts\\python backend\\onetime\\load_damodaran_data.py --dry-run
    venv\\Scripts\\python backend\\onetime\\load_damodaran_data.py --truncate
"""

import os
import sys
import csv
import argparse
from datetime import datetime, timezone
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

from sqlalchemy import (
    Column, Integer, SmallInteger, Numeric, String, DateTime,
    UniqueConstraint, text, create_engine
)
from sqlalchemy.orm import declarative_base, Session

# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------
Base = declarative_base()

SOURCE_LABEL = "Damodaran (NYU Stern)"
SOURCE_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html"


class DamodaranAnnualReturn(Base):
    """
    Annual U.S. asset-class returns compiled by Aswath Damodaran (NYU Stern).
    Source: histretSP.xls / histretSP.html. Covers 1928 to present.

    All return columns are decimal fractions (e.g. 0.4381 = 43.81%), consistent
    with the NominalTotalReturn convention used in shiller_market_data.

    DATA DICTIONARY
    ----------------
    Year               Calendar year
    SP500Return        S&P 500 annual return, including dividends
    SmallCapReturn     US small cap (bottom decile) annual return
    TBill3Month        3-month Treasury Bill annual return (average rate during the year)
    TBond10Year        10-year US Treasury Bond annual return
    BaaCorporateBond   Baa-rated corporate bond annual return
    RealEstate         Real estate annual return
    Gold               Gold annual return
    Source             Attribution label — always "Damodaran (NYU Stern)"
    SourceUrl           Page the data was pulled from
    """
    __tablename__ = "damodaran_annual_returns"

    Id                = Column(Integer,      primary_key=True, autoincrement=True)
    Year              = Column(SmallInteger, nullable=False)
    SP500Return       = Column(Numeric(12, 6), nullable=True)
    SmallCapReturn    = Column(Numeric(12, 6), nullable=True)
    TBill3Month       = Column(Numeric(12, 6), nullable=True)
    TBond10Year       = Column(Numeric(12, 6), nullable=True)
    BaaCorporateBond  = Column(Numeric(12, 6), nullable=True)
    RealEstate        = Column(Numeric(12, 6), nullable=True)
    Gold              = Column(Numeric(12, 6), nullable=True)
    Source            = Column(String(100), nullable=False, default=SOURCE_LABEL)
    SourceUrl         = Column(String(500), nullable=False, default=SOURCE_URL)
    CreatedAt         = Column(DateTime, nullable=False,
                                default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("Year", name="uq_damodaran_year"),
    )


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------
def read_csv(file_path):
    """Read damodaran_annual_returns.csv and return a list of dicts ready for insert.

    CSV values are plain percentages (e.g. 43.81 = 43.81%); converted here to
    decimal fractions (0.4381) to match project convention.
    """
    records = []
    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "Year":              int(row["Year"]),
                "SP500Return":       float(row["SP500"]) / 100,
                "SmallCapReturn":    float(row["SmallCap"]) / 100,
                "TBill3Month":       float(row["TBill3Mo"]) / 100,
                "TBond10Year":       float(row["TBond10Yr"]) / 100,
                "BaaCorporateBond":  float(row["BaaCorpBond"]) / 100,
                "RealEstate":        float(row["RealEstate"]) / 100,
                "Gold":              float(row["Gold"]) / 100,
                "Source":            SOURCE_LABEL,
                "SourceUrl":         SOURCE_URL,
            })
    print(f"  Parsed {len(records)} rows from {file_path.name} "
          f"({records[0]['Year']}-{records[-1]['Year']})")
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


def load_to_db(records, engine, truncate=False, dry_run=False):
    """Create table, optionally truncate, then bulk insert."""
    dialect = engine.dialect.name

    Base.metadata.create_all(bind=engine)
    print(f"  Table 'damodaran_annual_returns' ready ({dialect})")

    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT COUNT(*) FROM damodaran_annual_returns")
        ).scalar()
    print(f"  Existing rows: {existing:,}")

    if dry_run:
        print(f"  DRY RUN: would insert {len(records):,} rows (skipping actual write)")
        return

    if truncate and existing > 0:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM damodaran_annual_returns"))
        print(f"  Truncated {existing:,} existing rows")
        existing = 0

    if existing > 0 and not truncate:
        print("  Table already has data. Use --truncate to reload. Skipping insert.")
        return

    with Session(engine) as session:
        session.bulk_insert_mappings(DamodaranAnnualReturn, records)
        session.commit()
    print(f"  Done — {len(records):,} rows inserted into damodaran_annual_returns")

    if dialect == "postgresql":
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    'SELECT setval(\'damodaran_annual_returns_"Id"_seq\', '
                    '(SELECT MAX("Id") FROM damodaran_annual_returns), true)'
                ))
        except Exception:
            pass  # non-fatal


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Load damodaran_annual_returns.csv into damodaran_annual_returns table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db", choices=["sqlserver", "postgres", "both"],
        default=os.getenv("DB_TYPE", "sqlserver").strip().lower(),
        help="Target database (default: DB_TYPE from .env)"
    )
    parser.add_argument("--dry-run", action="store_true",
                         help="Parse the file and show counts without writing to DB")
    parser.add_argument("--truncate", action="store_true",
                         help="Delete existing rows before inserting (full reload)")
    parser.add_argument(
        "--file",
        default=str(PROJECT_ROOT / "inputdata" / "damodaran_annual_returns.csv"),
        help="Path to damodaran_annual_returns.csv"
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Damodaran Annual Returns Loader")
    print(f"  Source: {SOURCE_URL}")
    print("=" * 60)
    print(f"  File:     {file_path}")
    print(f"  Target:   {args.db}")
    print(f"  Truncate: {args.truncate}")
    print(f"  Dry run:  {args.dry_run}")
    print()

    print("Reading CSV file...")
    records = read_csv(file_path)
    print()

    if args.dry_run:
        print("DRY RUN — sample of first 3 records:")
        for r in records[:3]:
            print(" ", r)
        print()

    targets = ["sqlserver", "postgres"] if args.db == "both" else [args.db]

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
        load_to_db(records, engine, truncate=args.truncate, dry_run=args.dry_run)
        print()

    print("=" * 60)
    print("  Complete")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()

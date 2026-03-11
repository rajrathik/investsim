"""
One-time seeder: Stack & Earn tiered interest rate tables.
Creates and populates stack_earn_savings_tiers and stack_earn_goal_tiers.

Run from the project root:
    venv\\Scripts\\python backend\\onetime\\seed_stack_earn_tiers.py --db sqlserver
    venv\\Scripts\\python backend\\onetime\\seed_stack_earn_tiers.py --db postgres
    venv\\Scripts\\python backend\\onetime\\seed_stack_earn_tiers.py --db both
    venv\\Scripts\\python backend\\onetime\\seed_stack_earn_tiers.py --db both --truncate
    venv\\Scripts\\python backend\\onetime\\seed_stack_earn_tiers.py --dry-run
"""

import os
import sys
import argparse
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
from sqlalchemy import Column, Integer, String, Float, text, create_engine
from sqlalchemy.orm import declarative_base, Session

# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------
Base = declarative_base()


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
# Tier seed data  (change these values here to re-seed)
# ---------------------------------------------------------------------------
TIERS = [
    {"tier_number": 1, "tier_label": "Tier 1", "min_amount": 0.0,    "max_amount": 1000.0,  "annual_rate": 0.0500},
    {"tier_number": 2, "tier_label": "Tier 2", "min_amount": 1000.0, "max_amount": 10000.0, "annual_rate": 0.0300},
    {"tier_number": 3, "tier_label": "Tier 3", "min_amount": 10000.0,"max_amount": None,     "annual_rate": 0.0100},
]

# ---------------------------------------------------------------------------
# Engine builders
# ---------------------------------------------------------------------------

def build_sqlserver_engine():
    server   = os.environ.get("DB_SERVER", "localhost")
    database = os.environ.get("DB_NAME", "PortfolioSimulator")
    user     = os.environ.get("DB_USER", "")
    password = os.environ.get("DB_PASSWORD", "")
    if user and password:
        url = f"mssql+pyodbc://{user}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
    else:
        url = f"mssql+pyodbc://{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
    return create_engine(url, echo=False)


def build_postgres_engine():
    url = os.environ.get("POSTGRES_URL")
    if not url:
        print("ERROR: POSTGRES_URL not set in backend/.env")
        sys.exit(1)
    return create_engine(url, echo=False)


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

def seed(engine, truncate: bool, dry_run: bool):
    dialect = engine.dialect.name
    print(f"\n[{dialect.upper()}] Connecting...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[{dialect.upper()}] Connection OK")
    except Exception as exc:
        print(f"[{dialect.upper()}] Connection FAILED: {exc}")
        return

    # Create tables if they don't exist
    Base.metadata.create_all(engine)
    print(f"[{dialect.upper()}] Tables created / verified")

    if dry_run:
        print(f"[{dialect.upper()}] DRY RUN — no data written")
        return

    with Session(engine) as session:
        for model_cls, label in [(StackEarnSavingsTier, "savings"), (StackEarnGoalTier, "goal")]:
            if truncate:
                session.query(model_cls).delete()
                session.commit()
                print(f"[{dialect.upper()}] Truncated {model_cls.__tablename__}")

            existing = session.query(model_cls).count()
            if existing > 0 and not truncate:
                print(f"[{dialect.upper()}] {model_cls.__tablename__} already has {existing} rows — skipping (use --truncate to re-seed)")
                continue

            for t in TIERS:
                session.merge(model_cls(**t))
            session.commit()
            print(f"[{dialect.upper()}] Seeded {len(TIERS)} rows into {model_cls.__tablename__}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed Stack & Earn tier tables")
    parser.add_argument("--db", choices=["sqlserver", "postgres", "both"], default="sqlserver")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows before seeding")
    parser.add_argument("--dry-run", action="store_true", help="Create tables but don't insert data")
    args = parser.parse_args()

    if args.db in ("sqlserver", "both"):
        seed(build_sqlserver_engine(), truncate=args.truncate, dry_run=args.dry_run)

    if args.db in ("postgres", "both"):
        seed(build_postgres_engine(), truncate=args.truncate, dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()

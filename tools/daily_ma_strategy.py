"""Standalone technical-analysis experiment: 50/100/200-day moving averages
and a simple MA-crossover strategy backtest.

Isolated on purpose -- reads ONLY spy_daily_prices / oef_daily_prices,
straight SQL, no import from backend/app/ and no writes to the database.
Not wired into the API or admin.html; run it directly when you want to
look at the numbers.

Usage:
    venv\\Scripts\\python tools\\daily_ma_strategy.py --ticker SPY
    venv\\Scripts\\python tools\\daily_ma_strategy.py --ticker OEF
    venv\\Scripts\\python tools\\daily_ma_strategy.py --ticker SPY --save-csv
"""
import os
import argparse
import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Load .env (same pattern as tools/sync_sql_to_postgres.py)
# ---------------------------------------------------------------------------
_env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

DB_TYPE = os.getenv("DB_TYPE", "postgres").strip().lower()
if DB_TYPE == "sqlserver":
    _server = os.getenv("DB_SERVER", "")
    _name = os.getenv("DB_NAME", "")
    _user = os.getenv("DB_USER", "")
    _password = os.getenv("DB_PASSWORD", "")
    _driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    DATABASE_URL = f"mssql+pyodbc://{_user}:{_password}@{_server}/{_name}?driver={_driver.replace(' ', '+')}"
else:
    DATABASE_URL = os.getenv("POSTGRES_URL", "")

TABLES = {"SPY": "spy_daily_prices", "OEF": "oef_daily_prices"}


def load_prices(ticker: str) -> pd.DataFrame:
    """Read price_date + close straight from the ticker's daily-prices table. Nothing else."""
    if ticker not in TABLES:
        raise ValueError(f"Unknown ticker '{ticker}'. Available: {', '.join(TABLES)}")
    engine = create_engine(DATABASE_URL)
    table = TABLES[ticker]
    query = text(f"SELECT price_date, close FROM {table} WHERE ticker = :tk ORDER BY price_date")
    df = pd.read_sql(query, engine, params={"tk": ticker})
    df["price_date"] = pd.to_datetime(df["price_date"])
    df = df.set_index("price_date")
    return df


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma100"] = df["close"].rolling(100).mean()
    df["sma200"] = df["close"].rolling(200).mean()
    return df


def find_crossovers(df: pd.DataFrame) -> pd.DataFrame:
    """Golden Cross (sma50 crosses above sma200) / Death Cross (sma50 crosses below sma200)."""
    df = df.copy()
    df["regime"] = df["sma50"] > df["sma200"]
    df["cross"] = df["regime"].astype(int).diff()
    crosses = df[df["cross"].notna() & (df["cross"] != 0)].copy()
    crosses["signal"] = crosses["cross"].map({1: "GOLDEN CROSS (bullish)", -1: "DEATH CROSS (bearish)"})
    return crosses[["close", "sma50", "sma200", "signal"]]


def backtest_ma_crossover(df: pd.DataFrame, starting_value: float = 10000.0) -> dict:
    """Regime strategy: long when sma50 > sma200 (yesterday's signal), cash otherwise.
    Compared against buy-and-hold over the same window (from the first date
    sma200 is available -- i.e. once there's 200 days of history to average).
    """
    d = df.dropna(subset=["sma200"]).copy()
    if d.empty or len(d) < 2:
        return {"error": "Not enough history for a 200-day SMA yet."}

    d["daily_return"] = d["close"].pct_change().fillna(0)
    d["in_market"] = d["sma50"].shift(1) > d["sma200"].shift(1)  # act on yesterday's signal, not today's
    d["strategy_return"] = d["daily_return"] * d["in_market"]

    strategy_growth = (1 + d["strategy_return"]).cumprod()
    buyhold_growth = (1 + d["daily_return"]).cumprod()

    years = (d.index[-1] - d.index[0]).days / 365.25
    strategy_cagr = strategy_growth.iloc[-1] ** (1 / years) - 1 if years > 0 else 0
    buyhold_cagr = buyhold_growth.iloc[-1] ** (1 / years) - 1 if years > 0 else 0

    return {
        "window": f"{d.index[0].date()} to {d.index[-1].date()} ({years:.1f} years)",
        "starting_value": starting_value,
        "strategy_final_value": round(starting_value * strategy_growth.iloc[-1], 2),
        "strategy_cagr_pct": round(strategy_cagr * 100, 2),
        "buy_hold_final_value": round(starting_value * buyhold_growth.iloc[-1], 2),
        "buy_hold_cagr_pct": round(buyhold_cagr * 100, 2),
        "pct_days_in_market": round(d["in_market"].mean() * 100, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="MA(50/100/200) crossover analysis for SPY/OEF daily tables")
    parser.add_argument("--ticker", required=True, choices=["SPY", "OEF"])
    parser.add_argument("--save-csv", action="store_true", help="Save full daily series with MAs to tools/<ticker>_ma_analysis.csv")
    args = parser.parse_args()

    print(f"Loading {args.ticker} from {TABLES[args.ticker]}...")
    df = load_prices(args.ticker)
    print(f"{len(df)} rows, {df.index.min().date()} to {df.index.max().date()}")

    df = add_moving_averages(df)
    latest = df.iloc[-1]

    print(f"\n--- Latest ({df.index[-1].date()}) ---")
    print(f"Close:  {latest['close']:.2f}")
    print(f"SMA50:  {latest['sma50']:.2f}" if pd.notna(latest["sma50"]) else "SMA50:  n/a (not enough history)")
    print(f"SMA100: {latest['sma100']:.2f}" if pd.notna(latest["sma100"]) else "SMA100: n/a (not enough history)")
    print(f"SMA200: {latest['sma200']:.2f}" if pd.notna(latest["sma200"]) else "SMA200: n/a (not enough history)")

    if pd.notna(latest["sma50"]) and pd.notna(latest["sma200"]):
        regime = "BULLISH (SMA50 > SMA200)" if latest["sma50"] > latest["sma200"] else "BEARISH (SMA50 < SMA200)"
        print(f"Current regime: {regime}")

    print("\n--- Golden Cross / Death Cross history ---")
    crosses = find_crossovers(df)
    if crosses.empty:
        print("No crossovers found in this history yet.")
    else:
        for dt, row in crosses.iterrows():
            print(f"{dt.date()}  {row['signal']:<22} close={row['close']:.2f}  sma50={row['sma50']:.2f}  sma200={row['sma200']:.2f}")

    print("\n--- Backtest: SMA50/200 crossover regime vs Buy & Hold ($10,000 start) ---")
    bt = backtest_ma_crossover(df)
    for k, v in bt.items():
        print(f"{k}: {v}")

    if args.save_csv:
        out_path = os.path.join(os.path.dirname(__file__), f"{args.ticker.lower()}_ma_analysis.csv")
        df.to_csv(out_path)
        print(f"\nSaved full daily series to {out_path}")


if __name__ == "__main__":
    main()

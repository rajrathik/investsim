# How to Use the Test Spreadsheet

## Quick Start

1. Open `spreadsheet_config.txt` in Notepad
2. Change tickers, amount, years, or tax rate
3. Run: `python tools/generate_test_spreadsheet.py`
4. Open `Portfolio_Simulator_Test.xlsx` in Excel

---

## The 5 Sheets (left to right)

### Sheet 1: Setup (your inputs + raw data)

| Row | What's there |
|-----|-------------|
| Rows 3-6 | **Your inputs** (yellow cells): monthly amount, years, tax rate |
| Row 8 | Ticker table: which tickers, what % allocation |
| Row 12+ | **Raw data from database** — one row per month: MM rate, high price, close price, dividend per ticker |

**This is the source of truth.** Every other sheet pulls from here.

> Try it: change the Monthly Investment in cell B3 from $1,000 to $2,000. Watch all other sheets update.

---

### Sheet 2: Monthly Simulation (the engine)

One row per month. This is where the math happens.

| Column | What it calculates | How |
|--------|-------------------|-----|
| Month | Same as Setup | |
| MM Rate | Fed funds rate that month | From Setup |
| Prior Div Bal | Dividend cash balance carried from last month | Previous row's "Div Bal End" |
| MM Interest | Interest earned on cash | Prior Div Bal x MM Rate / 12 |
| Div Bal After Interest | Cash after interest | Prior Div Bal + MM Interest |
| Month Budget | Investable amount this month | Monthly Amount (flat — no aggregate carryover) |
| **Per ticker:** | | |
| Accum In | Unspent $ carried from last month for this ticker | Previous row's "Accum Out" |
| Allocated | Dollars earmarked for this ticker this month | Month Budget x Allocation % |
| Accum Bal | Total available to buy shares | Accum In + Allocated |
| Shares | Whole shares bought (round lot) | INT(Accum Bal / High Price) |
| Spent | Actual dollars used | Shares x High Price |
| Accum Out | Remainder stays in this ticker's bucket | Accum Bal - Spent |
| Cum Shares | Total shares you own | Last month's Cum Shares + Shares |
| Dividends | Cash dividend received | Cum Shares x Dividend per Share |
| Value | What your shares are worth | Cum Shares x Close Price |
| **Totals:** | | |
| Total Shares | Running total of all shares held | Sum of all ticker Cum Shares |
| Monthly Divs | All dividends this month | Sum of all ticker dividends |
| Div Bal End | Cash balance end of month | Div Bal After Interest + Monthly Divs |
| Total Invested | Cumulative actual $ spent | Running sum of Spent (not Allocated) |
| Equity Value | Stock value | Sum of all ticker Values |
| MM-Only Bal | What if you put everything in money market? | Grows with interest each month |

> Try it: click any green formula cell. Excel shows you the exact calculation in the formula bar.

---

### Sheet 3: Year Summary

Rolls up Monthly Simulation into one row per year.

| Column | Where it comes from |
|--------|-------------------|
| Year Invested | Sum of that year's monthly investments |
| Cum Invested | Running total across all years |
| Dividends | Sum of dividends received that year |
| MM Interest | Sum of interest earned that year |
| End Stock Value | December's stock value (shares x close price) |
| End Div Balance | December's cash balance |
| End Portfolio Value | Stock Value + Div Balance |

---

### Sheet 4: Tax Impact

One row per year. Shows taxes owed.

| Column | Formula |
|--------|--------|
| Dividends | From Year Summary |
| Tax on Dividends | Dividends x Tax Rate |
| MM Interest | From Year Summary |
| Tax on Interest | MM Interest x Tax Rate |
| Total Taxes | Tax on Dividends + Tax on Interest |

> Try it: change the Tax Rate on the Setup sheet (cell B5). All tax numbers update instantly.

---

### Sheet 5: Annual Returns

One summary row per year + calculation detail rows underneath.

**Summary row:**

| Column | What it means |
|--------|--------------|
| Invested | Dollars put in that year |
| Dividends | Cash dividends that year |
| MM Interest | Interest earned that year |
| Stock Value | End-of-year shares value |
| Portfolio Value | Stock Value + Div Balance |
| Pre-Tax Return % | How well you did before taxes |

**Detail rows** (italicized, below each year) show exactly how return is computed:

```
Stock Gain         = End Stock Value - Beginning Stock Value - Invested
Avg Invested Capital = Invested x 0.542   (assumes money goes in mid-year on average)
Base Capital       = Beginning Stock Value + Avg Invested Capital

Pre-Tax Return     = (Stock Gain + Dividends + MM Interest) / Base Capital
```

---

## How to Compare with the Website

1. Run the website with the **same** tickers, allocations, amount, years, and tax rate
2. Open the spreadsheet side-by-side
3. Check these numbers match:

| Website | Spreadsheet |
|---------|------------|
| Summary tiles (Total Invested, Portfolio Value, etc.) | Year Summary sheet, last row |
| Monthly table rows | Monthly Simulation sheet |
| Tax Impact table | Tax Impact sheet |
| Annual Return table | Annual Returns sheet, summary rows |
| Click any cell on website for calculation popup | Annual Returns sheet, detail rows |

---

## Key Concepts

- **Buys at monthly high price** — worst case scenario (conservative)
- **Integer shares only (round lots)** — you buy whole shares: INT(accumulated / price). No fractional shares.
- **Per-ticker accumulation** — each ticker keeps its own bucket of unspent dollars. When allocation can't buy a share, the money stays in that ticker's bucket until it accumulates enough. No money crosses between tickers.
- **Simulation stops at prior year-end** — runs through December of last complete calendar year, never into the current partial year
- **Dividends are NOT reinvested** — they sit in a cash account earning money market interest
- **0.542 multiplier** — since you invest monthly, on average your money was invested for about half the year (DCA mid-year approximation)
- **All cells are formulas** — change any input on Setup, everything recalculates

"""Damodaran annual asset-class returns fetcher.

Fetches the annual returns table published by Aswath Damodaran (NYU Stern)
and parses it into records ready for upsert into damodaran_annual_returns.

Source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html
"""
import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DAMODARAN_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html"
SOURCE_LABEL = "Damodaran (NYU Stern)"


class DamodaranFetchError(Exception):
    """Raised when the Damodaran page can't be fetched or parsed."""
    pass


def _parse_pct(cell_text: str):
    """Convert '43.81%' -> 0.4381 (decimal fraction). None if not parseable."""
    if cell_text is None:
        return None
    t = cell_text.strip().replace("%", "").replace(",", "")
    if not t:
        return None
    try:
        return float(t) / 100
    except ValueError:
        return None


def fetch_damodaran_returns() -> list[dict]:
    """Fetch and parse the annual returns table from Damodaran's page.

    Each row on the page has: Year, then 7 return % columns (S&P 500,
    Small Cap, 3-mo T.Bill, 10-yr T.Bond, Baa Corp Bond, Real Estate, Gold),
    followed by cumulative $ value columns (ignored here).

    Returns a list of dicts sorted by Year ascending, keys:
      Year, SP500Return, SmallCapReturn, TBill3Month, TBond10Year,
      BaaCorporateBond, RealEstate, Gold
    """
    try:
        resp = requests.get(
            DAMODARAN_URL,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PortfolioSimulator/1.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise DamodaranFetchError(f"Failed to fetch Damodaran page: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise DamodaranFetchError("No <table> found on Damodaran page — layout may have changed.")

    records = []
    for table in tables:
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 8:
                continue

            year_text = cells[0].get_text(strip=True)
            if not re.match(r"^(19|20)\d{2}$", year_text):
                continue  # skip header/footer/non-data rows

            sp500 = _parse_pct(cells[1].get_text())
            if sp500 is None:
                continue  # need at least the core return value

            records.append({
                "Year": int(year_text),
                "SP500Return": sp500,
                "SmallCapReturn": _parse_pct(cells[2].get_text()),
                "TBill3Month": _parse_pct(cells[3].get_text()),
                "TBond10Year": _parse_pct(cells[4].get_text()),
                "BaaCorporateBond": _parse_pct(cells[5].get_text()),
                "RealEstate": _parse_pct(cells[6].get_text()),
                "Gold": _parse_pct(cells[7].get_text()),
            })

    if not records:
        raise DamodaranFetchError("Parsed 0 rows from Damodaran page — layout may have changed.")

    # De-dupe by year (keep last occurrence in document order), sort ascending
    dedup = {r["Year"]: r for r in records}
    result = sorted(dedup.values(), key=lambda r: r["Year"])
    logger.info(
        f"Fetched {len(result)} Damodaran annual return rows "
        f"({result[0]['Year']}-{result[-1]['Year']})"
    )
    return result

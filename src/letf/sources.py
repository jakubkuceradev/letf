"""Download and cache every external data source.

Each function returns a pandas object and caches the raw download under
``data/raw``. A cached file is never refetched unless ``refresh=True``.
"""

import io

import pandas as pd
import requests
import yfinance as yf

from letf.paths import RAW

_UA = {"User-Agent": "Mozilla/5.0 (letf-research)"}
SHILLER_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
PROSHARES_NAV_URL = "https://accounts.profunds.com/etfdata/ByFund/{ticker}-historical_nav.csv"


def _cached_bytes(name: str, url: str, refresh: bool, headers: dict | None = _UA) -> bytes:
    path = RAW / name
    if path.exists() and not refresh:
        return path.read_bytes()
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return resp.content


def fred(series: str, refresh: bool = False) -> pd.Series:
    """A FRED series indexed by observation date."""
    # FRED stalls on browser-like user agents; the default requests agent works.
    raw = _cached_bytes(f"fred_{series}.csv", FRED_URL.format(series=series), refresh, None)
    df = pd.read_csv(io.BytesIO(raw), parse_dates=["observation_date"], na_values=["."])
    return df.set_index("observation_date")[series].astype(float).dropna()


def shiller(refresh: bool = False) -> pd.DataFrame:
    """Shiller monthly data: index level P and annualized dividend D, by month start."""
    raw = _cached_bytes("shiller_ie_data.xls", SHILLER_URL, refresh)
    df = pd.read_excel(io.BytesIO(raw), "Data", header=None, skiprows=8, usecols=[0, 1, 2])
    df.columns = ["date", "P", "D"]
    df = df[pd.to_numeric(df["date"], errors="coerce").notna()].copy()
    code = df["date"].astype(float)
    year = code.astype(int)
    month = ((code - year) * 100).round().astype(int)
    df.index = pd.to_datetime(pd.DataFrame({"year": year, "month": month, "day": 1}))
    return df[["P", "D"]].apply(pd.to_numeric, errors="coerce")


def yahoo(ticker: str, refresh: bool = False) -> pd.DataFrame:
    """Daily Yahoo history (unadjusted Close, Adj Close, Dividends), tz-naive index."""
    path = RAW / f"yahoo_{ticker.replace('^', '_')}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    hist = yf.Ticker(ticker).history(period="max", auto_adjust=False, actions=True)
    if hist.empty:
        raise RuntimeError(f"Yahoo returned no data for {ticker}")
    hist.index = hist.index.tz_localize(None).normalize()
    keep = [c for c in ["Close", "Adj Close", "Dividends", "Stock Splits"] if c in hist]
    hist = hist[keep]
    RAW.mkdir(parents=True, exist_ok=True)
    hist.to_parquet(path)
    return hist


def proshares_nav(ticker: str, refresh: bool = False) -> pd.Series:
    """ProShares daily NAV history (split-adjusted, excludes distributions)."""
    url = PROSHARES_NAV_URL.format(ticker=ticker)
    raw = _cached_bytes(f"proshares_{ticker}_nav.csv", url, refresh)
    df = pd.read_csv(io.BytesIO(raw))
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    return df.set_index("Date")["NAV"].astype(float).sort_index()

#!/usr/bin/env python3
"""
Fetch daily market data for the KKS console and write data/history.json.

What it covers (6 pages; the Screener page was removed from the site):
  - Debrief tape: 8 index/factor ETFs (SPY, QQQ, IWM, DIA, RSP, QQQE,
    SPMO, TLT) — 1D %, 1M % vs RSP, 50D ATR index.
  - Breadth: computed from S&P 500 constituents (Wikipedia list, fetched
    live). Daily +-4% up/down, 5D/10D up-down ratios, Quarter +-25%,
    Month +-25%, Month +-50%, 34-session +-13%, Above-40D %, SPX close.
  - Market Strength: 8 index cards + Market segments (9), Equal-weight
    sectors (11) and SPDR sectors (11) — RS 1M %, RS Thrust %, 50D ATR
    index, RS vs RSP, Intraday, 1D, 1M, Off-52W-High; plus 1W % and
    1W RS vs RSP (trailing 5 sessions).
  - Industry Group Strength: all 173 industry/thematic ETFs in IND_LIST,
    same columns as Market Strength. Weekly OHLC candles for the same
    173 ETFs (last 12 weeks, derived from the daily bars already
    fetched in the run) are written to data/industry_weekly.json.
  - Positioning: 10 COT markets from the CFTC legacy futures-only file
    (deafut.txt). Large specs = Noncommercial, Commercials = Commercial,
    Small specs = Nonreportable. Percentiles are the rank of each
    group's current net position in the net-position series stored in
    history.json (5-year lookback, accumulating as the workflow runs;
    50.0 until at least 2 observations exist). Never invent a COT value
    for a week with no release: if the CFTC file cannot be fetched, or
    its report date is unchanged, the last published positioning is
    carried forward unchanged.
  - Liquid Leadership: leaders from the S&P 500 + Nasdaq-100
    constituents, filtered to avg dollar volume > $100M and avg shares
    > 1M (21-session means), top 2% by 1M return, with 1M return %,
    extension vs 50D SMA (in 50D ATR multiples), avg $ vol, avg shares
    and ADR %; plus a group-leadership summary by GICS sub-industry.
  - RS Screener: one row per stock in the liquid universe (all
    US-listed common stocks with 30-session mean dollar volume
    > $50M, re-screened weekly) for the latest close — 1D/1M/3M/6M
    returns, RS 1M % vs RSP, RS
    percentile (0-100), O'Neil RS Rating (1-99), extension vs 50D
    SMA, ADR %, avg dollar volume, above 50D/200D, off 52W high and
    9D/9W/9M EMA position. Written to data/rs.json (single latest
    session, not a history list). Needs ~2 years of constituent
    closes, so constituents are fetched with period="2y".

Sources (all free / public):
  - Yahoo Finance via yfinance: daily OHLCV. Yahoo has no official
    public API; yfinance scrapes its chart endpoints, so treat this as
    best-effort. Stooq daily CSV is the fallback for ETF tickers.
  - Wikipedia (List of S&P 500 companies / NASDAQ-100): constituent
    lists with GICS sector and sub-industry. Parsed with the stdlib
    HTML parser — no extra dependency.
  - CFTC Commitments of Traders, legacy futures-only file:
    https://www.cftc.gov/dea/newcot/deafut.txt (weekly, Tuesdays).
    Contract codes are pinned in COT_MARKETS and were verified against
    the reference site's 2026-11-17 report (e.g. E-mini S&P 500 net
    -93,966, Natural gas net -262,984).

Definitions:
  - 1D = last session. 1M = 21 sessions. 1W = trailing 5 sessions.
    Strength benchmark = RSP.
  - RS 1M % = percentile rank (0-100) of the ETF's 1M return inside
    its own universe (Market Strength rows rank inside their group;
    Industry rows rank inside all 173).
  - RS Thrust % = percentile rank of the ETF's 5-session return inside
    the same universe (recent acceleration). This is our approximation:
    the reference site's exact thrust formula is not published.
  - 50D ATR index = the session's dollar move / 50-day ATR (dollars),
    i.e. the move in ATR multiples. atr_pct = 50D ATR as % of close.
  - Intraday % = (close - open) / open for the session.
  - Off 52W H % = close / highest high of the last 252 sessions - 1.
  - Breadth windows: Quarter = 63 sessions, Month = 21 sessions,
    34D = 34 sessions. 5D/10D ratio = sum of daily up counts over the
    last 5/10 sessions / sum of daily down counts over the same window.
  - Above 40D % = share of constituents with close above their
    40-session moving average.
  - Breadth indexes (per session, simple moving averages of closes):
    MMFI = % of the combined S&P 500 + Nasdaq-100 universe (518 names)
    above its 50-day SMA; MMTW = same universe above its 20-day SMA;
    S5TW = % of S&P 500 constituents above their 20-day SMA; NDTW =
    % of Nasdaq-100 constituents above their 20-day SMA. A ticker
    counts only with the full N sessions of history. Note the MM
    ("all-stocks") indexes cover the S&P 500 + Nasdaq-100 combined
    universe, not the full ~5,000 US-listed universe the standard
    $MMFI/$MMTW cover.
  - ADR % = mean true-range % over the last 21 sessions.
  - Extension = (close - 50-session SMA) / 50D ATR, in ATR multiples.

Behaviour (unchanged from the original script):
  - Only append new sessions; never rewrite history for past dates.
  - 1M = 21 sessions, benchmark RSP.
  - On any fetch failure the script prints a warning, exits 0 and
    leaves the last good history.json untouched. Sections whose data
    could not be fetched are null in the new session — never invented.
    The same applies to data/rs.json: if the RS rows cannot be
    computed (or cover fewer than RS_MIN_ROWS tickers), the last
    good rs.json is left untouched. The same rule applies to
    data/industry_weekly.json: if fewer than WEEKLY_MIN_TICKERS
    ETFs have a full 12 weeks of weekly bars, the last good file
    is left untouched.

Usage:
    pip install -r scripts/requirements.txt
    python scripts/fetch_data.py

Output:
    data/history.json  — { "as_of": "YYYY-MM-DD", "sessions": [...] }
    data/rs.json       — { "as_of", "close_date", "universe", "count",
                           "rows": [...] } for the latest close only.
    data/rs/<date>.json — same shape, one file per close date, newest
                           20 kept; the page lazy-loads the file for
                           the selected close.
    data/industry_weekly.json — { "as_of", "weeks": 12,
                           "candles": {ticker: [{w, o, h, l, c}]} }
                           for the latest close only (last 12 weeks,
                           weeks ending on each week's last trading day).
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "history.json"
RS_PATH = ROOT / "data" / "rs.json"
RS_HISTORY_DIR = ROOT / "data" / "rs"
RS_HISTORY_KEPT = 20  # per-date RS tables kept; older files are pruned
WEEKLY_PATH = ROOT / "data" / "industry_weekly.json"
WEEKS_KEPT = 12  # weekly candles kept per industry ETF
WEEKLY_MIN_TICKERS = 100  # below this, a run is treated as a failed
# fetch and the last good industry_weekly.json is left untouched.
RS_UNIVERSE = "LIQUID-ADV50M"
# RS Rating needs four 63-session quarters (252 sessions back) plus
# the 6M window (126 sessions); constituents are fetched with 2y of
# history so both are covered.
SESSIONS_3M = 63
SESSIONS_6M = 126
RS_MIN_ROWS = 100  # below this, a run is treated as a failed fetch
# and the last good rs.json is left untouched.
LIQUID_UNIVERSE_PATH = ROOT / "data" / "liquid_universe.json"
LIQUID_ADV_MIN = 50_000_000  # 30-session mean dollar volume bar
LIQUID_RESCREEN_DAYS = 7  # re-screen when the stored list is this old
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

TAPE = ["SPY", "QQQ", "IWM", "DIA", "RSP", "QQQE", "SPMO", "TLT"]
INDEX_NAMES = {
    "SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000",
    "DIA": "Dow Jones Industrial", "RSP": "S&P 500 equal weight",
    "QQQE": "Nasdaq 100 equal weight", "SPMO": "S&P 500 momentum",
    "TLT": "20Y+ Treasury",
}
BENCHMARK = "RSP"  # 1M strength is measured vs RSP, 1M = 21 sessions
SESSIONS_1M = 21
SESSIONS_QUARTER = 63
SESSIONS_34D = 34
SESSIONS_50D = 50
SESSIONS_40D = 40
SESSIONS_52W = 252

# Market Strength rows, exactly as on the site: (ticker, name).
SEGMENTS = [
    ("SPY", "Large cap"), ("QQQ", "Large cap growth"),
    ("IVE", "Large cap value"), ("MDY", "Mid cap"),
    ("IWM", "Small cap"), ("RSP", "Equal weight"),
    ("SPMO", "Momentum"), ("SCHD", "Dividend"),
    ("USMV", "Low volatility"),
]
EQUAL_WEIGHT_SECTORS = [
    ("RSPS", "Consumer staples EW"), ("RSPU", "Utilities EW"),
    ("RSPR", "Real estate EW"), ("RSPD", "Discretionary EW"),
    ("RSPI", "Industrials EW"), ("RSPH", "Health care EW"),
    ("RSPF", "Financials EW"), ("RSPM", "Materials EW"),
    ("RSPC", "Communication EW"), ("RSPE", "Energy EW"),
    ("RSPT", "Technology EW"),
]
SPDR_SECTORS = [
    ("XLP", "Staples"), ("XLRE", "Real Estate"), ("XLU", "Utilities"),
    ("XLY", "Discretionary"), ("XLV", "Health Care"),
    ("XLI", "Industrials"), ("XLF", "Financials"),
    ("XLB", "Materials"), ("XLE", "Energy"),
    ("XLC", "Communication"), ("XLK", "Technology"),
]

# Industry Group Strength: all 173 industry/thematic ETFs, exactly as
# on the site (ticker, name). Filled in by the build step from the
# exported site; see the end of this file for the list.
IND_LIST = [
    ('UNG', 'Natural gas'),
    ('BOIL', 'Natural gas 2x'),
    ('KOLD', 'Natural gas inverse'),
    ('USO', 'WTI crude oil'),
    ('UCO', 'Crude oil 2x'),
    ('SCO', 'Crude oil inverse'),
    ('FCG', 'Natural gas equities'),
    ('XOP', 'Oil & gas E&P'),
    ('OIH', 'Oil services'),
    ('XES', 'Oil equipment'),
    ('AMJ', 'MLPs'),
    ('MLPX', 'Midstream energy'),
    ('PHO', 'Water'),
    ('FIW', 'Water resources'),
    ('CGW', 'Global water'),
    ('JETS', 'Airlines'),
    ('AWAY', 'Travel technology'),
    ('RTH', 'Retail'),
    ('XRT', 'Retail equal weight'),
    ('IBUY', 'Online retail'),
    ('ONLN', 'Online retail pro'),
    ('CLIX', 'Long online / short stores'),
    ('EBIZ', 'E-commerce'),
    ('IHI', 'Medical equipment'),
    ('XHE', 'Health care equipment'),
    ('XBI', 'Biotechnology SPDR'),
    ('IBB', 'Biotechnology'),
    ('PBE', 'Biotech & genome'),
    ('XPH', 'Pharmaceuticals'),
    ('PPH', 'Pharmaceutical portfolio'),
    ('LABU', 'Biotech 3x'),
    ('LABD', 'Biotech -3x'),
    ('ARKG', 'Genomic revolution'),
    ('KRE', 'Regional banks'),
    ('KBWB', 'Bank portfolio'),
    ('KBE', 'Bank equal weight'),
    ('KBWR', 'Regional banking'),
    ('FINX', 'Fintech'),
    ('IPAY', 'Payments'),
    ('ARKF', 'Fintech innovation'),
    ('XSD', 'Semiconductor equal weight'),
    ('SOXL', 'Semiconductor 3x'),
    ('SOXS', 'Semiconductor -3x'),
    ('SMH', 'Semiconductors'),
    ('SOXX', 'Semiconductor index'),
    ('PSI', 'Semiconductor dynamic'),
    ('XSW', 'Software & services'),
    ('HACK', 'Cybersecurity'),
    ('CIBR', 'Cybersecurity Nasdaq'),
    ('SKYY', 'Cloud computing'),
    ('CLOU', 'Cloud computing global'),
    ('WCLD', 'Cloud software'),
    ('BOTZ', 'Robotics & AI'),
    ('ROBO', 'Robotics automation'),
    ('ARKQ', 'Autonomous technology'),
    ('ARKW', 'Next generation internet'),
    ('ARKK', 'Innovation'),
    ('QTUM', 'Quantum computing'),
    ('XME', 'Metals & mining'),
    ('COPX', 'Copper miners'),
    ('PICK', 'Mining & metals'),
    ('GDX', 'Gold miners'),
    ('GDXJ', 'Junior gold miners'),
    ('SIL', 'Silver miners'),
    ('SLVP', 'Silver miners iShares'),
    ('URA', 'Uranium'),
    ('URNM', 'Uranium miners'),
    ('LIT', 'Lithium & battery'),
    ('REMX', 'Rare earth metals'),
    ('SGDM', 'Gold miners sponsor'),
    ('GOEX', 'Gold explorers'),
    ('RING', 'Gold miners iShares'),
    ('XHB', 'Homebuilders'),
    ('ITB', 'Home construction'),
    ('NAIL', 'Homebuilders 3x'),
    ('PBW', 'Clean energy'),
    ('TAN', 'Solar'),
    ('FAN', 'Wind energy'),
    ('ICLN', 'Clean energy global'),
    ('QCLN', 'Clean energy index'),
    ('ACES', 'Clean energy solutions'),
    ('SMOG', 'Low carbon energy'),
    ('KRBN', 'Carbon allowances'),
    ('DBA', 'Agriculture'),
    ('CORN', 'Corn fund'),
    ('WEAT', 'Wheat fund'),
    ('SOYB', 'Soybean fund'),
    ('CANE', 'Sugar fund'),
    ('IYR', 'US real estate'),
    ('SCHH', 'US REIT'),
    ('REM', 'Mortgage REITs'),
    ('MORT', 'Mortgage REIT income'),
    ('ESPO', 'Video gaming'),
    ('GAMR', 'Gaming & eSports'),
    ('HERO', 'Gaming heroes'),
    ('SOCL', 'Social media'),
    ('MILN', 'Millennials'),
    ('GNOM', 'Genomics & biotech'),
    ('BUG', 'Cybersecurity bug'),
    ('DRIV', 'Electric vehicles'),
    ('KARS', 'Electric vehicles Krane'),
    ('KWEB', 'China internet'),
    ('CQQQ', 'China technology'),
    ('MCHI', 'China'),
    ('FXI', 'China large cap'),
    ('EWH', 'Hong Kong'),
    ('EWT', 'Taiwan'),
    ('EWJ', 'Japan'),
    ('EWZ', 'Brazil'),
    ('EWW', 'Mexico'),
    ('INDA', 'India'),
    ('INDY', 'India 50'),
    ('VNM', 'Vietnam'),
    ('TUR', 'Turkey'),
    ('GREK', 'Greece'),
    ('EWP', 'Spain'),
    ('EWI', 'Italy'),
    ('EWG', 'Germany'),
    ('EPU', 'Peru'),
    ('ARGT', 'Argentina'),
    ('GXG', 'Colombia'),
    ('ECH', 'Chile'),
    ('NORW', 'Norway'),
    ('EIRL', 'Ireland'),
    ('UVXY', 'Volatility 1.5x'),
    ('VIXY', 'Volatility futures'),
    ('SVXY', 'Volatility inverse'),
    ('VXX', 'Volatility note'),
    ('TQQQ', 'Nasdaq 3x'),
    ('SQQQ', 'Nasdaq -3x'),
    ('SPXL', 'S&P 500 3x'),
    ('SPXS', 'S&P 500 -3x'),
    ('UPRO', 'S&P 500 3x pro'),
    ('TNA', 'Small cap 3x'),
    ('TZA', 'Small cap -3x'),
    ('FAS', 'Financial 3x'),
    ('FAZ', 'Financial -3x'),
    ('NUGT', 'Gold miners 2x'),
    ('DUST', 'Gold miners -2x'),
    ('JNUG', 'Junior miners 2x'),
    ('JDST', 'Junior miners -2x'),
    ('ERX', 'Energy 2x'),
    ('ERY', 'Energy -2x'),
    ('GUSH', 'Oil & gas 2x'),
    ('DRIP', 'Oil & gas -2x'),
    ('DIG', 'Oil & gas 2x pro'),
    ('DUG', 'Oil & gas -2x pro'),
    ('UYM', 'Materials 2x'),
    ('SMN', 'Materials -2x'),
    ('DDM', 'Dow 2x'),
    ('DXD', 'Dow -2x'),
    ('QID', 'Nasdaq -2x'),
    ('SDS', 'S&P 500 -2x'),
    ('SSO', 'S&P 500 2x'),
    ('QLD', 'Nasdaq 2x'),
    ('UDOW', 'Dow 3x'),
    ('SDOW', 'Dow -3x'),
    ('TMF', 'Treasury 3x'),
    ('TMV', 'Treasury -3x'),
    ('TBT', 'Treasury -2x'),
    ('PST', 'Treasury -2x ultra'),
    ('TTT', 'Treasury -3x pro'),
    ('IBIT', 'Bitcoin trust'),
    ('ETHA', 'Ether trust'),
    ('BITO', 'Bitcoin futures'),
    ('ETHE', 'Ethereum trust'),
    ('GBTC', 'Bitcoin trust Grayscale'),
    ('FDIG', 'Digital payments'),
    ('VCX', 'Private technology'),
    ('ARKX', 'Space exploration'),
    ('UFO', 'Space industry'),
    ('SVIX', 'Short volatility futures'),
    ('MOON', 'Moonshot innovators')
]

# Positioning: (ETF, name, CFTC legacy contract code in deafut.txt).
# Verified against the reference site's 2026-11-17 COT report.
COT_MARKETS = [
    ("IWM", "Russell 2000", "239742"),   # RUSSELL E-MINI - CME
    ("SPY", "S&P 500", "13874A"),        # E-MINI S&P 500 - CME
    ("QQQ", "Nasdaq 100", "209742"),     # NASDAQ MINI - CME
    ("IBIT", "Bitcoin", "133741"),       # BITCOIN - CME
    ("ETHA", "Ether", "146021"),         # ETHER CASH SETTLED - CME
    ("GLD", "Gold", "088691"),           # GOLD - COMEX
    ("CPER", "Copper", "085692"),        # COPPER- #1 - COMEX
    ("SLV", "Silver", "084691"),         # SILVER - COMEX
    ("USO", "WTI crude oil", "067651"),  # WTI-PHYSICAL - NYMEX
    ("UNG", "Natural gas", "023651"),    # NAT GAS NYME - NYMEX
]
COT_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
SPX_LIST_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NDX_LIST_URL = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
UA = {"User-Agent": "Mozilla/5.0 (KKS data fetcher; github.com/koivan61/KKS)"}


# ---------------------------------------------------------------- helpers

def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or not b or not math.isfinite(a) or not math.isfinite(b):
        return None
    return round((a / b - 1.0) * 100.0, 2)


def _num(x) -> float | None:
    try:
        v = float(str(x).strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pct_rank(value: float, population: list[float]) -> float | None:
    """Percentile rank of value in population, 0-100."""
    pop = sorted(v for v in population if v is not None)
    if not pop or value is None:
        return None
    below = sum(1 for v in pop if v < value)
    equal = sum(1 for v in pop if v == value)
    if len(pop) == 1:
        return 50.0
    return round((below + 0.5 * equal) / (len(pop) - 1) * 100.0, 1)


def _percentile_of(value: float, series: list[float]) -> float:
    """Rank of value in series, 0-100; 50.0 when there is no history."""
    if not series:
        return 50.0
    below = sum(1 for v in series if v < value)
    equal = sum(1 for v in series if v == value)
    if len(series) == 1:
        return 50.0
    return round((below + 0.5 * equal) / (len(series) - 1) * 100.0, 1)


def yahoo_ticker(sym: str) -> str:
    """Wikipedia uses BRK.B; Yahoo wants BRK-B."""
    return sym.replace(".", "-")


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------------------------------------------------------------- OHLCV

def fetch_ohlcv(tickers: list[str], period: str = "6mo") -> dict:
    """{ticker: DataFrame indexed by date string with Close/High/Low/
    Open/Volume} via yfinance, batched; {} on failure."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed; run pip install -r scripts/requirements.txt",
              file=sys.stderr)
        return {}
    out: dict = {}
    for i in range(0, len(tickers), 80):
        chunk = tickers[i:i + 80]
        try:
            data = yf.download(
                " ".join(chunk), period=period, interval="1d",
                auto_adjust=False, progress=False, group_by="ticker",
            )
        except Exception as exc:  # noqa: BLE001 - keep old data
            print(f"yfinance download failed for {chunk[:3]}...: {exc}",
                  file=sys.stderr)
            continue
        if data is None or len(data) == 0:
            continue
        for ticker in chunk:
            try:
                frame = data[ticker] if len(chunk) > 1 else data
                closes = frame["Close"].dropna()
                if len(closes) == 0:
                    continue
                sub = frame.loc[closes.index].copy()
                sub.index = [d.date().isoformat() for d in sub.index]
                out[ticker] = sub
            except Exception:
                continue
    return out


def fetch_stooq(ticker: str) -> dict | None:
    """Stooq daily CSV fallback for one ETF ticker; None on failure."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        raw = _http_get(url, timeout=20).decode("utf-8", "ignore")
        import pandas as pd
        frame = pd.read_csv(io.StringIO(raw), parse_dates=["Date"])
    except Exception as exc:  # noqa: BLE001
        print(f"Stooq fallback failed for {ticker}: {exc}", file=sys.stderr)
        return None
    if frame is None or len(frame) == 0 or "Close" not in frame.columns:
        return None
    frame = frame.dropna(subset=["Close"])
    frame.index = [d.date().isoformat() for d in frame["Date"]]
    return {"frame": frame}


def fetch_etf_ohlcv(tickers: list[str]) -> dict:
    """ETF OHLCV via yfinance, Stooq per-ticker fallback for gaps."""
    out = fetch_ohlcv(tickers, period="6mo")
    missing = [t for t in tickers if t not in out]
    for ticker in missing:
        got = fetch_stooq(ticker)
        if got is not None:
            out[ticker] = got["frame"]
    return out


# ---------------------------------------------------------------- constituents

class _TablesParser(HTMLParser):
    """Collect every <table> as a list of rows of cell text."""

    def __init__(self):
        super().__init__()
        self.tables: list = []
        self._table = None
        self._row = None
        self._buf = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._row = []
            self._table.append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._in_cell = True
            self._buf = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._row.append(self._buf.strip())
        elif tag == "table":
            self._table = None
        elif tag == "tr":
            self._row = None

    def handle_data(self, data):
        if self._in_cell:
            self._buf += data


def _parse_constituent_table(html: str) -> list[tuple[str, str, str, str]]:
    """(yahoo ticker, GICS sector, GICS sub-industry, company name)
    from a Wikipedia constituents table; [] when the table cannot be
    found."""
    parser = _TablesParser()
    parser.feed(html)
    for table in parser.tables:
        if not table or not table[0]:
            continue
        header = [c.lower() for c in table[0]]
        if not any(h in ("symbol", "ticker") for h in header):
            continue
        sym_i = next(i for i, h in enumerate(header) if h in ("symbol", "ticker"))
        sec_i = next((i for i, h in enumerate(header) if "sector" in h and "sub" not in h), None)
        sub_i = next((i for i, h in enumerate(header) if "sub-industry" in h or "sub industry" in h), None)
        name_i = next((i for i, h in enumerate(header) if "security" in h or "company" in h), None)
        out = []
        for row in table[1:]:
            if len(row) <= sym_i:
                continue
            sym = re.sub(r"[^A-Z0-9.\-]", "", row[sym_i].upper())
            if not sym or len(sym) > 6:
                continue
            sector = row[sec_i] if sec_i is not None and len(row) > sec_i else ""
            sub = row[sub_i] if sub_i is not None and len(row) > sub_i else sector
            name = row[name_i] if name_i is not None and len(row) > name_i else sym
            out.append((yahoo_ticker(sym), sector, sub or sector, name))
        if out:
            return out
    return []


def fetch_constituents() -> tuple[dict, set, set]:
    """S&P 500 + Nasdaq-100 constituents.

    Returns ({yahoo ticker: (sector, sub-industry, company name)},
    spx_tickers, ndx_tickers) — the two sets record which Wikipedia
    list each ticker came from, so breadth indexes can be computed
    per universe. Returns ({}, set(), set()) when neither list can be
    fetched — callers must then leave breadth/liquid null instead of
    inventing values.
    """
    out: dict[str, tuple[str, str, str]] = {}
    spx: set[str] = set()
    ndx: set[str] = set()
    for url, dest in ((SPX_LIST_URL, spx), (NDX_LIST_URL, ndx)):
        try:
            html = _http_get(url, timeout=30).decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"Constituent list fetch failed ({url}): {exc}", file=sys.stderr)
            continue
        for sym, sector, sub, name in _parse_constituent_table(html):
            out.setdefault(sym, (sector, sub, name))
            dest.add(sym)
    if out:
        print(f"Constituents: {len(out)} tickers (S&P 500 + Nasdaq-100)")
    return out, spx, ndx


# ---------------------------------------------------------------- liquid universe

_COMMON_EXCL_RE = re.compile(
    r"\b(warrants?|rights?|units?|preferred|preference|notes? due|"
    r"debenture|baby bond|senior notes?|subordinated|trust|etf|etn|"
    r"exchange[- ]traded( note)?|index fund|fund)\b",
    re.I)


def _is_common_stock(name: str, etf_flag: str, test_flag: str) -> bool:
    """True for common stocks in a Nasdaq Trader symbol directory row."""
    if etf_flag == "Y" or test_flag == "Y":
        return False
    return not _COMMON_EXCL_RE.search(name or "")


def fetch_nasdaq_trader_lists() -> dict:
    """All US-listed common stocks from the Nasdaq Trader directories.

    Returns {yahoo ticker: security name} for nasdaqlisted.txt
    (NASDAQ) + otherlisted.txt (NYSE/AMEX/...), excluding ETFs,
    ETNs, funds, preferreds, warrants, units, rights, test issues
    and other non-common-share security types. ADS are kept: they
    are common shares in depositary form. {} on failure — callers
    must keep the last good universe instead of inventing one.
    """
    out: dict[str, str] = {}
    for url in (NASDAQ_LISTED_URL, OTHER_LISTED_URL):
        try:
            raw = _http_get(url, timeout=30).decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"Nasdaq Trader list fetch failed ({url}): {exc}", file=sys.stderr)
            return {}
        lines = raw.splitlines()
        if not lines:
            continue
        hdr = lines[0].split("|")
        for ln in lines[1:]:
            if not ln.strip() or ln.startswith("File Creation Time"):
                continue
            parts = ln.split("|")
            if len(parts) < len(hdr):
                continue
            row = dict(zip(hdr, parts))
            if "Symbol" in row:  # nasdaqlisted.txt
                sym = row["Symbol"].strip()
                name = row["Security Name"].strip()
                etf = row.get("ETF", "N")
                test = row.get("Test Issue", "N")
            else:  # otherlisted.txt
                sym = (row.get("NASDAQ Symbol") or row.get("ACT Symbol", "")).strip()
                name = row["Security Name"].strip()
                etf = row.get("ETF", "N")
                test = row.get("Test Issue", "N")
            if not sym or not _is_common_stock(name, etf, test):
                continue
            out.setdefault(yahoo_ticker(sym), name)
    if out:
        print(f"Nasdaq Trader lists: {len(out)} common stocks")
    return out


def screen_liquid_universe(candidates: dict) -> list[str]:
    """Tickers whose 30-session mean dollar volume exceeds $50M.

    Fetches ~3 months of closes for every candidate and keeps the
    ones with mean(close x volume) over the last 30 sessions above
    LIQUID_ADV_MIN. A ticker with fewer than 30 sessions is left
    out. Returns Yahoo tickers, sorted.
    """
    frames = fetch_ohlcv(sorted(candidates), period="3mo")
    keep: list[str] = []
    for ticker, frame in frames.items():
        try:
            dv = frame["Close"] * frame["Volume"]
            dv = dv.dropna()
            if len(dv) < 30:
                continue
            if float(dv.iloc[-30:].mean()) > LIQUID_ADV_MIN:
                keep.append(ticker)
        except Exception:
            continue
    print(f"Liquid screen: {len(keep)} of {len(frames)} fetched pass "
          f"${LIQUID_ADV_MIN / 1_000_000:.0f}M 30D mean dollar volume")
    return sorted(keep)


def load_liquid_universe() -> dict | None:
    """Stored liquid universe ({as_of, count, tickers, names}) or None."""
    if not LIQUID_UNIVERSE_PATH.exists():
        return None
    try:
        data = json.loads(LIQUID_UNIVERSE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not data.get("tickers"):
        return None
    return data


def _universe_age_days(universe: dict, close_date: str) -> int | None:
    try:
        as_of = date.fromisoformat(universe.get("as_of", ""))
        close = date.fromisoformat(close_date)
    except ValueError:
        return None
    return (close - as_of).days


def refresh_liquid_universe(close_date: str) -> bool:
    """Full re-screen of the Nasdaq Trader lists; True if refreshed.

    Writes data/liquid_universe.json. On any failure, or when too
    few tickers pass, the last good file is kept and False returned.
    """
    candidates = fetch_nasdaq_trader_lists()
    if not candidates:
        print("Liquid re-screen: candidate lists unavailable; keeping last good universe.")
        return False
    tickers = screen_liquid_universe(candidates)
    if len(tickers) < RS_MIN_ROWS:
        print(f"Liquid re-screen: only {len(tickers)} passers; keeping last good universe.")
        return False
    payload = {"as_of": close_date, "count": len(tickers), "tickers": tickers,
               "names": {t: candidates[t] for t in tickers if t in candidates}}
    LIQUID_UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIQUID_UNIVERSE_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"Liquid universe refreshed: {len(tickers)} tickers (as_of={close_date})")
    return True


def liquid_constituents(universe: dict, constituents: dict,
                        mid_small: dict | None = None) -> dict:
    """Constituents dict for compute_rs_rows from the liquid universe.

    Industry comes from the S&P 500 / Nasdaq-100 tables where the
    ticker is in them, else the S&P 400 / 600 tables, else "Other";
    the name from the stored universe file.
    """
    names = universe.get("names", {}) or {}
    mid_small = mid_small or {}
    out: dict[str, tuple[str, str, str]] = {}
    for ticker in universe.get("tickers", []):
        industry = constituents.get(ticker, ("", "", ""))[1]
        if not industry:
            industry = mid_small.get(ticker, "")
        industry = industry or "Other"
        out[ticker] = (industry, industry, names.get(ticker) or ticker)
    return out


SP400_LIST_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
SP600_LIST_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"


def fetch_sp_mid_small_industries() -> dict:
    """GICS sub-industry by ticker from the S&P 400 / 600 lists.

    Used only to label liquid-universe stocks that are not in the
    S&P 500 / Nasdaq-100 tables. {} on failure — those rows stay
    "Other" instead of inventing an industry.
    """
    out: dict[str, str] = {}
    for url in (SP400_LIST_URL, SP600_LIST_URL):
        try:
            html = _http_get(url, timeout=30).decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            print(f"S&P mid/small list fetch failed ({url}): {exc}", file=sys.stderr)
            continue
        for sym, _sector, sub, _name in _parse_constituent_table(html):
            out.setdefault(sym, sub)
    if out:
        print(f"S&P 400/600 industries: {len(out)} tickers")
    return out


# ---------------------------------------------------------------- COT

def fetch_cot() -> dict | None:
    """Parse the CFTC legacy futures-only file.

    Returns {"report_date": "YYYY-MM-DD", "markets": {etf: {...}}} or
    None when the file cannot be fetched or a market is missing.
    Legacy columns: 8/9 Noncommercial long/short, 11/12 Commercial
    long/short, 15/16 Nonreportable long/short; 38/39, 41/42, 45/46
    are the weekly changes in those positions.
    """
    try:
        raw = _http_get(COT_URL, timeout=30).decode("utf-8", "ignore")
    except Exception as exc:  # noqa: BLE001
        print(f"CFTC COT fetch failed: {exc}", file=sys.stderr)
        return None
    by_code: dict[str, list] = {}
    report_date = None
    for row in csv.reader(io.StringIO(raw)):
        if len(row) < 47:
            continue
        code = row[3].strip()
        if not report_date and row[2].strip():
            report_date = row[2].strip()
        by_code[code] = row
    markets = {}
    for etf, name, code in COT_MARKETS:
        row = by_code.get(code)
        if row is None:
            print(f"CFTC: contract {code} ({etf}) not in this week's file",
                  file=sys.stderr)
            return None
        nc = _num(row[8])
        nc_s = _num(row[9])
        cm = _num(row[11])
        cm_s = _num(row[12])
        nr = _num(row[15])
        nr_s = _num(row[16])
        if None in (nc, nc_s, cm, cm_s, nr, nr_s):
            return None
        markets[etf] = {
            "etf": etf,
            "name": name,
            "code": code,
            "large_net": int(nc - nc_s),
            "commercial_net": int(cm - cm_s),
            "small_net": int(nr - nr_s),
            "large_chg": int(_num(row[38]) - _num(row[39])) if _num(row[38]) is not None and _num(row[39]) is not None else None,
            "commercial_chg": int(_num(row[41]) - _num(row[42])) if _num(row[41]) is not None and _num(row[42]) is not None else None,
            "small_chg": int(_num(row[45]) - _num(row[46])) if _num(row[45]) is not None and _num(row[46]) is not None else None,
        }
    return {"report_date": report_date, "markets": markets}


def _cot_percentiles(cot: dict, existing_sessions: list[dict]) -> dict:
    """Add 0-100 percentiles for each COT group, ranked against the
    net-position series already stored in history.json plus this
    week's nets (5-year lookback = at most ~260 weekly reports)."""
    series: dict[str, dict[str, list[float]]] = {}
    for sess in existing_sessions:
        pos = sess.get("positioning") or {}
        for m in pos.get("markets", []) or []:
            s = series.setdefault(m["etf"], {"large": [], "commercial": [], "small": []})
            for key, field in (("large", "large_net"), ("commercial", "commercial_net"), ("small", "small_net")):
                if m.get(field) is not None:
                    s[key].append(float(m[field]))
    out = {}
    for etf, m in cot["markets"].items():
        hist = series.get(etf, {"large": [], "commercial": [], "small": []})
        entry = dict(m)
        for key, field in (("large", "large_net"), ("commercial", "commercial_net"), ("small", "small_net")):
            entry[f"{key}_pct"] = _percentile_of(float(m[field]), hist[key][-260:])
        # Crowding call, same rule as the site: large specs at an
        # extreme and commercials at the opposite extreme.
        entry["state"] = (
            "Crowded Short" if entry["large_pct"] <= 5 and entry["commercial_pct"] >= 95
            else "Crowded Long" if entry["large_pct"] >= 95 and entry["commercial_pct"] <= 5
            else "Within range"
        )
        out[etf] = entry
    return out


# ---------------------------------------------------------------- strength rows

def _atr(frame, idx: int) -> tuple[float | None, float | None]:
    """50D ATR in dollars and as % of close, ending at row idx."""
    try:
        import pandas as pd
    except ImportError:
        return None, None
    if idx < 1:
        return None, None
    window = frame.iloc[max(0, idx - SESSIONS_50D + 1): idx + 1]
    if len(window) < 10:
        return None, None
    high = window["High"].astype(float)
    low = window["Low"].astype(float)
    prev_close = window["Close"].astype(float).shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = float(tr.mean())
    close = float(frame["Close"].iloc[idx])
    return atr, round(atr / close * 100.0, 2) if close else None


def _strength_row(ticker: str, name: str, frame, dates: list[str],
                  idx: int, bench_1m: float | None,
                  bench_5d: float | None,
                  universe_1m: list[float], universe_5d: list[float]) -> dict | None:
    """One Market Strength / Industry row for session dates[idx].

    bench_1m / bench_5d are RSP's 21-session and 5-session returns
    for the same session; ret_5d is the ticker's own 5-session
    return, reused as the 1W return (1W = trailing 5 sessions).
    """
    row = frame.iloc[idx]
    close = _num(row.get("Close"))
    if close is None:
        return None
    prev_idx = idx - 1
    ret_1d = None
    if prev_idx >= 0:
        ret_1d = pct(close, _num(frame["Close"].iloc[prev_idx]))
    j = idx - SESSIONS_1M
    ret_1m = pct(close, _num(frame["Close"].iloc[j])) if j >= 0 else None
    k = idx - 5
    ret_5d = pct(close, _num(frame["Close"].iloc[k])) if k >= 0 else None
    open_px = _num(row.get("Open"))
    intraday = round((close / open_px - 1.0) * 100.0, 2) if open_px else None
    atr, atr_pct = _atr(frame, idx)
    atr_index = None
    if atr and ret_1d is not None:
        move = close - float(frame["Close"].iloc[prev_idx])
        atr_index = round(move / atr, 2)
    high_52w = None
    window = frame.iloc[max(0, idx - SESSIONS_52W + 1): idx + 1]
    if len(window):
        try:
            high_52w = float(window["High"].astype(float).max())
        except Exception:
            high_52w = None
    return {
        "ticker": ticker,
        "name": name,
        "rs_1m_pct": _pct_rank(ret_1m, universe_1m),
        "rs_thrust_pct": _pct_rank(ret_5d, universe_5d),
        "atr_index": atr_index,
        "atr_pct": atr_pct,
        "rs_vs_rsp": round(ret_1m - bench_1m, 2) if ret_1m is not None and bench_1m is not None else None,
        "ret_1w_pct": ret_5d,
        "rs_1w_vs_rsp": round(ret_5d - bench_5d, 2) if ret_5d is not None and bench_5d is not None else None,
        "intraday_pct": intraday,
        "ret_1d_pct": ret_1d,
        "ret_1m_pct": ret_1m,
        "off_52w_high_pct": round((close / high_52w - 1.0) * 100.0, 2) if high_52w else None,
    }


def _ret_at(frame, idx: int, back: int) -> float | None:
    j = idx - back
    if j < 0:
        return None
    return pct(_num(frame["Close"].iloc[idx]), _num(frame["Close"].iloc[j]))


# ---------------------------------------------------------------- breadth

def compute_breadth(const_closes, dates: list[str], spx_frame) -> dict:
    """Breadth for every session date in `dates`, or None.

    const_closes: DataFrame of constituent closes, columns = tickers,
    index = date strings. Returns {date: breadth dict}.
    """
    try:
        import pandas as pd
    except ImportError:
        return {}
    if const_closes is None or const_closes.empty:
        return {}
    closes = const_closes.reindex(dates)
    ret_1d = closes.pct_change() * 100.0
    ret_21 = closes.pct_change(21) * 100.0
    ret_63 = closes.pct_change(63) * 100.0
    ret_34 = closes.pct_change(34) * 100.0
    up_1d = (ret_1d >= 4.0)
    down_1d = (ret_1d <= -4.0)
    up_n = up_1d.sum(axis=1)
    down_n = down_1d.sum(axis=1)
    out = {}
    for i, d in enumerate(dates):
        if d not in ret_1d.index:
            continue
        def _count(frame, thr, sign):
            col = frame.loc[d]
            valid = col.notna()
            if sign > 0:
                return int(((col >= thr) & valid).sum())
            return int(((col <= -thr) & valid).sum())
        up5 = int(up_n.iloc[max(0, i - 4): i + 1].sum())
        dn5 = int(down_n.iloc[max(0, i - 4): i + 1].sum())
        up10 = int(up_n.iloc[max(0, i - 9): i + 1].sum())
        dn10 = int(down_n.iloc[max(0, i - 9): i + 1].sum())
        ma40 = closes.rolling(40, min_periods=40).mean()
        above = closes.loc[d] > ma40.loc[d]
        n_above = int(above.sum())
        n_valid = int(ma40.loc[d].notna().sum())
        spx_close = _num(spx_frame["Close"].loc[d]) if spx_frame is not None and d in spx_frame.index else None
        spx_1d = None
        if spx_frame is not None and d in spx_frame.index:
            pos = list(spx_frame.index).index(d)
            if pos > 0:
                spx_1d = pct(spx_close, _num(spx_frame["Close"].iloc[pos - 1]))
        out[d] = {
            "daily_up": int(up_n.loc[d]),
            "daily_down": int(down_n.loc[d]),
            "ratio_5d": round(up5 / dn5, 2) if dn5 else None,
            "ratio_10d": round(up10 / dn10, 2) if dn10 else None,
            "quarter_up": _count(ret_63, 25.0, 1),
            "quarter_down": _count(ret_63, 25.0, -1),
            "month25_up": _count(ret_21, 25.0, 1),
            "month25_down": _count(ret_21, 25.0, -1),
            "month50_up": _count(ret_21, 50.0, 1),
            "month50_down": _count(ret_21, 50.0, -1),
            "d34_up": _count(ret_34, 13.0, 1),
            "d34_down": _count(ret_34, 13.0, -1),
            "above_40d_pct": round(n_above / n_valid * 100.0, 1) if n_valid else None,
            "spx_close": spx_close,
            "spx_session_pct": spx_1d,
        }
    return out


def compute_breadth_idx(const_closes, spx_cols: list[str], ndx_cols: list[str],
                        dates: list[str]) -> dict:
    """Per-session % of constituents above their 20D / 50D SMA, by universe.

    const_closes: DataFrame of constituent closes, columns = tickers,
    index = date strings. spx_cols / ndx_cols: tickers in each list
    that are present in the frame. Returns {date: {"mmfi", "mmtw",
    "s5tw", "ndtw"}} — mmfi/mmtw over the combined universe, s5tw over
    S&P 500 only, ndtw over Nasdaq-100 only. A ticker counts only when
    it has the full N sessions of history (rolling mean is NaN
    otherwise), and is excluded from numerator AND denominator. Values
    are rounded to 1 decimal; None when no valid names. Returns {}
    when the frames are missing.
    """
    try:
        import pandas as pd
    except ImportError:
        return {}
    if const_closes is None or const_closes.empty:
        return {}
    closes = const_closes.reindex(dates)
    ma20 = closes.rolling(20, min_periods=20).mean()
    ma50 = closes.rolling(50, min_periods=50).mean()
    all_cols = [c for c in closes.columns]
    spx = [c for c in spx_cols if c in closes.columns]
    ndx = [c for c in ndx_cols if c in closes.columns]

    def _above_pct(cols, ma, d):
        if not cols:
            return None
        if d not in ma.index:
            return None
        m = ma.loc[d, cols]
        c = closes.loc[d, cols]
        valid = m.notna() & c.notna()
        n_valid = int(valid.sum())
        if not n_valid:
            return None
        return round(float(((c > m) & valid).sum()) / n_valid * 100.0, 1)

    out = {}
    for d in dates:
        if d not in closes.index:
            continue
        out[d] = {
            "mmfi": _above_pct(all_cols, ma50, d),
            "mmtw": _above_pct(all_cols, ma20, d),
            "s5tw": _above_pct(spx, ma20, d),
            "ndtw": _above_pct(ndx, ma20, d),
        }
    return out


def compute_breadth_idx_counts(const_closes, spx_cols: list[str],
                               ndx_cols: list[str], d: str) -> dict:
    """Valid-name counts (n_valid) behind each breadth index at date d.

    Diagnostic helper for the 2026-11-20 backfill verification; mirrors
    compute_breadth_idx exactly. Returns {"mmfi": n, "mmtw": n,
    "s5tw": n, "ndtw": n} with 0 when the frames are missing.
    """
    try:
        import pandas as pd
    except ImportError:
        return {"mmfi": 0, "mmtw": 0, "s5tw": 0, "ndtw": 0}
    if const_closes is None or const_closes.empty:
        return {"mmfi": 0, "mmtw": 0, "s5tw": 0, "ndtw": 0}
    closes = const_closes
    ma20 = closes.rolling(20, min_periods=20).mean()
    ma50 = closes.rolling(50, min_periods=50).mean()
    all_cols = [c for c in closes.columns]
    spx = [c for c in spx_cols if c in closes.columns]
    ndx = [c for c in ndx_cols if c in closes.columns]

    def _n(cols, ma):
        if not cols or d not in ma.index:
            return 0
        return int((ma.loc[d, cols].notna() & closes.loc[d, cols].notna()).sum())

    return {
        "mmfi": _n(all_cols, ma50),
        "mmtw": _n(all_cols, ma20),
        "s5tw": _n(spx, ma20),
        "ndtw": _n(ndx, ma20),
    }


# ---------------------------------------------------------------- liquid

def compute_liquid(const_ohlcv: dict, constituents: dict, dates: list[str],
                   bench_1m_by_date: dict) -> dict:
    """Liquid leaders per session date.

    const_ohlcv: {ticker: OHLCV frame}. Returns {date: liquid dict}.
    Universe is S&P 500 + Nasdaq-100 constituents; a stock is liquid
    when its 21-session mean dollar volume > $100M and mean shares
    > 1M. Leaders are the top 2% by 1M return among liquid stocks.
    """
    try:
        import pandas as pd
    except ImportError:
        return {}
    tickers = [t for t in constituents if t in const_ohlcv]
    if not tickers:
        return {}
    closes = pd.DataFrame({t: const_ohlcv[t]["Close"] for t in tickers})
    highs = pd.DataFrame({t: const_ohlcv[t]["High"] for t in tickers})
    lows = pd.DataFrame({t: const_ohlcv[t]["Low"] for t in tickers})
    vols = pd.DataFrame({t: const_ohlcv[t]["Volume"] for t in tickers})
    closes = closes.reindex(dates)
    highs = highs.reindex(dates)
    lows = lows.reindex(dates)
    vols = vols.reindex(dates)
    ret_1m = closes.pct_change(21) * 100.0
    sma50 = closes.rolling(50, min_periods=50).mean()
    prev_close = closes.shift(1)
    tr = pd.concat([
        (highs - lows).stack(),
        (highs - prev_close).abs().stack(),
        (lows - prev_close).abs().stack(),
    ], axis=1).max(axis=1).unstack()
    atr50 = tr.rolling(50, min_periods=50).mean()
    adr21 = (tr / closes * 100.0).rolling(21, min_periods=21).mean()
    dollar_vol = (closes * vols).rolling(21, min_periods=21).mean()
    avg_shares = vols.rolling(21, min_periods=21).mean()
    out = {}
    for d in dates:
        if d not in ret_1m.index:
            continue
        liquid = (dollar_vol.loc[d] > 100_000_000) & (avg_shares.loc[d] > 1_000_000)
        liquid = liquid & ret_1m.loc[d].notna() & sma50.loc[d].notna()
        cand = ret_1m.loc[d][liquid]
        if len(cand) == 0:
            continue
        n_leaders = max(1, int(math.ceil(len(cand) * 0.02)))
        top = cand.sort_values(ascending=False).head(n_leaders)
        leaders = []
        for t, r1m in top.items():
            close = _num(closes.loc[d, t])
            sma = _num(sma50.loc[d, t])
            atr = _num(atr50.loc[d, t])
            leaders.append({
                "ticker": t,
                "industry": constituents[t][1] or constituents[t][0] or "Other",
                "ret_1m_pct": round(float(r1m), 2),
                "extension": round((close - sma) / atr, 2) if close is not None and sma is not None and atr else None,
                "avg_dollar_vol": int(dollar_vol.loc[d, t]) if pd.notna(dollar_vol.loc[d, t]) else None,
                "avg_shares": int(avg_shares.loc[d, t]) if pd.notna(avg_shares.loc[d, t]) else None,
                "adr_pct": round(float(adr21.loc[d, t]), 2) if pd.notna(adr21.loc[d, t]) else None,
            })
        # Group summary by GICS sub-industry, top 12 by leaders then
        # median 1M return. Group RS is the median 1M return minus
        # RSP's 1M return (percentage points).
        groups = []
        bench = bench_1m_by_date.get(d)
        for industry, tick_list in _group_by_industry(cand.index, constituents).items():
            med_ret = float(cand[tick_list].median()) if tick_list else None
            exts = []
            for t in tick_list:
                close = _num(closes.loc[d, t])
                sma = _num(sma50.loc[d, t])
                atr = _num(atr50.loc[d, t])
                if close is not None and sma is not None and atr:
                    exts.append((close - sma) / atr)
            groups.append({
                "industry": industry,
                "leaders": sum(1 for l in leaders if l["industry"] == industry),
                "liquid_stocks": len(tick_list),
                "median_ret_1m_pct": round(med_ret, 2) if med_ret is not None else None,
                "group_rs_pp": round(med_ret - bench, 2) if med_ret is not None and bench is not None else None,
                "group_extension": round(sorted(exts)[len(exts) // 2], 2) if exts else None,
            })
        groups.sort(key=lambda g: (-g["leaders"], -(g["median_ret_1m_pct"] or 0)))
        out[d] = {
            "leaders": leaders,
            "groups": groups[:12],
            "leaders_count": len(leaders),
            "universe_count": int(liquid.sum()),
        }
    return out


def _group_by_industry(tickers, constituents: dict) -> dict:
    groups: dict[str, list] = {}
    for t in tickers:
        groups.setdefault(constituents[t][1] or constituents[t][0] or "Other", []).append(t)
    return groups


# ---------------------------------------------------------------- RS screener

def _r1(x) -> float | None:
    """Round to 1 decimal place; None for NaN / missing."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, 1) if math.isfinite(v) else None


def _rank_1_99(value: float, population: list[float]) -> int | None:
    """O'Neil-style percentile rank scaled to 1-99 (integer)."""
    pop = sorted(v for v in population if v is not None)
    if not pop or value is None:
        return None
    below = sum(1 for v in pop if v < value)
    equal = sum(1 for v in pop if v == value)
    if len(pop) == 1:
        return 50
    rank = (below + 0.5 * equal) / (len(pop) - 1) * 98.0 + 1.0
    return max(1, min(99, int(round(rank))))


def compute_rs_rows(const_ohlcv: dict, constituents: dict,
                    bench_frame, close_date: str) -> list[dict]:
    """One RS Screener row per liquid-universe stock for `close_date`.

    const_ohlcv: {ticker: OHLCV frame} with ~2y of history (the RS
    Rating needs 252 sessions back). bench_frame is the RSP frame.
    Rows are sorted by rs_pct descending. A value that cannot be
    computed (e.g. a recent IPO with < 252 sessions for the RS
    Rating) is null, never invented. Tickers with no close on
    close_date are left out entirely.
    """
    try:
        import pandas as pd
    except ImportError:
        return []
    tickers = [t for t in constituents if t in const_ohlcv]
    if not tickers or bench_frame is None or close_date not in bench_frame.index:
        return []
    closes = pd.DataFrame({t: const_ohlcv[t]["Close"] for t in tickers})
    highs = pd.DataFrame({t: const_ohlcv[t]["High"] for t in tickers})
    vols = pd.DataFrame({t: const_ohlcv[t]["Volume"] for t in tickers})
    closes = closes.sort_index()
    highs = highs.sort_index()
    vols = vols.sort_index()
    if close_date not in closes.index:
        return []
    pos = list(closes.index).index(close_date)
    # Benchmark 1M return (21 sessions back, RSP's own calendar).
    bench_pos = list(bench_frame.index).index(close_date)
    bench_1m = _ret_at(bench_frame, bench_pos, SESSIONS_1M)

    close = closes.iloc[pos]
    ret_1d = closes.pct_change(1).iloc[pos] * 100.0
    ret_1m = closes.pct_change(SESSIONS_1M).iloc[pos] * 100.0
    ret_3m = closes.pct_change(SESSIONS_3M).iloc[pos] * 100.0
    ret_6m = closes.pct_change(SESSIONS_6M).iloc[pos] * 100.0
    # O'Neil RS Rating: four 63-session quarterly returns, weighted
    # 0.4 / 0.2 / 0.2 / 0.2, percentile ranked 1-99 across the
    # universe. Needs 252 sessions of history per ticker.
    weighted = pd.Series(float("nan"), index=tickers, dtype=float)
    if pos >= SESSIONS_52W:
        q1 = closes.iloc[pos] / closes.iloc[pos - 63] - 1.0
        q2 = closes.iloc[pos - 63] / closes.iloc[pos - 126] - 1.0
        q3 = closes.iloc[pos - 126] / closes.iloc[pos - 189] - 1.0
        q4 = closes.iloc[pos - 189] / closes.iloc[pos - 252] - 1.0
        weighted = 0.4 * q1 + 0.2 * q2 + 0.2 * q3 + 0.2 * q4
    sma50 = closes.rolling(50, min_periods=50).mean().iloc[pos]
    sma200 = closes.rolling(200, min_periods=200).mean().iloc[pos]
    adr = closes.pct_change().abs().mul(100.0).rolling(21, min_periods=21).mean().iloc[pos]
    dollar_vol = closes.mul(vols).rolling(21, min_periods=21).mean().iloc[pos] / 1_000_000.0
    high_52w = highs.rolling(252, min_periods=1).max().iloc[pos]
    ema_9d = closes.ewm(span=9, adjust=False).mean().iloc[pos]
    ema_9w = closes.ewm(span=45, adjust=False).mean().iloc[pos]
    ema_9m = closes.ewm(span=189, adjust=False).mean().iloc[pos]

    universe_1m = [float(v) for v in ret_1m.dropna()]
    weighted_pop = [float(v) for v in weighted.dropna()]
    rows: list[dict] = []
    for t in tickers:
        px = _num(close.get(t))
        if px is None:
            continue  # no close on close_date: row left out, not invented
        r1m = _num(ret_1m.get(t))
        sector, sub, name = constituents[t]
        rows.append({
            "ticker": t,
            "name": name or t,
            "industry": sub or sector or "Other",
            "price": round(px, 2),
            "ret_1d_pct": _r1(ret_1d.get(t)),
            "ret_1m_pct": _r1(r1m),
            "ret_3m_pct": _r1(ret_3m.get(t)),
            "ret_6m_pct": _r1(ret_6m.get(t)),
            "rs_1m_vs_rsp_pct": _r1(r1m - bench_1m) if r1m is not None and bench_1m is not None else None,
            # _pct_rank can overshoot 100 for the top-ranked value
            # (mid-rank tie handling); clamp to the 0-100 range.
            "rs_pct": min(100.0, _pct_rank(r1m, universe_1m)) if r1m is not None else None,
            "rs_rating": _rank_1_99(_num(weighted.get(t)), weighted_pop),
            "ext_50d_pct": _r1((px / _num(sma50.get(t)) - 1.0) * 100.0) if _num(sma50.get(t)) else None,
            "adr_pct": _r1(adr.get(t)),
            "avg_dollar_vol_m": _r1(dollar_vol.get(t)),
            "above_50d": bool(px > _num(sma50.get(t))) if _num(sma50.get(t)) else None,
            "above_200d": bool(px > _num(sma200.get(t))) if _num(sma200.get(t)) else None,
            "off_52w_high_pct": _r1((px / _num(high_52w.get(t)) - 1.0) * 100.0) if _num(high_52w.get(t)) else None,
            "ema_9d": bool(px > _num(ema_9d.get(t))) if pos >= 8 and _num(ema_9d.get(t)) else None,
            "ema_9w": bool(px > _num(ema_9w.get(t))) if pos >= 44 and _num(ema_9w.get(t)) else None,
            "ema_9m": bool(px > _num(ema_9m.get(t))) if pos >= 188 and _num(ema_9m.get(t)) else None,
        })
    rows.sort(key=lambda r: (r["rs_pct"] is None, -(r["rs_pct"] or 0)))
    return rows


def write_rs_snapshot(rows: list[dict], close_date: str) -> None:
    """Write data/rs.json for one close date (latest session only)."""
    payload = {
        "as_of": close_date,
        "close_date": close_date,
        "universe": RS_UNIVERSE,
        "count": len(rows),
        "rows": rows,
    }
    RS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"RS screener: wrote {len(rows)} rows to {RS_PATH} (as_of={close_date})")


def write_rs_history(rows: list[dict], close_date: str) -> None:
    """Write data/rs/<close_date>.json and prune to the newest 20 dates.

    Same payload shape as data/rs.json. The page lazy-loads the
    per-date file when the user picks that close, so the screener
    shows the real table for past dates instead of falling back to
    the embedded preview sample. Pruning keeps the repo bounded:
    one file per trading session, newest 20 kept.
    """
    RS_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of": close_date,
        "close_date": close_date,
        "universe": RS_UNIVERSE,
        "count": len(rows),
        "rows": rows,
    }
    path = RS_HISTORY_DIR / f"{close_date}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"RS screener: wrote {len(rows)} rows to {path} (as_of={close_date})")
    files = sorted(RS_HISTORY_DIR.glob("????-??-??.json"))
    for old in files[:-RS_HISTORY_KEPT]:
        old.unlink()
        print(f"RS screener: pruned old per-date file {old.name}")


# ---------------------------------------------------------------- weekly candles

def _weekly_bars(frame) -> list[dict]:
    """Weekly OHLC bars from one daily OHLCV frame, last 12 weeks.

    Weeks are ISO calendar weeks; each bar ends on that week's last
    trading day, which is the bar's date ("w"). Bars are
    chronological, most recent last. A bar is skipped when any of
    its OHLC values is missing. Returns [] when the frame has too
    little history.
    """
    try:
        import pandas as pd
    except ImportError:
        return []
    if frame is None or len(frame) < 5:
        return []
    idx = pd.to_datetime(frame.index)
    df = frame.copy()
    df.index = idx
    iso = idx.isocalendar()
    bars: list[dict] = []
    for _, g in df.groupby([iso.year, iso.week]):
        o = _num(g["Open"].iloc[0])
        h = _num(g["High"].max())
        l = _num(g["Low"].min())
        c = _num(g["Close"].iloc[-1])
        if None in (o, h, l, c):
            continue
        bars.append({
            "w": g.index[-1].date().isoformat(),
            "o": round(o, 2),
            "h": round(h, 2),
            "l": round(l, 2),
            "c": round(c, 2),
        })
    return bars[-WEEKS_KEPT:]


def compute_industry_weekly(etf_ohlcv: dict) -> dict | None:
    """Weekly OHLC candles for the 173 industry ETFs, latest close
    only: {"as_of", "weeks": 12, "candles": {ticker: [bars]}}.

    Derived from the daily bars already fetched in this run — no
    extra downloads. An ETF is included only when it has a full
    12 weeks of bars. Returns None when too few ETFs qualify
    (caller keeps the last good file).
    """
    candles: dict[str, list[dict]] = {}
    as_of = None
    for ticker, _ in IND_LIST:
        frame = etf_ohlcv.get(ticker)
        if frame is None or len(frame) == 0:
            continue
        bars = _weekly_bars(frame)
        if len(bars) < WEEKS_KEPT:
            continue
        candles[ticker] = bars
        if as_of is None or bars[-1]["w"] > as_of:
            as_of = bars[-1]["w"]
    if len(candles) < WEEKLY_MIN_TICKERS or as_of is None:
        return None
    return {"as_of": as_of, "weeks": WEEKS_KEPT, "candles": candles}


def write_industry_weekly(payload: dict) -> None:
    """Write data/industry_weekly.json for one close date (latest
    close only)."""
    WEEKLY_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEEKLY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Industry weekly: wrote {len(payload['candles'])} ETFs to "
          f"{WEEKLY_PATH} (as_of={payload['as_of']})")


# ---------------------------------------------------------------- sessions

def build_sessions(etf_ohlcv: dict, const_ohlcv: dict, constituents: dict,
                   cot: dict | None, existing_sessions: list[dict],
                   spx_tickers: set | None = None,
                   ndx_tickers: set | None = None) -> list[dict]:
    """Build one session dict per close date from raw OHLCV.

    Sections that could not be computed (missing data) are null —
    never invented. The front end ships with sample sessions for
    2026-11-13 to 2026-11-20; this appends new sessions in the same
    shape and never overwrites those samples.
    """
    if BENCHMARK not in etf_ohlcv:
        return []
    try:
        import pandas as pd
    except ImportError:
        return []
    bench_frame = etf_ohlcv[BENCHMARK]
    dates = sorted(bench_frame.index.tolist())
    # Benchmark 1M / 1W (5-session) returns per date.
    bench_1m_by_date: dict[str, float | None] = {}
    bench_5d_by_date: dict[str, float | None] = {}
    for i, d in enumerate(dates):
        bench_1m_by_date[d] = _ret_at(bench_frame, i, SESSIONS_1M)
        bench_5d_by_date[d] = _ret_at(bench_frame, i, 5)
    # Breadth (needs the constituent close matrix).
    breadth_by_date: dict = {}
    idx_by_date: dict = {}
    if const_ohlcv:
        tickers = [t for t in constituents if t in const_ohlcv]
        if tickers:
            closes = pd.DataFrame({t: const_ohlcv[t]["Close"] for t in tickers})
            spx_frame = etf_ohlcv.get("^GSPC")
            breadth_by_date = compute_breadth(closes, dates, spx_frame)
            spx_cols = [t for t in (spx_tickers or ()) if t in closes.columns]
            ndx_cols = [t for t in (ndx_tickers or ()) if t in closes.columns]
            idx_by_date = compute_breadth_idx(closes, spx_cols, ndx_cols, dates)
    # Liquid leaders.
    liquid_by_date: dict = {}
    if const_ohlcv and constituents:
        liquid_by_date = compute_liquid(const_ohlcv, constituents, dates, bench_1m_by_date)
    # Positioning: carry the last published report forward when the
    # CFTC file is missing or its report date has not moved.
    positioning = None
    last_pos = None
    for sess in reversed(existing_sessions):
        if sess.get("positioning"):
            last_pos = sess["positioning"]
            break
    if cot is not None:
        if last_pos is None or cot["report_date"] != last_pos.get("report_date"):
            markets = _cot_percentiles(cot, existing_sessions)
            crowded = next(
                (m["name"] for m in markets.values() if m["state"] == "Crowded Short"),
                next((m["name"] for m in markets.values() if m["state"] == "Crowded Long"), None),
            )
            positioning = {
                "report_date": cot["report_date"],
                "crowded": crowded,
                "markets": [markets[etf] for etf, _, _ in COT_MARKETS],
            }
        else:
            positioning = last_pos
    else:
        positioning = last_pos
    # Strength universes (1M / 5D returns) for percentile ranks.
    def _universe_returns(rows_def, d):
        r1m, r5d = [], []
        for ticker, _ in rows_def:
            frame = etf_ohlcv.get(ticker)
            if frame is None or d not in frame.index:
                continue
            j = frame.index.tolist().index(d)
            r1 = _ret_at(frame, j, SESSIONS_1M)
            r5 = _ret_at(frame, j, 5)
            if r1 is not None:
                r1m.append(r1)
            if r5 is not None:
                r5d.append(r5)
        return r1m, r5d

    sessions: list[dict] = []
    for i, d in enumerate(dates):
        # Tape (8 ETFs).
        tape = []
        for ticker in TAPE:
            frame = etf_ohlcv.get(ticker)
            if frame is None or d not in frame.index:
                continue
            j = frame.index.tolist().index(d)
            tape.append(_strength_row(
                ticker, INDEX_NAMES[ticker], frame, dates, j,
                bench_1m_by_date[d], bench_5d_by_date[d], [], []))
        if len(tape) != len(TAPE):
            continue
        tape_simple = [{
            "ticker": r["ticker"],
            "close": round(float(etf_ohlcv[r["ticker"]]["Close"].loc[d]), 2),
            "session_pct": r["ret_1d_pct"],
            "rel_1m_rsp_pct": r["rs_vs_rsp"],
            "atr_index": r["atr_index"],
        } for r in tape]
        # Market Strength groups.
        sectors = {}
        for key, rows_def in (
            ("segments", SEGMENTS),
            ("equal_weight", EQUAL_WEIGHT_SECTORS),
            ("spdr", SPDR_SECTORS),
        ):
            u1m, u5d = _universe_returns(rows_def, d)
            rows = []
            for ticker, name in rows_def:
                frame = etf_ohlcv.get(ticker)
                if frame is None or d not in frame.index:
                    continue
                j = frame.index.tolist().index(d)
                row = _strength_row(ticker, name, frame, dates, j,
                                    bench_1m_by_date[d], bench_5d_by_date[d],
                                    u1m, u5d)
                if row:
                    rows.append(row)
            sectors[key] = rows
        # Industries (173).
        u1m, u5d = _universe_returns(IND_LIST, d)
        industries = []
        for ticker, name in IND_LIST:
            frame = etf_ohlcv.get(ticker)
            if frame is None or d not in frame.index:
                continue
            j = frame.index.tolist().index(d)
            row = _strength_row(ticker, name, frame, dates, j,
                                bench_1m_by_date[d], bench_5d_by_date[d],
                                u1m, u5d)
            if row:
                industries.append(row)
        industries.sort(key=lambda r: (r["rs_vs_rsp"] is None, -(r["rs_vs_rsp"] or 0)))
        breadth = breadth_by_date.get(d)
        spx_frame = etf_ohlcv.get("^GSPC")
        if breadth:
            spx_close = breadth["spx_close"]
        elif spx_frame is not None and d in spx_frame.index:
            spx_close = _num(spx_frame["Close"].loc[d])
        else:
            spx_close = None
        spx_1d = breadth["spx_session_pct"] if breadth else None
        leader = industries[0] if industries else None
        session = {
            "close_date": d,
            "tape": tape_simple,
            "spx_close": spx_close,
            "spx_session_pct": spx_1d,
            "breadth_up": breadth["daily_up"] if breadth else None,
            "breadth_down": breadth["daily_down"] if breadth else None,
            "breadth": breadth,
            "breadth_idx": idx_by_date.get(d),
            "sectors": sectors if any(sectors.values()) else None,
            "industries": industries if industries else None,
            "positioning": positioning,
            "liquid": liquid_by_date.get(d),
            "leader_1m": leader["ticker"] if leader else None,
            "leader_1m_rsp_pct": leader["rs_vs_rsp"] if leader else None,
            "positioning_crowded_short": positioning.get("crowded") if positioning else None,
        }
        sessions.append(session)
    return sessions


# ---------------------------------------------------------------- main

def main() -> int:
    existing = {"as_of": None, "sessions": []}
    if DATA_PATH.exists():
        try:
            existing = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"WARNING: {DATA_PATH} is not valid JSON; starting fresh",
                  file=sys.stderr)
    existing_sessions = existing.get("sessions", [])
    have = {s.get("close_date") for s in existing_sessions}

    etf_tickers = sorted({*TAPE, "^GSPC",
                          *[t for t, _ in SEGMENTS],
                          *[t for t, _ in EQUAL_WEIGHT_SECTORS],
                          *[t for t, _ in SPDR_SECTORS],
                          *[t for t, _ in IND_LIST]})
    print(f"Fetching ETF OHLCV for {len(etf_tickers)} tickers ...")
    etf_ohlcv = fetch_etf_ohlcv(etf_tickers)
    if BENCHMARK not in etf_ohlcv:
        print("No benchmark data fetched; leaving history.json unchanged.")
        return 0

    print("Fetching constituent lists ...")
    constituents, spx_tickers, ndx_tickers = fetch_constituents()
    const_ohlcv: dict = {}
    if constituents:
        # 2y of history: the RS Rating needs 252 sessions back, and
        # breadth/liquid reuse the same frames.
        print(f"Fetching constituent OHLCV for {len(constituents)} tickers ...")
        const_ohlcv = fetch_ohlcv(sorted(constituents), period="2y")
        missing = [t for t in constituents if t not in const_ohlcv]
        if missing:
            print(f"Stooq fallback for {len(missing)} missing constituents ...")
            for ticker in missing:
                got = fetch_stooq(ticker)
                if got is not None:
                    const_ohlcv[ticker] = got["frame"]
        if not const_ohlcv:
            print("Constituent OHLCV fetch failed; breadth/liquid will be null.")
    else:
        print("Constituent lists unavailable; breadth/liquid will be null.")

    print("Fetching CFTC COT ...")
    cot = fetch_cot()
    if cot is None:
        print("COT unavailable; carrying forward the last published report.")

    # RS Screener (single latest session). Regenerated on every run,
    # even when history.json gains no new session. Runs over the
    # liquid universe, re-screened on the Monday run or whenever the
    # stored list is at least 7 days old; the nightly run never
    # re-scans the full ~6,000 names.
    if BENCHMARK in etf_ohlcv:
        rs_close = etf_ohlcv[BENCHMARK].index[-1]
        liquid = load_liquid_universe()
        age = _universe_age_days(liquid, rs_close) if liquid else None
        try:
            is_monday = date.fromisoformat(rs_close).weekday() == 0
        except ValueError:
            is_monday = False
        if liquid is None or is_monday or (age is not None and age >= LIQUID_RESCREEN_DAYS):
            if refresh_liquid_universe(rs_close):
                liquid = load_liquid_universe()
        if liquid:
            liquid_cons = liquid_constituents(
                liquid, constituents, fetch_sp_mid_small_industries())
            print(f"Fetching liquid-universe OHLCV for {len(liquid_cons)} tickers ...")
            liquid_ohlcv = fetch_ohlcv(sorted(liquid_cons), period="2y")
            missing = [t for t in liquid_cons if t not in liquid_ohlcv]
            if missing:
                print(f"Stooq fallback for {len(missing)} missing liquid tickers ...")
                for ticker in missing:
                    got = fetch_stooq(ticker)
                    if got is not None:
                        liquid_ohlcv[ticker] = got["frame"]
            if liquid_ohlcv:
                rs_rows = compute_rs_rows(liquid_ohlcv, liquid_cons,
                                          etf_ohlcv[BENCHMARK], rs_close)
                if len(rs_rows) >= RS_MIN_ROWS:
                    write_rs_snapshot(rs_rows, rs_close)
                    write_rs_history(rs_rows, rs_close)
                else:
                    print(f"RS screener: only {len(rs_rows)} rows for {rs_close}; "
                          "leaving rs.json unchanged.")
            else:
                print("Liquid-universe OHLCV fetch failed; leaving rs.json unchanged.")
        else:
            print("No liquid universe available; leaving rs.json unchanged.")

    # Industry weekly candles (latest close only). Regenerated on
    # every run, even when history.json gains no new session.
    weekly = compute_industry_weekly(etf_ohlcv)
    if weekly is not None:
        write_industry_weekly(weekly)
    else:
        print("Industry weekly: too few ETFs with 12 weeks of bars; "
              "leaving industry_weekly.json unchanged.")

    new_sessions = [s for s in build_sessions(
        etf_ohlcv, const_ohlcv, constituents, cot, existing_sessions,
        spx_tickers, ndx_tickers)
        if s["close_date"] not in have]
    if not new_sessions:
        print("No new sessions to append.")
        return 0
    existing["sessions"] = sorted(
        existing_sessions + new_sessions,
        key=lambda s: s.get("close_date", ""),
    )
    existing["as_of"] = existing["sessions"][-1]["close_date"]
    existing["note"] = (
        "Sessions built by scripts/fetch_data.py. Tape, Market Strength, "
        "Industry (173 ETFs), Breadth (S&P 500 constituents), Positioning "
        "(CFTC legacy COT, last published report) and Liquid Leadership "
        "(S&P 500 + Nasdaq-100, top 2% by 1M return). Sections that could "
        "not be fetched are null, never invented."
    )
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"Appended {len(new_sessions)} session(s); as_of={existing['as_of']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

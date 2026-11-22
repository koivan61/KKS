# KKS — GitHub Pages

A finance market-console in light grey (background
rgb(184, 184, 184), bullish rgb(117, 117, 117), bearish black):
sticky header with date navigation, 6 pages — Debrief,
Breadth, Market Strength, Industry Group Strength,
Positioning and Liquid Leadership. There is no Screener page.

## How to publish

1. Repository: `koivan61/KKS`.
   Upload this folder to it, overwriting `index.html`.
2. In the repo: Settings → Pages → Build and deployment →
   Deploy from a branch → Branch `main`, folder `/ (root)`.
3. Open `https://koivan61.github.io/KKS/#debrief`.

`index.html` is the exported site. On load it fetches
`data/history.json` (same folder) and re-renders every panel
from the sessions in that file; if the file cannot be fetched
it falls back to the embedded 2026-11-20 / 2026-11-19 snapshot,
so no panel ever goes blank.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The 6-page site (single file, no build step) |
| `data/history.json` | Sessions by close date. Sample sessions cover 2026-11-13 to 2026-11-20; the 2026-11-20 close matches the reference (SPY -3.64%, SPX 6,914.4, UNG leader +12.3% vs RSP, Natural gas Crowded Short). |
| `scripts/fetch_data.py` | Fetches daily data and appends new sessions. Run it locally or via Actions. |
| `scripts/requirements.txt` | `yfinance`, `pandas` |
| `.github/workflows/update-data.yml` | Weekdays at 22:00 UTC: fetch, then commit `data/history.json` if a new session appeared. |
| `.nojekyll` | Tells GitHub Pages not to run Jekyll. |

## Auto-update — what it covers

`scripts/fetch_data.py` (append-only, never rewrites past
sessions; on fetch failure it exits 0 and leaves the last good
`history.json` in place) covers, per close date:

- **Tape / Market Strength / Sectors / Industries**: Yahoo
  Finance via `yfinance` (Stooq daily-CSV fallback per ticker)
  for the 8 tape ETFs, 9 market-segment, 11 equal-weight-sector
  and 11 SPDR-sector ETFs, and all 173 industry ETFs. Computes
  1D, 1M vs RSP, RS 1M %, RS Thrust %, 50D ATR index, Intraday,
  1M and Off 52W H.
- **Breadth**: computed from live S&P 500 constituents
  (Wikipedia list, 518 tickers with Nasdaq-100): Daily ±4%
  up/down, 5D/10D ratio, Quarter ±25%, Month ±25% and ±50%,
  34D ±13%, Above 40D %, SPX close and 1D %.
- **Positioning (COT)**: CFTC legacy futures-only file
  (`deafut.txt`) for the 10 markets. Net long/short contracts
  verified exactly against the reference site's 2026-11-17
  report (e.g. SPY large specs net -93,966, UNG -262,984,
  GLD +166,132). Only a published release is used; if the
  report date has not moved, the last published positioning
  is carried forward unchanged.
- **Liquid Leadership**: S&P 500 + Nasdaq-100 universe,
  avg dollar volume > $100M and avg shares > 1M, top 2% by
  1M return, with extension vs 50D SMA, avg $ vol, avg shares
  and ADR%, plus the 12-row group summary.

## Known limits

- **COT percentiles start at 50.0 / "Within range"** until
  weekly runs accumulate COT history in `history.json`; the
  crowded call is empty until then. The CFTC annual history
  zips are not yet parsed.
- **RS Thrust % is an approximation** (percentile of the
  5-session return in the same universe); the reference site's
  exact thrust formula is not published.
- **Liquid universe is narrower than the reference site's**
  (~518 names vs ~786 liquid stocks), so leader counts differ
  (top 2% is about 10–12 leaders here vs 16 on the site).
  Industry labels come from Wikipedia GICS sub-industries.
- **The live yfinance run has not been verified in this
  sandbox** (yfinance hit timeouts there); the first real test
  is the GitHub Actions run after upload. Yahoo Finance has no
  official public API; `yfinance` uses its chart endpoints, so
  a fetch can fail — when it does, the workflow keeps the last
  good `history.json`.
- **TradingView**: charts only, via its embed widgets
  (Advanced Real-Time Chart). TradingView is **not** a data API
  for this site — the numbers come from `history.json`.
- **CFTC Commitments of Traders**: weekly COT data for
  Positioning. Only use a published release; never invent a
  COT value for a week with no release.
- Percentages on the page render to 1 decimal place;
  the underlying values in `data/history.json` are to 2 decimals.

## Definitions used on the page

- `1D` = last session. `1M` = 21 sessions.
- Strength benchmark = RSP (equal-weight S&P 500 ETF).
- `ATR index` = session move standardised by ATR.
- `Thrust` = recent acceleration in 1M strength.
- Positioning percentiles are 5-year percentiles for Large specs,
  Commercials and Small specs; “Crowded Short / Long” is the
  crowding call from those percentiles.

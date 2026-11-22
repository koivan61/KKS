# KKS Debrief — GitHub Pages

A finance market-console Debrief page in light grey (background
rgb(184, 184, 184), bullish rgb(117, 117, 117), bearish black):
sticky header with date navigation, 3 summary cards, an 8-ETF
Market tape, and Breadth, Sector leadership, Industry ETFs and
Positioning panels.

This is the Debrief page only (the first page). The full console has
6 more pages: Breadth, Market Strength, Industry Group Strength,
Positioning, Liquid Leadership and Screener.

## How to publish

1. Repository: `koivan61/KKS` — already created (empty).
   Upload this folder to it.
2. In the repo: Settings → Pages → Build and deployment →
   Deploy from a branch → Branch `main`, folder `/ (root)`.
3. Open `https://koivan61.github.io/KKS/#debrief`.

`index.html` is the exported Debrief page. `data/history.json`
holds the sessions it renders; the page is a static snapshot per
close date, not a live stream.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The Debrief page (single file, no build step) |
| `data/history.json` | Sessions by close date. Sample sessions cover 2026-11-13 to 2026-11-20; the 2026-11-20 close matches the reference (SPY -3.64%, SPX 6,914.4, UNG leader +12.3% vs RSP, Natural gas Crowded Short). |
| `scripts/fetch_data.py` | Fetches daily closes and appends new sessions. Run it locally or via Actions. |
| `scripts/requirements.txt` | `yfinance`, `pandas` |
| `.github/workflows/update-data.yml` | Weekdays at 22:00 UTC: fetch, then commit `data/history.json` if a new session appeared. |

## Data sources — what is real, what is not

- **Yahoo Finance (via `yfinance`)**: daily closes for
  SPY, QQQ, IWM, DIA, RSP, QQQE, SPMO, TLT. Yahoo Finance has no
  official public API; `yfinance` uses its chart endpoints, so a
  fetch can fail. When it does, the workflow keeps the last good
  `history.json` instead of blanking the page.
- **Stooq** (`https://stooq.com/q/d/l/?s=spy.us&i=d`): free daily
  closes and 5-minute intraday bars. Named on the reference site
  as the source for intraday data. Use it as the fallback if Yahoo
  Finance is unavailable.
- **CFTC Commitments of Traders**: weekly COT data for Positioning.
  Only use a published release; never invent a COT value for a
  week with no release. Older release dates in history may be
  estimates — the page says so.
- **TradingView**: charts only, via its embed widgets
  (Advanced Real-Time Chart). TradingView is **not** a data API
  for this page — the numbers come from `history.json`.

## Definitions used on the page

- `1D` = last session. `1M` = 21 sessions.
- Strength benchmark = RSP (equal-weight S&P 500 ETF).
- `ATR index` = session move standardised by ATR.
- `Thrust` = recent acceleration in 1M strength.
- Positioning percentiles are 5-year percentiles for Large specs,
  Commercials and Small specs; “Crowded Short / Long” is the
  crowding call from those percentiles.

## What still needs doing

- Fill in Breadth (SPX constituents), Sector / Industry ETF lists
  (173 industry ETFs) and COT history — `fetch_data.py` currently
  builds the tape only; those panels use the shipped sample
  sessions until their own fetchers are added.
- Confirm the Muse GitHub App installation has been given access
  to `koivan61/KKS` (GitHub → Settings → Applications →
  Muse GitHub App → Repository access) before pushing.
- Percentages on the exported page render to 1 decimal place;
  the underlying values in `data/history.json` are to 2 decimals.

# KKS — GitHub Pages

A finance market-console in light grey (background
rgb(184, 184, 184), bullish rgb(117, 117, 117), bearish black):
sticky header with date navigation, 7 pages — Debrief,
Breadth, Market Strength, Industry Group Strength,
Positioning, Liquid Leadership and RS Screener. The old
NELL/OSB Screener page was removed; the RS Screener is a
new page built on relative strength.

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
so no panel ever goes blank. The RS Screener page additionally
fetches `data/rs.json` (one row per stock for the latest close);
if that file cannot be fetched it falls back to its embedded
2026-11-20 snapshot.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The 7-page site (single file, no build step) |
| `data/history.json` | Sessions by close date. Sample sessions in this file cover 2026-11-19 to 2026-11-20 (the page's embedded snapshot covers 2026-11-13 to 2026-11-20); the 2026-11-20 close matches the reference (SPY -3.64%, SPX 6,914.4, UNG leader +12.3% vs RSP, Natural gas Crowded Short). |
| `data/rs.json` | RS Screener snapshot for the latest close only: `{as_of, close_date, universe: "SP500+NDX100", count, rows}`. Initial snapshot is 2026-11-20, 517 rows of the 518-ticker universe (SNDK had no 2026-11-20 bar on Yahoo and is left out). Percentages are to 1 decimal place. |
| `data/industry_weekly.json` | Weekly OHLC candles for the Industry Group Strength charts, latest close only: `{as_of, weeks: 12, candles: {ticker: [{w, o, h, l, c}]}}`. One bar per ISO week, ending on each week's last trading day, last 12 weeks. Initial snapshot is 2026-11-20, 168 of the 173 ETFs (AMJ, KBWR, GXG, MOON returned 404 from Yahoo and CLIX had only one daily bar left in the window; all left out, never invented). Regenerated on every run from the daily bars already fetched. |
| `scripts/fetch_data.py` | Fetches daily data and appends new sessions; also regenerates `data/rs.json`. Run it locally or via Actions. |
| `scripts/requirements.txt` | `yfinance`, `pandas` |
| `.github/workflows/update-data.yml` | Weekdays at 22:00 UTC: fetch, then commit `data/history.json`, `data/rs.json` and `data/industry_weekly.json` if any changed. |
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
  1M and Off 52W H — plus 1W % and 1W RS vs RSP (trailing 5
  sessions). The Industry page also gets weekly candlestick
  data: `data/industry_weekly.json`, last 12 weekly OHLC bars
  per industry ETF, derived from the same daily bars (no extra
  downloads), latest close only.
- **Breadth**: computed from live S&P 500 constituents
  (Wikipedia list, 518 tickers with Nasdaq-100): Daily ±4%
  up/down, 5D/10D ratio, Quarter ±25%, Month ±25% and ±50%,
  34D ±13%, Above 40D %, SPX close and 1D %.
  Each session also carries `breadth_idx` — four breadth
  indexes, all simple moving averages of daily closes, a
  ticker counting only with the full N sessions of history:
  **MMFI** = % of the combined S&P 500 + Nasdaq-100 universe
  (518 names) above its 50-day SMA; **MMTW** = same universe
  above its 20-day SMA; **S5TW** = % of S&P 500 constituents
  above their 20-day SMA; **NDTW** = % of Nasdaq-100
  constituents above their 20-day SMA. Note the MM
  ("all-stocks") indexes cover the 518-name combined universe,
  not the full ~5,000 US-listed universe the standard $MMFI /
  $MMTW cover; R2TW (Russell 2000) is not computed — the
  fetcher holds no Russell 2000 constituents.
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
- **RS Screener**: one row per S&P 500 + Nasdaq-100
  constituent for the latest close, from ~2y of closes
  (constituents are fetched with `period="2y"`): 1D / 1M /
  3M / 6M returns, RS 1M % vs RSP, RS percentile (0–100),
  O'Neil RS Rating (1–99), extension vs 50D SMA, ADR %,
  avg dollar volume, above 50D / 200D, off 52W high and
  9D / 9W / 9M EMA position. Names and industries come from
  the Wikipedia constituent tables (GICS sub-industry).
  Written to `data/rs.json` (latest close only, not a
  history list) on every run, even when `history.json`
  gains no new session; if fewer than 100 rows can be
  computed the last good `rs.json` is left untouched.

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
  good `history.json` / `rs.json` / `industry_weekly.json`. Note: the initial
  `data/rs.json` (2026-11-20, 517 rows) was built in the
  sandbox by calling Yahoo's chart endpoint directly with
  urllib, because yfinance's own transport times out there
  and Stooq closes the connection; the fetcher itself still
  uses yfinance + Stooq, which is what the Actions run uses.
  The initial `data/industry_weekly.json` (2026-11-20, 168
  ETFs) was built the same way.
- **RS Screener limits**: a stock with no bar on the close
  date is left out of `rs.json` (e.g. SNDK on 2026-11-20);
  the O'Neil RS Rating is null for stocks with under 252
  sessions of history (recent IPOs / index additions, e.g.
  FDXF, VYLR, HONA, SPCX on 2026-11-20) — never estimated.
  The two RS measures differ by design: RS percentile ranks
  the 1M return vs RSP over 21 sessions, while the O'Neil
  rating ranks a weighted 12-month return (0.4× latest
  quarter + 0.2× each prior quarter) 1–99.
- **TradingView**: charts only, via its embed widgets
  (Advanced Real-Time Chart). TradingView is **not** a data API
  for this site — the numbers come from `history.json`.
- **CFTC Commitments of Traders**: weekly COT data for
  Positioning. Only use a published release; never invent a
  COT value for a week with no release.
- Percentages on the page render to 1 decimal place;
  the underlying values in `data/history.json` are to 2 decimals.

## Definitions used on the page

- `1D` = last session. `1M` = 21 sessions. `1W` = trailing
  5 sessions. `3M` = 63 sessions. `6M` = 126 sessions.
- Strength benchmark = RSP (equal-weight S&P 500 ETF).
- RS percentile (`rs_pct`) = percentile rank (0–100) of the
  stock's 1M return inside the S&P 500 + Nasdaq-100 universe;
  `rs_1m_vs_rsp_pct` = stock 1M return minus RSP 1M return.
  `rs_1w_vs_rsp_pct` is the same over 1W (trailing 5 sessions):
  stock 5-session return minus RSP 5-session return.
- Weekly candles (`data/industry_weekly.json`) = one OHLC bar
  per ISO week for each industry ETF, ending on the week's last
  trading day, last 12 weeks, latest close only (no history —
  each run overwrites with the newest 12 weeks).
- O'Neil RS Rating (`rs_rating`) = percentile rank (1–99) of
  the weighted quarterly return 0.4×Q1 + 0.2×Q2 + 0.2×Q3 +
  0.2×Q4, where each Q is a 63-session return; needs 252
  sessions of history.
- `ADR %` on the RS Screener = mean absolute daily % move
  over the last 21 sessions (the Liquid page's ADR % is mean
  true-range % instead).
- `ext_50d_pct` = (close − 50D SMA) / 50D SMA × 100.
- `ema_9d` / `ema_9w` / `ema_9m` = close above the 9-session /
  45-session / 189-session EMA.
- `ATR index` = session move standardised by ATR.
- `Thrust` = recent acceleration in 1M strength.
- Positioning percentiles are 5-year percentiles for Large specs,
  Commercials and Small specs; “Crowded Short / Long” is the
  crowding call from those percentiles.

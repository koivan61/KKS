#!/usr/bin/env python3
"""
Fetch daily market data for the KKS Debrief page and write data/history.json.

Sources (all free / public):
  - Yahoo Finance via yfinance: daily closes for index / factor ETFs
    SPY, QQQ, IWM, DIA, RSP, QQQE, SPMO, TLT and sector / industry ETFs.
    Yahoo Finance has no official public API; yfinance scrapes its
    chart endpoints, so treat this as best-effort and keep the last
    good history.json when a fetch fails.
  - Stooq (https://stooq.com) CSV: free daily closes, useful as a
    fallback for the same tickers, and for intraday 5-minute bars.
  - CFTC Commitments of Traders: weekly COT CSV for Positioning.
    The Debrief page uses the last published COT release; do not
    invent a COT value for a week with no release.

TradingView is NOT a data API here. Use its embed widgets
(Advanced Real-Time Chart / Symbol Overview) in index.html for
charts only. The numbers on the Debrief page come from history.json.

Usage:
    pip install -r scripts/requirements.txt
    python scripts/fetch_data.py

Output:
    data/history.json  — { "as_of": "YYYY-MM-DD", "sessions": [...] }
    Each session is one close date with the same fields index.html
    expects: tape (8 ETFs), breadth, sectors, industries, positioning.
    Only append a new session; never rewrite history for past dates.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "history.json"

TAPE = ["SPY", "QQQ", "IWM", "DIA", "RSP", "QQQE", "SPMO", "TLT"]
BENCHMARK = "RSP"  # 1M strength is measured vs RSP, 1M = 21 sessions
SESSIONS_1M = 21


def pct(a: float, b: float) -> float | None:
    if not b or not math.isfinite(a) or not math.isfinite(b):
        return None
    return round((a / b - 1.0) * 100.0, 2)


def atr_index(session_return: float | None, atr: float | None) -> float | None:
    """Return / ATR, rounded to 2dp. None when either input is missing."""
    if session_return is None or atr is None or atr == 0:
        return None
    return round(session_return / atr, 2)


def fetch_closes() -> dict:
    """Return {ticker: [(date, close), ...]} using yfinance, or {} on failure."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed; run pip install -r scripts/requirements.txt", file=sys.stderr)
        return {}
    try:
        data = yf.download(
            " ".join(TAPE), period="6mo", interval="1d",
            auto_adjust=False, progress=False, group_by="ticker",
        )
    except Exception as exc:  # noqa: BLE001 - network / Yahoo outage: keep old data
        print(f"yfinance download failed: {exc}", file=sys.stderr)
        return {}
    out: dict[str, list] = {}
    for ticker in TAPE:
        try:
            closes = data[ticker]["Close"].dropna()
        except Exception:
            continue
        out[ticker] = [(d.date().isoformat(), float(v)) for d, v in closes.items()]
    return out


def build_sessions(closes: dict) -> list[dict]:
    """Build one session dict per close date from raw closes.

    This is a minimal, auditable version: 1D and 1M vs RSP for the
    tape. Breadth / sector / industry / COT need their own sources
    (SPX constituents, sector ETF list, CFTC files) — see README.md.
    The front end already ships with sample sessions for
    2026-11-13 to 2026-11-20; this script appends new sessions in
    the same shape and never overwrites those samples.
    """
    if BENCHMARK not in closes:
        return []
    dates = sorted({d for rows in closes.values() for d, _ in rows})
    by_ticker = {
        t: {d: c for d, c in rows} for t, rows in closes.items()
    }
    sessions: list[dict] = []
    for i, d in enumerate(dates):
        if d not in by_ticker.get(BENCHMARK, {}):
            continue
        tape = []
        for ticker in TAPE:
            row = by_ticker.get(ticker, {})
            if d not in row or i == 0:
                continue
            prev = dates[i - 1]
            if prev not in row:
                continue
            one_d = pct(row[d], row[prev])
            # 1M = 21 sessions back, vs RSP over the same window
            j = max(0, i - SESSIONS_1M)
            d_1m = dates[j]
            if d_1m not in row or d_1m not in by_ticker[BENCHMARK]:
                continue
            ret_1m = pct(row[d], row[d_1m])
            bench_1m = pct(by_ticker[BENCHMARK][d], by_ticker[BENCHMARK][d_1m])
            rel_1m = None if ret_1m is None or bench_1m is None else round(ret_1m - bench_1m, 2)
            tape.append({
                "ticker": ticker,
                "close": round(row[d], 2),
                "session_pct": one_d,
                "rel_1m_rsp_pct": rel_1m,
                # ATR index needs a 14-day ATR; leave null until
                # scripts/compute_atr.py (or the front-end sample) fills it.
                "atr_index": None,
            })
        if len(tape) == len(TAPE):
            sessions.append({"close_date": d, "tape": tape})
    return sessions


def main() -> int:
    existing = {"as_of": None, "sessions": []}
    if DATA_PATH.exists():
        try:
            existing = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"WARNING: {DATA_PATH} is not valid JSON; starting fresh", file=sys.stderr)
    have = {s.get("close_date") for s in existing.get("sessions", [])}
    closes = fetch_closes()
    if not closes:
        print("No data fetched; leaving history.json unchanged.")
        return 0
    new_sessions = [s for s in build_sessions(closes) if s["close_date"] not in have]
    if not new_sessions:
        print("No new sessions to append.")
        return 0
    existing["sessions"] = sorted(
        existing.get("sessions", []) + new_sessions,
        key=lambda s: s.get("close_date", ""),
    )
    existing["as_of"] = existing["sessions"][-1]["close_date"]
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"Appended {len(new_sessions)} session(s); as_of={existing['as_of']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

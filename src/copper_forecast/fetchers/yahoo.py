"""Yahoo Finance market data fetcher."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from copper_forecast.fetchers import FetchedRecord, FetchResult

LB_TO_TON = 2204.6226218488


def _history(ticker: str, lookback_days: int) -> pd.DataFrame:
    frame = pd.DataFrame()
    for period in ("2y", "1y", "6mo", "3mo", "1mo"):
        if lookback_days > 365 and period in ("3mo", "1mo"):
            continue
        frame = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        if not frame.empty:
            break

    if frame.empty:
        period = "2y" if lookback_days > 365 else "1y"
        downloaded = yf.download(
            ticker,
            period=period,
            progress=False,
            auto_adjust=False,
        )
        if not downloaded.empty:
            frame = downloaded

    if frame.empty:
        return frame
    frame = frame.reset_index()
    date_col = "Date" if "Date" in frame.columns else frame.columns[0]
    frame["Date"] = pd.to_datetime(frame[date_col]).dt.tz_localize(None)
    return frame


def fetch_yahoo(
    indicators_cfg: dict,
    lookback_days: int,
) -> FetchResult:
    result = FetchResult()
    for indicator, cfg in indicators_cfg.items():
        ticker = cfg["ticker"]
        try:
            frame = _history(ticker, lookback_days)
            if frame.empty:
                result.errors.append(f"yahoo:{indicator}: no data for {ticker}")
                continue

            cutoff = datetime.now() - timedelta(days=lookback_days)
            for _, row in frame.iterrows():
                row_date = row["Date"].date()
                if row_date < cutoff.date():
                    continue
                value = float(row["Close"])
                if cfg.get("transform") == "comex_lb_to_usd_ton":
                    value = value * LB_TO_TON

                result.records.append(
                    FetchedRecord(
                        date=row_date,
                        indicator=indicator,
                        value=round(value, 4),
                        unit=cfg["unit"],
                        source=cfg["source"],
                        source_url=cfg["source_url"],
                        frequency=cfg["frequency"],
                        confidence=cfg["confidence"],
                        note=cfg.get("note", ""),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"yahoo:{indicator}: {exc}")
    return result

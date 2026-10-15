"""Yahoo Finance market data fetcher."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

from copper_forecast.fetchers import FetchedRecord, FetchResult

LB_TO_TON = 2204.6226218488
OUTLIER_DAILY_PCT = 0.08
# First session continued from Eastmoney after Yahoo settlements. Do not splice
# this quote over earlier Yahoo rows; the two closes are not identical.
EASTMONEY_CUTOVER = date(2026, 9, 8)
_EASTMONEY_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_EASTMONEY_FALLBACK = {
    "HG=F": {
        "secid": "101.HG00Y",
        "source": "东方财富-COMEX铜",
        "source_url": "https://quote.eastmoney.com/globalfuture/HG00Y.html",
        "scale": LB_TO_TON,
        "note": "COMEX HG00Y close, USD/lb converted to USD/ton; Yahoo fallback",
    },
    "DX-Y.NYB": {
        "secid": "100.UDI",
        "source": "东方财富-美元指数",
        "source_url": "https://quote.eastmoney.com/gb/zsUDI.html",
        "scale": 1.0,
        "note": "Eastmoney UDI close; Yahoo fallback",
    },
}


def _smooth_daily_outliers(
    records: list[FetchedRecord],
    threshold: float = OUTLIER_DAILY_PCT,
    max_passes: int = 10,
) -> list[FetchedRecord]:
    """Replace single-day spikes (e.g. COMEX roll bad ticks) via neighbor averaging."""
    if len(records) < 2:
        return records

    ordered = sorted(records, key=lambda r: r.date)
    values = [float(r.value) for r in ordered]

    for _ in range(max_passes):
        changed = False
        for i in range(1, len(values)):
            prev = values[i - 1]
            if not prev:
                continue
            if abs((values[i] - prev) / prev) <= threshold:
                continue
            if i + 1 < len(values):
                values[i] = round((prev + values[i + 1]) / 2, 4)
            else:
                values[i] = round(prev, 4)
            changed = True
        if not changed:
            break

    smoothed: list[FetchedRecord] = []
    for rec, new_val in zip(ordered, values):
        old_val = float(rec.value)
        if old_val == new_val:
            smoothed.append(rec)
            continue
        note = rec.note or ""
        tag = "Yahoo outlier smoothed"
        if tag not in note:
            note = f"{note}; {tag}" if note else tag
        smoothed.append(
            FetchedRecord(
                date=rec.date,
                indicator=rec.indicator,
                value=new_val,
                unit=rec.unit,
                source=rec.source,
                source_url=rec.source_url,
                frequency=rec.frequency,
                confidence=rec.confidence,
                updated_at=rec.updated_at,
                note=note,
            )
        )
    return smoothed


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
                _fill_eastmoney_fallback(
                    result, indicator, cfg, lookback_days, "no data for " + ticker
                )
                continue

            cutoff = datetime.now() - timedelta(days=lookback_days)
            indicator_records: list[FetchedRecord] = []
            for _, row in frame.iterrows():
                row_date = row["Date"].date()
                if row_date < cutoff.date():
                    continue
                value = float(row["Close"])
                if cfg.get("transform") == "comex_lb_to_usd_ton":
                    value = value * LB_TO_TON

                indicator_records.append(
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
            result.records.extend(_smooth_daily_outliers(indicator_records))
        except Exception as exc:  # noqa: BLE001
            _fill_eastmoney_fallback(result, indicator, cfg, lookback_days, str(exc))
    return result


def records_from_eastmoney_klines(
    lines: list[str],
    *,
    indicator: str,
    unit: str,
    source: str,
    source_url: str,
    frequency: str,
    confidence: str,
    note: str,
    scale: float,
    not_before: date = EASTMONEY_CUTOVER,
    before: date | None = None,
) -> list[FetchedRecord]:
    """Turn Eastmoney daily klines into records. `before` defaults to local today."""
    cutoff = before or date.today()
    records: list[FetchedRecord] = []
    for line in lines:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        row_date = date.fromisoformat(parts[0])
        if row_date < not_before or row_date >= cutoff:
            continue
        close = float(parts[2])
        records.append(
            FetchedRecord(
                date=row_date,
                indicator=indicator,
                value=round(close * scale, 4),
                unit=unit,
                source=source,
                source_url=source_url,
                frequency=frequency,
                confidence=confidence,
                note=note,
            )
        )
    return records


def _eastmoney_klines(secid: str, limit: int) -> list[str]:
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": str(limit),
    }
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "Mozilla/5.0"
    last_error: Exception | None = None
    for _ in range(3):
        try:
            response = session.get(_EASTMONEY_KLINE, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            lines = (payload.get("data") or {}).get("klines") or []
            if not lines:
                raise ValueError(f"eastmoney empty kline for {secid}")
            return list(lines)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(last_error)


def fetch_eastmoney_quote_fallback(
    indicator: str,
    cfg: dict,
    lookback_days: int,
    *,
    before: date | None = None,
) -> FetchResult:
    """Fill HG=F / DX-Y.NYB from Eastmoney when Yahoo is unavailable."""
    result = FetchResult()
    spec = _EASTMONEY_FALLBACK.get(cfg.get("ticker", ""))
    if spec is None:
        return result
    limit = min(60, max(lookback_days, 30))
    try:
        lines = _eastmoney_klines(spec["secid"], limit)
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"eastmoney:{indicator}: {exc}")
        return result
    result.records.extend(
        records_from_eastmoney_klines(
            lines,
            indicator=indicator,
            unit=cfg["unit"],
            source=spec["source"],
            source_url=spec["source_url"],
            frequency=cfg["frequency"],
            confidence=cfg["confidence"],
            note=spec["note"],
            scale=spec["scale"],
            before=before,
        )
    )
    if not result.records:
        result.errors.append(f"eastmoney:{indicator}: no bars in range")
    return result


def _fill_eastmoney_fallback(
    result: FetchResult,
    indicator: str,
    cfg: dict,
    lookback_days: int,
    yahoo_error: str,
) -> None:
    fallback = fetch_eastmoney_quote_fallback(indicator, cfg, lookback_days)
    if fallback.records:
        result.records.extend(fallback.records)
        result.warnings.append(
            f"yahoo:{indicator}: {yahoo_error}; filled from Eastmoney"
        )
        return
    result.errors.append(f"yahoo:{indicator}: {yahoo_error}")
    result.errors.extend(fallback.errors)

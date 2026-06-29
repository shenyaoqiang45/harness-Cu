"""Derived indicators from fetched market data."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import akshare as ak
import pandas as pd
import yfinance as yf

from copper_forecast.fetchers import FetchedRecord, FetchResult
from copper_forecast.fetchers.yahoo import LB_TO_TON

LOOKBACK = 120


def _latest_fx() -> float:
    frame = yf.Ticker("USDCNY=X").history(period="10d")
    if frame.empty:
        return 7.2
    return float(frame["Close"].iloc[-1])


def shfe_lme_premium(lookback_days: int = LOOKBACK) -> FetchResult:
    result = FetchResult()
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")
        shfe = ak.futures_main_sina(symbol="CU0", start_date=start, end_date=end)
        comex = yf.Ticker("HG=F").history(
            start=(datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        )
        if shfe.empty or comex.empty:
            result.errors.append("derived:spot_premium: missing SHFE or COMEX history")
            return result

        shfe = shfe.rename(columns={"日期": "date", "收盘价": "shfe_close"})
        shfe["date"] = pd.to_datetime(shfe["date"])
        comex = comex.reset_index()
        comex["Date"] = pd.to_datetime(comex["Date"]).dt.tz_localize(None)
        fx = _latest_fx()

        merged = pd.merge_asof(
            shfe.sort_values("date"),
            comex[["Date", "Close"]].sort_values("Date"),
            left_on="date",
            right_on="Date",
            direction="backward",
        )
        merged["lme_usd_ton"] = merged["Close"] * LB_TO_TON
        merged["shfe_usd_ton"] = merged["shfe_close"] / fx
        merged["premium"] = merged["shfe_usd_ton"] - merged["lme_usd_ton"]

        for _, row in merged.dropna(subset=["premium"]).iterrows():
            result.records.append(
                FetchedRecord(
                    date=row["date"].date(),
                    indicator="spot_premium",
                    value=round(float(row["premium"]), 2),
                    unit="USD/ton",
                    source="derived",
                    source_url="",
                    frequency="daily",
                    confidence="C",
                    note="SHFE CU0 vs COMEX HG=F after USDCNY conversion",
                )
            )
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"derived:spot_premium: {exc}")
    return result


def premium_to_curve(existing: list[FetchedRecord], lookback_days: int = LOOKBACK) -> FetchResult:
    result = FetchResult()
    premiums = sorted(
        [r for r in existing if r.indicator == "spot_premium"],
        key=lambda r: r.date,
    )
    if not premiums:
        result.warnings.append("derived:term_structure: no spot_premium available")
        return result

    for rec in premiums[-lookback_days:]:
        label = "backwardation" if float(rec.value) > 0 else "contango"
        result.records.append(
            FetchedRecord(
                date=rec.date,
                indicator="term_structure",
                value=label,
                unit="label",
                source="derived",
                source_url="",
                frequency="daily",
                confidence="C",
                note="Inferred from SHFE-LME premium sign",
            )
        )
    return result


def composite_global_pmi(existing: list[FetchedRecord]) -> FetchResult:
    """Blend China + US ISM (if present) into a simple global PMI proxy."""
    result = FetchResult()
    china = {r.date: float(r.value) for r in existing if r.indicator == "china_pmi"}
    usm = {r.date: float(r.value) for r in existing if r.indicator == "us_ism_manufacturing"}
    if not china:
        result.warnings.append("derived:global_manufacturing_pmi: no china_pmi")
        return result

    for dt, cpmi in sorted(china.items()):
        us_val = usm.get(dt)
        if us_val is None:
            # nearest US month
            us_candidates = [d for d in usm if abs((d.year - dt.year) * 12 + d.month - dt.month) <= 1]
            us_val = usm[us_candidates[0]] if us_candidates else None
        value = cpmi if us_val is None else (cpmi + us_val) / 2
        result.records.append(
            FetchedRecord(
                date=dt,
                indicator="global_manufacturing_pmi",
                value=round(value, 2),
                unit="index",
                source="derived",
                source_url="",
                frequency="monthly",
                confidence="C",
                note="Average of China PMI and US ISM when both exist",
            )
        )
    return result


def fetch_derived(
    indicators_cfg: dict,
    existing: list[FetchedRecord],
    lookback_days: int,
) -> FetchResult:
    result = FetchResult()
    for indicator, cfg in indicators_cfg.items():
        func = cfg.get("func")
        if func == "shfe_lme_premium":
            part = shfe_lme_premium(lookback_days)
        elif func == "premium_to_curve":
            part = premium_to_curve(existing + result.records, lookback_days)
        elif func == "composite_global_pmi":
            part = composite_global_pmi(existing + result.records)
        else:
            result.errors.append(f"derived:{indicator}: unknown func {func}")
            continue
        result.extend(part)
    return result

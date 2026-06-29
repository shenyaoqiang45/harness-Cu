"""CME Group COMEX copper warehouse stocks fetcher."""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from copper_forecast.fetchers import FetchedRecord, FetchResult

CME_COPPER_STOCKS_URL = "https://www.cmegroup.com/delivery_reports/Copper_Stocks.xls"
SHORT_TON_TO_METRIC_TON = 0.90718474
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def parse_cme_copper_stocks_xls(content: bytes) -> tuple[date, float]:
    """Return activity date and total copper stocks in metric tons."""
    frame = pd.read_excel(io.BytesIO(content), header=None)
    activity_date: date | None = None
    total_short_tons: float | None = None

    for _, row in frame.iterrows():
        cells = [str(x) for x in row if pd.notna(x)]
        line = " ".join(cells)
        if "Activity Date:" in line:
            match = re.search(r"Activity Date:\s*(\d{1,2}/\d{1,2}/\d{4})", line)
            if match:
                activity_date = pd.to_datetime(match.group(1)).date()
        if cells and cells[0] == "TOTAL COPPER":
            numbers = [float(x) for x in cells[1:] if re.fullmatch(r"\d+(?:\.\d+)?", str(x))]
            if numbers:
                total_short_tons = numbers[-1]

    if activity_date is None or total_short_tons is None:
        raise ValueError("CME copper stocks report missing activity date or TOTAL COPPER row")

    metric_tons = total_short_tons * SHORT_TON_TO_METRIC_TON
    return activity_date, round(metric_tons, 2)


def fetch_comex(indicators_cfg: dict, lookback_days: int) -> FetchResult:
    result = FetchResult()
    cutoff = (datetime.now() - timedelta(days=lookback_days)).date()

    try:
        response = requests.get(CME_COPPER_STOCKS_URL, headers=_HEADERS, timeout=30)
        response.raise_for_status()
        activity_date, metric_tons = parse_cme_copper_stocks_xls(response.content)
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"cme:comex_inventory: {exc}")
        return result

    if activity_date < cutoff:
        result.warnings.append(
            f"cme:comex_inventory: activity date {activity_date} older than lookback cutoff"
        )

    cfg = indicators_cfg.get("comex_inventory", {})
    result.records.append(
        FetchedRecord(
            date=activity_date,
            indicator="comex_inventory",
            value=metric_tons,
            unit=cfg.get("unit", "ton"),
            source=cfg.get("source", "CME Group"),
            source_url=cfg.get("source_url", CME_COPPER_STOCKS_URL),
            frequency=cfg.get("frequency", "daily"),
            confidence=cfg.get("confidence", "A"),
            note=cfg.get(
                "note",
                "COMEX high-grade copper warehouse stocks; converted from short tons to metric tons",
            ),
        )
    )
    return result

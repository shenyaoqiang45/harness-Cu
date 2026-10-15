"""COMEX copper warehouse stocks from MetalCharts.

MetalCharts keeps the CME daily depository report after CME overwrites the
public file. The total is short tons and equals registered plus eligible.
The Vault Report quotes that same latest total; it is a cross-check, not the
history source. Days where the split is missing are a different figure and
are left out, including the smaller series mixed in from March through May 2026.
"""

from __future__ import annotations

from datetime import date

import requests

from copper_forecast.fetchers.comex import SHORT_TON_TO_METRIC_TON

COPPER_PAGE_URL = "https://metalcharts.org/comex/copper"
TOKEN_URL = "https://metalcharts.org/api/security/token"
INVENTORY_URL = "https://metalcharts.org/api/comex/inventory"
_MAX_GAP_DAYS = 5
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": COPPER_PAGE_URL,
    "Origin": "https://metalcharts.org",
}


def short_tons_to_metric_tons(short_tons: float) -> float:
    return round(float(short_tons) * SHORT_TON_TO_METRIC_TON, 2)


def parse_comex_inventory_payload(payload: dict, *, max_gap_days: int = _MAX_GAP_DAYS) -> dict[date, float]:
    """Return metric tons for the trailing run of complete warehouse totals."""
    short_tons: dict[date, float] = {}
    for row in payload.get("data") or []:
        total = row.get("total")
        registered = row.get("registered")
        eligible = row.get("eligible")
        if total is None or registered is None or eligible is None:
            continue
        if registered + eligible != total:
            continue
        short_tons[date.fromisoformat(str(row["date"])[:10])] = float(total)
    return {
        day: short_tons_to_metric_tons(value)
        for day, value in _trailing_continuous(short_tons, max_gap_days).items()
    }


def _trailing_continuous(stocks: dict[date, float], max_gap_days: int) -> dict[date, float]:
    """Keep the segment after the last hole larger than max_gap_days."""
    days = sorted(stocks)
    start = 0
    for index in range(1, len(days)):
        if (days[index] - days[index - 1]).days > max_gap_days:
            start = index
    return {day: stocks[day] for day in days[start:]}


def fetch_metalcharts_comex() -> dict[date, float]:
    """Download one year of COMEX copper warehouse stocks, in metric tons."""
    session = requests.Session()
    session.headers.update(_HEADERS)
    page = session.get(COPPER_PAGE_URL, timeout=30)
    page.raise_for_status()
    token_response = session.get(TOKEN_URL, timeout=30)
    token_response.raise_for_status()
    token = token_response.json().get("token")
    if not token:
        raise ValueError("MetalCharts token response had no token")
    session.headers["X-MC-Token"] = token
    response = session.get(
        INVENTORY_URL,
        params={"symbol": "HG", "range": "1Y"},
        timeout=30,
    )
    response.raise_for_status()
    stocks = parse_comex_inventory_payload(response.json())
    if not stocks:
        raise ValueError("MetalCharts COMEX copper inventory series was empty")
    return stocks

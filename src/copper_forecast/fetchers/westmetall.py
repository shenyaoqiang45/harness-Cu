"""LME copper warehouse stocks from the Westmetall daily table."""

from __future__ import annotations

import re
from datetime import date

import requests

_MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
_ROW = re.compile(
    r"<td[^>]*>\s*(\d{1,2})\.\s+([A-Za-z]+)\s+(\d{4})\s*</td>\s*"
    r"<td[^>]*>\s*([\d,]+)\s*</td>",
    re.IGNORECASE,
)
_URL = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_stock&year={year}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def parse_lme_copper_stock_html(html: str) -> dict[date, float]:
    """Parse the LME copper stock column. Later rows do not overwrite earlier ones."""
    stocks: dict[date, float] = {}
    for day, month, year, raw in _ROW.findall(html):
        month_num = _MONTHS.get(month)
        if month_num is None:
            continue
        stocks.setdefault(
            date(int(year), month_num, int(day)),
            float(raw.replace(",", "")),
        )
    return stocks


def fetch_westmetall_lme(years: list[int] | None = None) -> dict[date, float]:
    """Download one or more yearly Westmetall tables. Default is this year and the last."""
    if years is None:
        today = date.today()
        years = [today.year, today.year - 1]
    stocks: dict[date, float] = {}
    for year in years:
        response = requests.get(_URL.format(year=year), headers=_HEADERS, timeout=30)
        response.raise_for_status()
        stocks.update(parse_lme_copper_stock_html(response.text))
    if not stocks:
        raise ValueError("Westmetall LME copper stock table was empty")
    return stocks

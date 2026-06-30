"""Tests for inventory monitor filtering."""

from datetime import date, datetime

from copper_forecast.fetchers import FetchedRecord
from copper_forecast.inventory_monitor import (
    MONITOR_SOURCE,
    MonitorState,
    filter_inventory_records,
)


def _inv(day: str, value: float, source: str) -> FetchedRecord:
    return FetchedRecord(
        date=date.fromisoformat(day),
        indicator="shfe_inventory",
        value=value,
        unit="ton",
        source=source,
        source_url="",
        frequency="daily",
        confidence="B",
    )


def test_filter_inventory_keeps_only_monitor_inside_cutover():
    monitor = MonitorState(cutover=date(2026, 4, 1), source_path=__import__("pathlib").Path("."))
    records = [
        _inv("2026-03-31", 100.0, MONITOR_SOURCE),
        _inv("2026-04-01", 110.0, MONITOR_SOURCE),
        _inv("2026-06-30", 120.0, "东方财富-SHFE"),
        _inv("2026-06-29", 115.0, MONITOR_SOURCE),
    ]
    filtered = filter_inventory_records(records, monitor)
    assert len(filtered) == 2
    assert filtered[0].date == date(2026, 4, 1)
    assert filtered[1].date == date(2026, 6, 29)

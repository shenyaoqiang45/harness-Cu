"""Tests for Yahoo price outlier smoothing."""

from datetime import date

from copper_forecast.fetchers import FetchedRecord
from copper_forecast.fetchers.yahoo import _smooth_daily_outliers


def _rec(day: str, value: float) -> FetchedRecord:
    return FetchedRecord(
        date=date.fromisoformat(day),
        indicator="lme_copper_price",
        value=value,
        unit="USD/ton",
        source="Yahoo Finance",
        source_url="",
        frequency="daily",
        confidence="B",
    )


def test_smooth_daily_outliers_fixes_spike_and_roll_gap():
    records = [
        _rec("2025-07-07", 10988.9413),
        _rec("2025-07-08", 12445.0947),
        _rec("2025-07-09", 12000.8633),
        _rec("2025-07-30", 12279.7484),
        _rec("2025-07-31", 9547.1185),
        _rec("2025-08-01", 9727.8971),
        _rec("2025-08-04", 9733.4054),
    ]
    smoothed = _smooth_daily_outliers(records)
    values = [float(r.value) for r in smoothed]
    assert values[1] == 11494.9023
    for i in range(1, len(values)):
        prev, curr = values[i - 1], values[i]
        assert abs((curr - prev) / prev) <= 0.08

"""Tests for Yahoo price outlier smoothing."""

from datetime import date

from copper_forecast.fetchers import FetchedRecord
from copper_forecast.fetchers.yahoo import (
    LB_TO_TON,
    _smooth_daily_outliers,
    records_from_eastmoney_klines,
)


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


def test_eastmoney_fallback_converts_copper_and_drops_partial_session():
    lines = [
        "2026-09-07,6.6690,6.7040,6.7340,6.6360,14681,0.0000",
        "2026-09-25,6.7805,6.7790,6.7970,6.7230,25665,0.0000",
        "2026-10-14,6.7270,6.6150,6.7890,6.5990,43246,0.0000",
        "2026-10-15,6.6330,6.6110,6.6330,6.6055,3089,0.0000",
    ]
    records = records_from_eastmoney_klines(
        lines,
        indicator="lme_copper_price",
        unit="USD/ton",
        source="东方财富-COMEX铜",
        source_url="https://quote.eastmoney.com/globalfuture/HG00Y.html",
        frequency="daily",
        confidence="B",
        note="fallback",
        scale=LB_TO_TON,
        before=date(2026, 10, 15),
    )
    by_day = {r.date.isoformat(): r.value for r in records}
    assert "2026-09-07" not in by_day
    assert "2026-10-15" not in by_day
    assert by_day["2026-09-25"] == round(6.7790 * LB_TO_TON, 4)
    assert by_day["2026-10-14"] == round(6.6150 * LB_TO_TON, 4)

"""Westmetall parsing and monitor-table extension."""

from datetime import date

from copper_forecast.fetchers import FetchedRecord
from copper_forecast.fetchers.comex import SHORT_TON_TO_METRIC_TON
from copper_forecast.fetchers.metalcharts import parse_comex_inventory_payload, short_tons_to_metric_tons
from copper_forecast.fetchers.westmetall import parse_lme_copper_stock_html
from copper_forecast.inventory_refresh import extend_monitor_rows, retire_mismatched_inventory


def _row(day: str, lme: int, shfe: int, comex: int) -> dict:
    return {
        "日期": day,
        "LME铜库存(公吨)": str(lme),
        "LME日变化": "0",
        "SHFE铜库存(吨)": str(shfe),
        "SHFE日变化": "0",
        "COMEX铜库存(公吨)": str(comex),
        "COMEX日变化": "0",
        "全球总库存(公吨)": str(lme + shfe + comex),
        "全球总库存变化": "0",
    }


def test_parse_westmetall_stock_cell():
    html = """
    <tr>
    <td >13. July 2026</td>
    <td >305,200</td>
    <td >13,460.50</td>
    </tr>
    <tr>
    <td >14. October 2026</td>
    <td >228,000</td>
    <td >14,751.00</td>
    </tr>
    """
    stocks = parse_lme_copper_stock_html(html)
    assert stocks[date(2026, 7, 13)] == 305200
    assert stocks[date(2026, 10, 14)] == 228000


def test_replace_when_scale_differs_and_fills_the_weekend():
    rows = [
        _row("2026-07-10", 100, 50, 80),
        _row("2026-07-11", 101, 50, 80),
        _row("2026-07-13", 121, 50, 80),
    ]
    updated, notes = extend_monitor_rows(
        rows,
        {
            "lme_inventory": {
                date(2026, 7, 10): 300,
                date(2026, 7, 13): 305,
                date(2026, 7, 14): 303,
            }
        },
    )
    by_day = {row["日期"]: row for row in updated}
    assert any("replaced with the live series" in note for note in notes)
    assert by_day["2026-07-10"]["LME铜库存(公吨)"] == "300"
    assert by_day["2026-07-11"]["LME铜库存(公吨)"] == "300"
    assert by_day["2026-07-13"]["LME铜库存(公吨)"] == "305"
    assert by_day["2026-07-14"]["LME铜库存(公吨)"] == "303"
    assert by_day["2026-07-14"]["LME日变化"] == "-2"
    assert by_day["2026-07-10"]["SHFE铜库存(吨)"] == "50"
    assert by_day["2026-07-14"]["SHFE铜库存(吨)"] == ""
    assert by_day["2026-07-14"]["全球总库存(公吨)"] == ""


def test_append_when_overlap_matches():
    rows = [_row("2026-07-13", 305, 50, 80)]
    updated, notes = extend_monitor_rows(
        rows,
        {"lme_inventory": {date(2026, 7, 13): 305, date(2026, 7, 14): 303}},
    )
    assert any("appended after 2026-07-13" in note for note in notes)
    assert updated[0]["LME铜库存(公吨)"] == "305"
    assert updated[1]["日期"] == "2026-07-14"
    assert updated[1]["LME铜库存(公吨)"] == "303"


def _stored(indicator: str, day: str, value: float) -> FetchedRecord:
    return FetchedRecord(
        date=date.fromisoformat(day),
        indicator=indicator,
        value=value,
        unit="ton",
        source="金属库存监控",
        source_url="",
        frequency="daily",
        confidence="B",
    )


def test_retire_drops_a_different_scale_and_keeps_a_match():
    existing = [
        _stored("lme_inventory", "2026-07-13", 121408),
        _stored("comex_inventory", "2026-07-13", 167775),
    ]
    incoming = [
        _stored("lme_inventory", "2026-07-13", 305200),
        _stored("lme_inventory", "2026-10-14", 228000),
        _stored("comex_inventory", "2026-07-13", 167775),
    ]
    kept, notes = retire_mismatched_inventory(existing, incoming)
    assert [rec.indicator for rec in kept] == ["comex_inventory"]
    assert any(note.startswith("lme_inventory: retired") for note in notes)


def test_metalcharts_keeps_the_warehouse_total_and_drops_the_broken_stretch():
    payload = {
        "data": [
            {"date": "2026-03-05", "total": 597938, "registered": 376825, "eligible": 221113},
            {"date": "2026-03-06", "total": 49376, "registered": None, "eligible": None},
            {"date": "2026-06-12", "total": 650412, "registered": 432757, "eligible": 217655},
            {"date": "2026-06-16", "total": 650631, "registered": 433383, "eligible": 217248},
            {"date": "2026-06-17", "total": 650414, "registered": 1, "eligible": 1},
        ]
    }
    stocks = parse_comex_inventory_payload(payload)
    assert set(stocks) == {date(2026, 6, 12), date(2026, 6, 16)}
    assert stocks[date(2026, 6, 12)] == short_tons_to_metric_tons(650412)
    latest = parse_comex_inventory_payload(
        {"data": [{"date": "2026-10-14", "total": 788272, "registered": 471249, "eligible": 317023}]}
    )
    assert latest[date(2026, 10, 14)] == round(788272 * SHORT_TON_TO_METRIC_TON, 2)


def test_comex_replace_clears_the_old_series_before_the_new_origin():
    rows = [
        _row("2026-06-11", 100, 50, 167775),
        _row("2026-06-12", 100, 50, 167000),
    ]
    updated, notes = extend_monitor_rows(
        rows,
        {"comex_inventory": {date(2026, 6, 12): 590000, date(2026, 6, 15): 590100}},
    )
    by_day = {row["日期"]: row for row in updated}
    assert any("comex_inventory: monitor scale differs" in note for note in notes)
    assert by_day["2026-06-11"]["COMEX铜库存(公吨)"] == ""
    assert by_day["2026-06-11"]["全球总库存(公吨)"] == ""
    assert by_day["2026-06-12"]["COMEX铜库存(公吨)"] == "590000"
    assert by_day["2026-06-12"]["LME铜库存(公吨)"] == "100"


def test_no_overlap_does_not_splice_a_later_print():
    rows = [_row("2026-07-13", 100, 50, 168)]
    updated, notes = extend_monitor_rows(
        rows,
        {"comex_inventory": {date(2026, 10, 14): 600}},
    )
    assert len(updated) == 1
    assert updated[0]["COMEX铜库存(公吨)"] == "168"
    assert any("comex_inventory: no overlapping date" in note for note in notes)

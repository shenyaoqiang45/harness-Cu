"""Westmetall parsing and monitor-table extension."""

from datetime import date

from copper_forecast.fetchers import FetchedRecord
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


def test_no_overlap_does_not_splice_a_later_print():
    rows = [_row("2026-07-13", 100, 50, 168)]
    updated, notes = extend_monitor_rows(
        rows,
        {"comex_inventory": {date(2026, 10, 14): 600}},
    )
    assert len(updated) == 1
    assert updated[0]["COMEX铜库存(公吨)"] == "168"
    assert any("comex_inventory: no overlapping date" in note for note in notes)

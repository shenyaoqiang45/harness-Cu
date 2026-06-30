"""Tests for metal inventory monitor import."""

from pathlib import Path

from copper_forecast.inventory_monitor import build_import_rows


def test_build_import_rows_maps_three_exchanges():
    source = Path("data/raw/metal_inventory_monitor.csv")
    rows = build_import_rows(source)
    dates = {row["date"] for row in rows}
    assert len(rows) == len(dates) * 3
    indicators = {row["indicator"] for row in rows}
    assert indicators == {"lme_inventory", "shfe_inventory", "comex_inventory"}

    sample = next(
        row for row in rows if row["date"] == "2026-06-29" and row["indicator"] == "comex_inventory"
    )
    assert sample["value"] == 174033.0
    assert sample["unit"] == "ton"

"""Extend metal_inventory_monitor.csv from public inventory series.

The monitor file is the series the pipeline stores. A public series is appended
only when it agrees with the file on overlapping dates. When the levels are a
different definition, that column is replaced from the public series so the
file does not jump from one definition to another on a single day.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from copper_forecast.inventory_monitor import monitor_path

VALUE_COLUMNS = {
    "lme_inventory": "LME铜库存(公吨)",
    "shfe_inventory": "SHFE铜库存(吨)",
    "comex_inventory": "COMEX铜库存(公吨)",
}
CHANGE_COLUMNS = {
    "lme_inventory": "LME日变化",
    "shfe_inventory": "SHFE日变化",
    "comex_inventory": "COMEX日变化",
}
GLOBAL_VALUE = "全球总库存(公吨)"
GLOBAL_CHANGE = "全球总库存变化"
DATE_COL = "日期"
_SCALE_TOLERANCE = 0.15
_FILL_GAP_DAYS = 4


def _parse_num(raw: str | None) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    return float(text)


def _fmt(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-6:
        return str(int(rounded))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _row_date(row: dict) -> date:
    return date.fromisoformat(row[DATE_COL].strip()[:10])


def extend_monitor_rows(
    rows: list[dict],
    live: dict[str, dict[date, float]],
    *,
    tolerance: float = _SCALE_TOLERANCE,
) -> tuple[list[dict], list[str]]:
    """Return updated rows and one note per inventory column."""
    notes: list[str] = []
    if not rows:
        return rows, ["inventory monitor is empty"]

    original = [dict(row) for row in rows]
    file_dates = [_row_date(row) for row in rows]
    first, last = min(file_dates), max(file_dates)
    modes: dict[str, str] = {}

    for indicator, column in VALUE_COLUMNS.items():
        series = live.get(indicator) or {}
        if not series:
            modes[indicator] = "skip"
            notes.append(f"{indicator}: no live series, left unchanged")
            continue
        gaps: list[float] = []
        for row in original:
            current = _parse_num(row.get(column))
            day = _row_date(row)
            if current is None or current == 0 or day not in series:
                continue
            gaps.append(abs(series[day] - current) / abs(current))
        if not gaps:
            modes[indicator] = "skip"
            notes.append(f"{indicator}: no overlapping date, left unchanged")
            continue
        gap = _median(gaps)
        if gap <= tolerance:
            modes[indicator] = "append"
            notes.append(
                f"{indicator}: matches the monitor, appended after {last.isoformat()}"
            )
        else:
            modes[indicator] = "replace"
            notes.append(
                f"{indicator}: monitor scale differs (median gap {gap:.0%}), "
                "replaced with the live series"
            )

    fieldnames = list(rows[0].keys())
    existing = set(file_dates)
    for indicator, mode in modes.items():
        if mode == "skip":
            continue
        for day in live[indicator]:
            if day < first or day in existing:
                continue
            if mode == "append" and day <= last:
                continue
            blank = {name: "" for name in fieldnames}
            blank[DATE_COL] = day.isoformat()
            rows.append(blank)
            existing.add(day)
    rows.sort(key=_row_date)

    for indicator, mode in modes.items():
        if mode == "skip":
            continue
        column = VALUE_COLUMNS[indicator]
        series = live[indicator]
        origin = min(series)
        carried: float | None = None
        carried_on: date | None = None
        for row in rows:
            day = _row_date(row)
            if mode == "append" and day <= last:
                continue
            if mode == "replace" and day < origin:
                continue
            if day in series:
                row[column] = _fmt(series[day])
                carried = series[day]
                carried_on = day
            elif (
                carried is not None
                and carried_on is not None
                and 0 < (day - carried_on).days <= _FILL_GAP_DAYS
            ):
                row[column] = _fmt(carried)

    _recompute_changes(rows)
    return rows, notes


def _recompute_changes(rows: list[dict]) -> None:
    previous: dict[str, float | None] = {indicator: None for indicator in VALUE_COLUMNS}
    previous_global: float | None = None
    for row in rows:
        values: dict[str, float | None] = {}
        for indicator, column in VALUE_COLUMNS.items():
            value = _parse_num(row.get(column))
            values[indicator] = value
            change_col = CHANGE_COLUMNS[indicator]
            if value is None:
                row[change_col] = ""
            elif previous[indicator] is None:
                row[change_col] = "0"
            else:
                row[change_col] = _fmt(value - previous[indicator])
            if value is not None:
                previous[indicator] = value
        if all(value is not None for value in values.values()):
            total = sum(value for value in values.values() if value is not None)
            row[GLOBAL_VALUE] = _fmt(total)
            row[GLOBAL_CHANGE] = (
                "0" if previous_global is None else _fmt(total - previous_global)
            )
            previous_global = total
        else:
            row[GLOBAL_VALUE] = ""
            row[GLOBAL_CHANGE] = ""


def load_monitor_table(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
    return fields, rows


def save_monitor_table(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def extend_monitor_file(
    path: Path,
    live: dict[str, dict[date, float]],
    *,
    tolerance: float = _SCALE_TOLERANCE,
) -> list[str]:
    """Update the CSV in place when a column can be extended or replaced."""
    fields, rows = load_monitor_table(path)
    before = [dict(row) for row in rows]
    updated, notes = extend_monitor_rows(rows, live, tolerance=tolerance)
    if updated != before:
        save_monitor_table(path, fields, updated)
    return notes


def fetch_shfe_inventory() -> dict[date, float]:
    import akshare as ak
    import pandas as pd

    frame = ak.futures_inventory_em(symbol="沪铜")
    stocks: dict[date, float] = {}
    for _, row in frame.iterrows():
        value = row["库存"]
        if pd.isna(value):
            continue
        stocks[pd.to_datetime(row["日期"]).date()] = float(value)
    if not stocks:
        raise ValueError("SHFE copper inventory series was empty")
    return stocks


def fetch_comex_inventory() -> dict[date, float]:
    from copper_forecast.fetchers.comex import fetch_comex

    result = fetch_comex(
        {
            "comex_inventory": {
                "unit": "ton",
                "frequency": "daily",
                "source": "CME Group",
                "source_url": "https://www.cmegroup.com/delivery_reports/Copper_Stocks.xls",
                "confidence": "A",
            }
        },
        30,
    )
    if result.errors:
        raise RuntimeError(result.errors[0])
    stocks = {
        rec.date: float(rec.value)
        for rec in result.records
        if rec.indicator == "comex_inventory"
    }
    if not stocks:
        raise ValueError("CME copper inventory series was empty")
    return stocks


def retire_mismatched_inventory(
    existing: list,
    incoming: list,
    *,
    tolerance: float = _SCALE_TOLERANCE,
) -> tuple[list, list[str]]:
    """Drop stored inventory rows when incoming levels are a different series.

    Same-day anomaly protection would otherwise keep the old level and leave the
    new dates looking like a one-day crash or surge. Day-to-day jumps inside the
    incoming series are still checked later by validate_rows().
    """
    notes: list[str] = []
    drop: set[str] = set()
    for indicator in VALUE_COLUMNS:
        old_values = {
            rec.date: float(rec.value)
            for rec in existing
            if rec.indicator == indicator and isinstance(rec.value, (int, float)) and rec.value
        }
        new_values = {
            rec.date: float(rec.value)
            for rec in incoming
            if rec.indicator == indicator and isinstance(rec.value, (int, float)) and rec.value
        }
        gaps = [
            abs(new_values[day] - old) / abs(old)
            for day, old in old_values.items()
            if day in new_values
        ]
        if gaps and _median(gaps) > tolerance:
            drop.add(indicator)
            notes.append(
                f"{indicator}: retired stored levels that use a different scale"
            )
    if not drop:
        return existing, notes
    return [rec for rec in existing if rec.indicator not in drop], notes


def refresh_inventory_monitor(project_root: Path, configured: str | None = None) -> list[str]:
    """Refresh the monitor CSV. Missing file is a no-op. Fetch errors stay on that column."""
    path = monitor_path(project_root, configured)
    if not path.exists():
        return []

    live: dict[str, dict[date, float]] = {}
    notes: list[str] = []
    failed: set[str] = set()
    for indicator, fetcher in (
        ("lme_inventory", _fetch_lme),
        ("shfe_inventory", fetch_shfe_inventory),
        ("comex_inventory", fetch_comex_inventory),
    ):
        try:
            live[indicator] = fetcher()
        except Exception as exc:  # noqa: BLE001
            failed.add(indicator)
            notes.append(f"{indicator}: live fetch failed ({exc})")
    for note in extend_monitor_file(path, live):
        indicator = note.split(":", 1)[0]
        if indicator in failed and "no live series" in note:
            continue
        notes.append(note)
    return notes


def _fetch_lme() -> dict[date, float]:
    from copper_forecast.fetchers.westmetall import fetch_westmetall_lme

    return fetch_westmetall_lme()

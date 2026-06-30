"""Sync exchange inventory from metal_inventory_monitor.csv."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from copper_forecast.fetchers import FetchedRecord

MONITOR_SOURCE = "金属库存监控"
DEFAULT_MONITOR_PATH = Path("data/raw/metal_inventory_monitor.csv")
DEFAULT_MANUAL_PATH = Path("data/raw/manual_indicators.csv")

COLUMN_MAP = {
    "LME铜库存(公吨)": "lme_inventory",
    "SHFE铜库存(吨)": "shfe_inventory",
    "COMEX铜库存(公吨)": "comex_inventory",
}

INVENTORY_INDICATORS = frozenset(COLUMN_MAP.values())

CSV_FIELDS = [
    "date",
    "indicator",
    "value",
    "unit",
    "source",
    "source_url",
    "updated_at",
    "frequency",
    "confidence",
    "note",
]


@dataclass(frozen=True)
class MonitorState:
    cutover: date
    source_path: Path


def monitor_path(project_root: Path, configured: str | None = None) -> Path:
    rel = Path(configured or DEFAULT_MONITOR_PATH)
    return rel if rel.is_absolute() else project_root / rel


def monitor_cutover(source: Path) -> date:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        dates = [row["日期"].strip()[:10] for row in csv.DictReader(handle) if row.get("日期")]
    if not dates:
        raise ValueError(f"No dates in {source}")
    return date.fromisoformat(min(dates))


def build_import_rows(source: Path) -> list[dict]:
    updated_at = datetime.now().isoformat(timespec="seconds")
    imported: list[dict] = []

    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            day = row["日期"].strip()[:10]
            for col, indicator in COLUMN_MAP.items():
                raw = row.get(col, "").strip()
                if not raw:
                    continue
                imported.append(
                    {
                        "date": day,
                        "indicator": indicator,
                        "value": float(raw),
                        "unit": "ton",
                        "source": MONITOR_SOURCE,
                        "source_url": "",
                        "updated_at": updated_at,
                        "frequency": "daily",
                        "confidence": "B",
                        "note": f"from {source.name}",
                    }
                )

    imported.sort(key=lambda r: (r["indicator"], r["date"]))
    return imported


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def merge_into_manual(manual_path: Path, inventory_rows: list[dict]) -> None:
    """Replace all manual inventory rows with monitor import."""
    existing: list[dict] = []
    if manual_path.exists():
        with manual_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["indicator"] in INVENTORY_INDICATORS:
                    continue
                existing.append(row)

    merged = existing + inventory_rows
    merged.sort(key=lambda r: (r["indicator"], r["date"]))
    write_csv(manual_path, merged)


def sync_monitor_to_manual(project_root: Path, configured_path: str | None = None) -> MonitorState | None:
    """Import monitor CSV into manual_indicators when present."""
    source = monitor_path(project_root, configured_path)
    if not source.exists():
        return None

    manual_path = project_root / DEFAULT_MANUAL_PATH
    rows = build_import_rows(source)
    merge_into_manual(manual_path, rows)
    return MonitorState(cutover=monitor_cutover(source), source_path=source)


def filter_inventory_records(
    records: list[FetchedRecord],
    monitor: MonitorState | None,
) -> list[FetchedRecord]:
    """Keep only monitor inventory inside cutover window when monitor is active."""
    if monitor is None:
        return records

    kept: list[FetchedRecord] = []
    for rec in records:
        if rec.indicator not in INVENTORY_INDICATORS:
            kept.append(rec)
            continue
        if rec.date < monitor.cutover:
            continue
        if rec.source != MONITOR_SOURCE:
            continue
        kept.append(rec)
    return kept

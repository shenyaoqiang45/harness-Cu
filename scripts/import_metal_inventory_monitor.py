"""Import metal_inventory_monitor.csv into project CSV format."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

from copper_forecast.inventory_monitor import (
    CSV_FIELDS,
    DEFAULT_MONITOR_PATH,
    INVENTORY_INDICATORS,
    build_import_rows,
    monitor_cutover,
    sync_monitor_to_manual,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "raw" / "live.csv"
HISTORY = ROOT / "data" / "raw" / "history.csv"
MANUAL = ROOT / "data" / "raw" / "manual_indicators.csv"


def trim_inventory_before(path: Path, cutover: date) -> int:
    """Drop exchange inventory rows dated before monitor cutover."""
    if not path.exists():
        return 0

    kept: list[dict] = []
    removed = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or CSV_FIELDS
        for row in reader:
            indicator = row.get("indicator", "")
            row_date = row.get("date", "")[:10]
            if (
                indicator in INVENTORY_INDICATORS
                and row_date
                and date.fromisoformat(row_date) < cutover
            ):
                removed += 1
                continue
            kept.append(row)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    return removed


def _configured_path(source: Path) -> str:
    try:
        return str(source.relative_to(ROOT))
    except ValueError:
        return str(source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import metal inventory monitor CSV")
    parser.add_argument(
        "--run",
        action="store_true",
        help="After import: fetch live data and regenerate reports/live.md",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / DEFAULT_MONITOR_PATH,
        help="Path to metal_inventory_monitor.csv",
    )
    args = parser.parse_args()

    source = args.source
    if not source.exists():
        raise SystemExit(f"Missing source file: {source}")

    state = sync_monitor_to_manual(ROOT, _configured_path(source))
    if state is None:
        raise SystemExit(f"Failed to sync monitor file: {source}")

    rows = build_import_rows(source)
    dates = sorted({row["date"] for row in rows})
    print(f"Synced {len(rows)} inventory rows into {MANUAL}")
    print(f"Date range: {dates[0]} .. {dates[-1]} (cutover {state.cutover.isoformat()})")

    if not args.run:
        return

    subprocess.run([sys.executable, "-m", "copper_forecast.cli", "run"], cwd=ROOT, check=True)
    removed_live = trim_inventory_before(LIVE, state.cutover)
    removed_hist = trim_inventory_before(HISTORY, state.cutover)
    print(f"Trimmed pre-{state.cutover} inventory: live -{removed_live}, history -{removed_hist}")
    if removed_live or removed_hist:
        subprocess.run([sys.executable, "-m", "copper_forecast.cli", "report"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

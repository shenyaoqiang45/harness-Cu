"""Import metal_inventory_monitor.csv into project CSV format."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "metal_inventory_monitor.csv"
OUT = ROOT / "data" / "raw" / "inventory_indicators_from_monitoring.csv"
MANUAL = ROOT / "data" / "raw" / "manual_indicators.csv"
LIVE = ROOT / "data" / "raw" / "live.csv"
HISTORY = ROOT / "data" / "raw" / "history.csv"

SOURCE_LABEL = "金属库存监控"
SOURCE_URL = ""

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
                        "source": SOURCE_LABEL,
                        "source_url": SOURCE_URL,
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


def run_fetch_and_report() -> None:
    subprocess.run(
        [sys.executable, "-m", "copper_forecast.cli", "fetch"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "copper_forecast.cli",
            "report",
            "-o",
            "reports/live.md",
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import metal inventory monitor CSV")
    parser.add_argument(
        "--run",
        action="store_true",
        help="After import: fetch live data, trim pre-cutover inventory, regenerate report",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE,
        help="Path to metal_inventory_monitor.csv",
    )
    args = parser.parse_args()

    source = args.source
    if not source.exists():
        raise SystemExit(f"Missing source file: {source}")

    cutover = monitor_cutover(source)
    rows = build_import_rows(source)
    write_csv(OUT, rows)
    merge_into_manual(MANUAL, rows)
    dates = sorted({row["date"] for row in rows})
    print(f"Wrote {len(rows)} rows -> {OUT}")
    print(f"Merged inventory indicators into {MANUAL}")
    print(f"Date range: {dates[0]} .. {dates[-1]} (cutover {cutover.isoformat()})")

    if not args.run:
        return

    run_fetch_and_report()
    removed_live = trim_inventory_before(LIVE, cutover)
    removed_hist = trim_inventory_before(HISTORY, cutover)
    print(f"Trimmed pre-{cutover} inventory: live -{removed_live}, history -{removed_hist}")
    if removed_live or removed_hist:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "copper_forecast.cli",
                "report",
                "-o",
                "reports/live.md",
            ],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    main()

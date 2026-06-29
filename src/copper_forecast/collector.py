"""Orchestrate live data collection into standard CSV."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from copper_forecast.data_loader import REQUIRED_COLUMNS, DataRow
from copper_forecast.fetchers import FetchedRecord, FetchResult
from copper_forecast.fetchers.akshare_src import fetch_akshare
from copper_forecast.fetchers.derived import fetch_derived
from copper_forecast.fetchers.eastmoney import fetch_eastmoney
from copper_forecast.fetchers.fred import fetch_fred
from copper_forecast.fetchers.yahoo import fetch_yahoo


def load_sources_config(config_dir: Path) -> dict:
    with (config_dir / "sources.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_manual(path: Path) -> FetchResult:
    result = FetchResult()
    if not path.exists():
        return result

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            indicator = row["indicator"].strip()
            raw = row["value"].strip()
            value: float | str = raw if indicator == "term_structure" else float(raw)
            result.records.append(
                FetchedRecord(
                    date=datetime.fromisoformat(row["date"][:10]).date(),
                    indicator=indicator,
                    value=value,
                    unit=row["unit"].strip(),
                    source=row["source"].strip(),
                    source_url=row.get("source_url", "").strip(),
                    frequency=row["frequency"].strip(),
                    confidence=row["confidence"].strip().upper(),
                    note=row.get("note", "").strip(),
                )
            )
    return result


def collect_all(config_dir: Path, project_root: Path) -> FetchResult:
    cfg = load_sources_config(config_dir)
    lookback = int(cfg.get("lookback_days", 400))
    merged = FetchResult()

    sources = cfg.get("sources", {})
    if sources.get("yahoo", {}).get("enabled", True):
        merged.extend(fetch_yahoo(sources["yahoo"]["indicators"], lookback))
    if sources.get("fred", {}).get("enabled", True):
        merged.extend(fetch_fred(sources["fred"]["indicators"], lookback))
    if sources.get("eastmoney", {}).get("enabled", True):
        merged.extend(fetch_eastmoney(sources["eastmoney"]["indicators"], lookback))
    if sources.get("akshare", {}).get("enabled", True):
        merged.extend(fetch_akshare(sources["akshare"]["indicators"], lookback))

    if sources.get("derived", {}).get("enabled", True):
        merged.extend(
            fetch_derived(sources["derived"]["indicators"], merged.records, lookback)
        )

    manual_path = project_root / cfg.get("manual", {}).get("path", "data/raw/manual_indicators.csv")
    manual = _load_manual(manual_path)
    merged.extend(manual)

    return merged


def _record_key(rec: FetchedRecord) -> tuple:
    if rec.frequency == "monthly":
        return (rec.indicator, f"{rec.date:%Y-%m}")
    return (rec.indicator, rec.date.isoformat())


def merge_records(
    existing: list[FetchedRecord],
    incoming: list[FetchedRecord],
) -> list[FetchedRecord]:
    """Merge by indicator+date; incoming overwrites existing."""
    by_key: dict[tuple, FetchedRecord] = {_record_key(r): r for r in existing}
    for rec in incoming:
        by_key[_record_key(rec)] = rec
    return sorted(by_key.values(), key=lambda r: (r.indicator, r.date))


def write_fetched_csv(path: Path, records: list[FetchedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = REQUIRED_COLUMNS + ["note"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow(
                {
                    "date": rec.date.isoformat(),
                    "indicator": rec.indicator,
                    "value": rec.value,
                    "unit": rec.unit,
                    "source": rec.source,
                    "source_url": rec.source_url,
                    "updated_at": rec.updated_at.isoformat(),
                    "frequency": rec.frequency,
                    "confidence": rec.confidence,
                    "note": rec.note,
                }
            )


def write_fetch_log(path: Path, result: FetchResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "record_count": len(result.records),
        "warnings": result.warnings,
        "errors": result.errors,
        "indicators": sorted({r.indicator for r in result.records}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_fetch(
    config_dir: Path,
    project_root: Path,
    output_path: Path | None = None,
    merge_history: bool = True,
) -> FetchResult:
    output_path = output_path or project_root / "data" / "raw" / "live.csv"
    history_path = project_root / "data" / "raw" / "history.csv"

    existing: list[FetchedRecord] = []
    if merge_history and output_path.exists():
        from copper_forecast.data_loader import load_csv

        for row in load_csv(output_path):
            existing.append(
                FetchedRecord(
                    date=row.date,
                    indicator=row.indicator,
                    value=row.value,
                    unit=row.unit,
                    source=row.source,
                    source_url=row.source_url,
                    frequency=row.frequency,
                    confidence=row.confidence,
                    updated_at=row.updated_at,
                )
            )

    fetched = collect_all(config_dir, project_root)
    merged = merge_records(existing, fetched.records)
    write_fetched_csv(output_path, merged)
    if merge_history:
        write_fetched_csv(history_path, merged)
    write_fetch_log(project_root / "data" / "audit" / "fetch_log.json", fetched)
    return fetched

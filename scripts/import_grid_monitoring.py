"""Import rows from 电网指标监控数据_*.csv into project CSV format."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "电网指标监控数据_2026-06-29.csv"
OUT = ROOT / "data" / "raw" / "grid_indicators_from_monitoring.csv"
MANUAL = ROOT / "data" / "raw" / "manual_indicators.csv"

# indicator_id -> (project_indicator, unit, frequency, confidence)
MAPPING = {
    "grid_investment": ("grid_investment", "pct", "monthly", "A"),
    "grid_investment_amount": ("grid_investment_amount", "CNY_100m", "monthly", "A"),
    "power_consumption_yoy": ("power_consumption_yoy", "pct", "monthly", "A"),
    "wire_cable_output_yoy": ("wire_cable_output_yoy", "pct", "monthly", "B"),
    "new_energy_grid_connection": ("new_energy_grid_connection", "10kW", "monthly", "A"),
}

FREQ_MAP = {"月度": "monthly", "周度/月度": "weekly"}


def _parse_source(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_data = False
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            if line.startswith("date,indicator_id"):
                in_data = True
                continue
            if not in_data or not line.strip() or line.startswith("#"):
                continue
            rows.append(next(csv.DictReader([line], fieldnames=[
                "date", "indicator_id", "indicator_name", "value", "unit",
                "source", "source_url", "updated_at", "frequency", "confidence", "note", "is_manual",
            ])))
    return rows


def _gw_to_10kw_unit(gw: float) -> float:
    """Monitoring file uses GW; project unit 10kW stores 万千瓦 (10 MW)."""
    return round(gw * 100, 4)


def _monthly_amounts(amount_rows: list[dict]) -> list[dict]:
    by_date = sorted(amount_rows, key=lambda r: r["date"])
    out: list[dict] = []
    prev = 0.0
    for row in by_date:
        cumulative = float(row["value"])
        monthly = cumulative if not prev else cumulative - prev
        prev = cumulative
        out.append({
            "date": row["date"],
            "indicator": "grid_investment_monthly_amount",
            "value": round(monthly, 4),
            "unit": "CNY_100m",
            "source": row["source"],
            "source_url": row.get("source_url", ""),
            "updated_at": row["updated_at"],
            "frequency": "monthly",
            "confidence": "A",
            "note": "Derived from cumulative grid_investment_amount; monitoring import",
        })
    return out


def build_import_rows(source: Path) -> list[dict]:
    raw = _parse_source(source)
    imported: list[dict] = []
    amount_raw: list[dict] = []

    for row in raw:
        ind_id = row["indicator_id"].strip()
        if ind_id == "grid_investment_amount":
            amount_raw.append(row)
        if ind_id not in MAPPING:
            continue
        indicator, unit, frequency, confidence = MAPPING[ind_id]
        value = float(row["value"])
        if ind_id == "new_energy_grid_connection":
            value = _gw_to_10kw_unit(value)
        imported.append({
            "date": row["date"][:10],
            "indicator": indicator,
            "value": value,
            "unit": unit,
            "source": row["source"],
            "source_url": row.get("source_url", ""),
            "updated_at": row["updated_at"],
            "frequency": frequency,
            "confidence": confidence,
            "note": f"from {source.name}",
        })

    imported.extend(_monthly_amounts(amount_raw))
    imported.sort(key=lambda r: (r["indicator"], r["date"]))
    return imported


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "date", "indicator", "value", "unit", "source", "source_url",
        "updated_at", "frequency", "confidence", "note",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def merge_into_manual(manual_path: Path, grid_rows: list[dict], keep_indicators: set[str]) -> None:
    """Replace manual rows for imported grid indicators; keep other indicators."""
    fields = [
        "date", "indicator", "value", "unit", "source", "source_url",
        "updated_at", "frequency", "confidence", "note",
    ]
    existing: list[dict] = []
    if manual_path.exists():
        with manual_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["indicator"] not in keep_indicators:
                    existing.append(row)

    merged = existing + grid_rows
    merged.sort(key=lambda r: (r["indicator"], r["date"]))
    write_csv(manual_path, merged)


def main() -> None:
    rows = build_import_rows(SOURCE)
    write_csv(OUT, rows)
    merge_into_manual(
        MANUAL,
        rows,
        keep_indicators={
            "grid_investment",
            "grid_investment_amount",
            "grid_investment_monthly_amount",
            "power_consumption_yoy",
            "wire_cable_output_yoy",
            "new_energy_grid_connection",
        },
    )
    print(f"Wrote {len(rows)} rows -> {OUT}")
    print(f"Merged grid indicators into {MANUAL}")


if __name__ == "__main__":
    main()

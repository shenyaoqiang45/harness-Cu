"""Quality gate for unattended fetch → validate → report runs.

The gate reuses ``validate_rows`` and ``merge_records``. It refuses to replace
trusted history when a fetch fails, when a new point is only an anomaly, or
when nothing confirmed has changed. It does not change weights or supply events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from copper_forecast.collector import (
    _record_key,
    collect_all,
    load_sources_config,
    merge_records,
    write_fetch_log,
    write_fetched_csv,
)
from copper_forecast.data_loader import DataRow, load_csv
from copper_forecast.fetchers import FetchedRecord, FetchResult
from copper_forecast.inventory_monitor import filter_inventory_records, sync_monitor_to_manual
from copper_forecast.validator import validate_rows


@dataclass
class GateDecision:
    status: str
    publish: bool
    notify: bool
    exit_code: int
    reasons: list[str] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self, extra: dict | None = None) -> dict:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": self.status,
            "publish": self.publish,
            "notify": self.notify,
            "exit_code": self.exit_code,
            "reasons": self.reasons,
            "categories": self.categories,
        }
        if extra:
            payload.update(extra)
        return payload


def load_unattended_config(config_dir: Path) -> dict:
    path = config_dir / "unattended.yaml"
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def content_key(records: list[FetchedRecord]) -> tuple:
    """Identity of market data, ignoring fetch timestamps."""
    return tuple(
        sorted(
            (rec.indicator, rec.date.isoformat(), _value_token(rec.value))
            for rec in records
        )
    )


def _value_token(value: float | str) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _to_row(rec: FetchedRecord) -> DataRow:
    return DataRow(
        date=rec.date,
        indicator=rec.indicator,
        value=rec.value,
        unit=rec.unit,
        source=rec.source,
        source_url=rec.source_url,
        updated_at=rec.updated_at,
        frequency=rec.frequency,
        confidence=rec.confidence,
    )


def _load_records(path: Path) -> list[FetchedRecord]:
    if not path.exists():
        return []
    records: list[FetchedRecord] = []
    for row in load_csv(path):
        records.append(
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
    return records


def dedupe_incoming(incoming: list[FetchedRecord]) -> tuple[list[FetchedRecord], int]:
    """Last row wins for a repeated indicator+date. Returns (rows, dropped)."""
    by_key: dict[tuple, FetchedRecord] = {}
    dropped = 0
    for rec in incoming:
        key = _record_key(rec)
        if key in by_key:
            dropped += 1
        by_key[key] = rec
    return list(by_key.values()), dropped


def _replaces_with_anomaly(
    previous: FetchedRecord, incoming: FetchedRecord, anomaly_rules: list[dict]
) -> bool:
    """True when a new value for the same key would fail an existing anomaly rule."""
    if _value_token(previous.value) == _value_token(incoming.value):
        return False
    prev_val = _to_row(previous).numeric_value
    new_val = _to_row(incoming).numeric_value
    if prev_val is None or new_val is None:
        return False
    for rule in anomaly_rules:
        if rule.get("indicator") != incoming.indicator:
            continue
        if rule.get("rule") == "range":
            if new_val < rule["min"] or new_val > rule["max"]:
                return True
        elif rule.get("rule") == "daily_pct_change" and prev_val != 0:
            if abs((new_val - prev_val) / prev_val) > rule["threshold"]:
                return True
        elif rule.get("rule") == "abs_change":
            if abs(new_val - prev_val) > rule["threshold"]:
                return True
    return False


def protect_trusted_rows(
    existing: list[FetchedRecord],
    incoming: list[FetchedRecord],
    config_dir: Path,
) -> tuple[list[FetchedRecord], list[str]]:
    """Drop rejected newcomers and do not let an anomaly replace a stored row."""
    from copper_forecast.validator import load_validation_config

    unique, _dropped = dedupe_incoming(incoming)
    merged = merge_records(existing, unique)
    validation = validate_rows([_to_row(rec) for rec in merged], config_dir)
    anomaly_rules = load_validation_config(config_dir)["rules"].get("anomaly_rules", [])
    blocked = {
        (issue.row.indicator, issue.row.date.isoformat(), issue.row.frequency)
        for issue in validation.rejected
    }
    pending = {
        (issue.row.indicator, issue.row.date.isoformat(), issue.row.frequency)
        for issue in validation.pending
    }
    existing_by_key = {_record_key(rec): rec for rec in existing}
    incoming_by_key = {_record_key(rec): rec for rec in unique}

    kept: list[FetchedRecord] = []
    notes: list[str] = []
    for rec in merged:
        key = _record_key(rec)
        identity = (rec.indicator, rec.date.isoformat(), rec.frequency)
        if key not in incoming_by_key:
            kept.append(rec)
            continue
        previous = existing_by_key.get(key)
        if previous is not None and _replaces_with_anomaly(previous, rec, anomaly_rules):
            kept.append(previous)
            notes.append(f"anomaly_kept_previous:{rec.indicator}:{rec.date.isoformat()}")
            continue
        if identity in blocked or identity in pending:
            if previous is not None and _value_token(previous.value) != _value_token(rec.value):
                kept.append(previous)
                kind = "rejected" if identity in blocked else "anomaly"
                notes.append(f"{kind}_kept_previous:{rec.indicator}:{rec.date.isoformat()}")
            elif identity in blocked:
                notes.append(f"rejected_dropped:{rec.indicator}:{rec.date.isoformat()}")
            else:
                notes.append(f"anomaly_dropped:{rec.indicator}:{rec.date.isoformat()}")
            continue
        kept.append(rec)
    return kept, notes


def latest_by_indicator(records: list[FetchedRecord]) -> dict[str, FetchedRecord]:
    latest: dict[str, FetchedRecord] = {}
    for rec in records:
        current = latest.get(rec.indicator)
        if current is None or rec.date > current.date:
            latest[rec.indicator] = rec
    return latest


def expected_max_age(as_of: date, freshness: dict) -> int:
    return int(freshness.get(as_of.weekday(), freshness.get(str(as_of.weekday()), 3)))


def update_fail_streak(previous: int, status: str) -> int:
    if status == "failed":
        return previous + 1
    return 0


def _confirmed_records(records: list[FetchedRecord], config_dir: Path) -> list[FetchedRecord]:
    validation = validate_rows([_to_row(rec) for rec in records], config_dir)
    confirmed_ids = {
        (row.indicator, row.date.isoformat(), row.frequency) for row in validation.confirmed
    }
    return [
        rec
        for rec in records
        if (rec.indicator, rec.date.isoformat(), rec.frequency) in confirmed_ids
    ]


def parse_fetch_errors(errors: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for err in errors:
        parts = err.split(":")
        if len(parts) >= 2 and parts[1]:
            found[parts[1]] = err
    return found


def evaluate_gate(
    existing: list[FetchedRecord],
    protected: list[FetchedRecord],
    fetched: FetchResult,
    config_dir: Path,
    as_of: date,
    protection_notes: list[str],
    duplicates_dropped: int,
) -> GateDecision:
    """Decide success, partial success, no-change, or failure without publishing."""
    cfg = load_unattended_config(config_dir)
    lags = cfg.get("monthly_lag_days") or {}
    default_lag = int(lags.get("default", 45))
    critical = list(cfg.get("critical_daily") or [])
    surge_min = int(cfg.get("anomaly_surge_min", 3))
    max_age = expected_max_age(as_of, cfg.get("freshness_max_age_days") or {})

    sources = load_sources_config(config_dir).get("sources", {})
    enabled = [name for name, meta in sources.items() if meta.get("enabled", True)]
    failed_groups = {err.split(":", 1)[0] for err in fetched.errors}
    failed_enabled = sorted(set(enabled) & failed_groups)
    source_rate = 1.0 if not enabled else (len(enabled) - len(failed_enabled)) / len(enabled)

    error_map = parse_fetch_errors(fetched.errors)
    latest = latest_by_indicator(protected)
    categories: dict[str, list[str]] = {
        "fetch_failed": sorted(error_map),
        "not_published": [],
        "anomaly": [note for note in protection_notes if note.startswith("anomaly_")],
        "market_closed": [],
        "rejected": [note for note in protection_notes if note.startswith("rejected_")],
    }

    market_closed = as_of.weekday() >= 5
    if market_closed:
        categories["market_closed"].append(as_of.isoformat())

    stale: list[str] = []
    missing: list[str] = []
    for name in critical:
        row = latest.get(name)
        if row is None:
            missing.append(name)
            continue
        age = (as_of - row.date).days
        if age > max_age:
            stale.append(f"{name}:{row.date.isoformat()}:age={age}")

    for name, row in latest.items():
        if row.frequency != "monthly":
            continue
        lag = int(lags.get(name, default_lag))
        age = (as_of - row.date).days
        if age <= lag and name not in critical:
            categories["not_published"].append(f"{name}:age={age}:lag={lag}")

    old_confirmed = content_key(_confirmed_records(existing, config_dir))
    new_confirmed = content_key(_confirmed_records(protected, config_dir))
    confirmed_changed = old_confirmed != new_confirmed

    critical_errors = [name for name in critical if name in error_map]
    old_latest = latest_by_indicator(existing)
    confirmed_ids = {
        (rec.indicator, rec.date) for rec in _confirmed_records(protected, config_dir)
    }
    gained_critical = False
    for name in critical:
        before = old_latest.get(name)
        after = latest.get(name)
        if after is None:
            continue
        if (before is None or after.date > before.date) and (after.indicator, after.date) in confirmed_ids:
            gained_critical = True

    pending_new = _new_pending_count(existing, protected, config_dir)
    anomaly_count = len(categories["anomaly"])
    surge = pending_new >= surge_min or anomaly_count >= surge_min

    reasons: list[str] = []
    if duplicates_dropped:
        reasons.append(f"duplicates_collapsed:{duplicates_dropped}")
    if failed_enabled:
        reasons.append("source_groups_failed:" + ",".join(failed_enabled))
    reasons.extend(f"fetch_failed:{name}" for name in critical_errors)
    reasons.extend(f"missing:{name}" for name in missing)
    reasons.extend(f"stale:{item}" for item in stale)
    reasons.extend(categories["anomaly"])
    reasons.extend(categories["rejected"])

    critical_blocked = bool(missing or stale or (critical_errors and not gained_critical))
    if market_closed and not missing and not stale and not confirmed_changed:
        status, publish, notify, exit_code = "unchanged", False, False, 0
        reasons.append("market_closed_no_new_bar")
    elif critical_blocked and not (market_closed and not missing and not stale):
        status, publish, notify, exit_code = "failed", False, True, 1
        reasons.append("critical_gate_failed")
    elif not confirmed_changed:
        status, publish, notify, exit_code = "unchanged", False, surge or bool(critical_errors), 0
        reasons.append("no_confirmed_change")
    elif failed_enabled or surge or categories["anomaly"]:
        status, publish, notify, exit_code = "partial", True, surge or bool(critical_errors), 0
        reasons.append("published_with_gaps")
    else:
        status, publish, notify, exit_code = "success", True, False, 0
        reasons.append("published")

    decision = GateDecision(
        status=status,
        publish=publish,
        notify=notify,
        exit_code=exit_code,
        reasons=reasons,
        categories=categories,
    )
    decision.categories["summary"] = [
        f"source_success_rate={source_rate:.2f}",
        f"pending_new={pending_new}",
        f"duplicates_dropped={duplicates_dropped}",
    ]
    return decision


def _new_pending_count(
    existing: list[FetchedRecord],
    protected: list[FetchedRecord],
    config_dir: Path,
) -> int:
    old_ids = {(rec.indicator, rec.date.isoformat()) for rec in existing}
    validation = validate_rows([_to_row(rec) for rec in protected], config_dir)
    return sum(
        1
        for issue in validation.pending
        if (issue.row.indicator, issue.row.date.isoformat()) not in old_ids
    )


def _write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot(paths: list[Path]) -> dict[Path, bytes]:
    return {path: path.read_bytes() if path.exists() else b"" for path in paths}


def _restore(snapshots: dict[Path, bytes]) -> None:
    for path, blob in snapshots.items():
        if blob:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        elif path.exists():
            path.unlink()


def run_unattended(
    config_dir: Path,
    project_root: Path,
    *,
    output: Path | None = None,
    as_of: date | None = None,
) -> int:
    """Fetch, gate, and publish only when confirmed data actually changed."""
    as_of = as_of or date.today()
    history_path = project_root / "data" / "raw" / "history.csv"
    live_path = project_root / "data" / "raw" / "live.csv"
    cfg = load_sources_config(config_dir)
    manual_rel = cfg.get("manual", {}).get("path", "data/raw/manual_indicators.csv")
    manual_path = project_root / manual_rel
    manual_blob = manual_path.read_bytes() if manual_path.exists() else b""

    monitor = None
    refresh_notes: list[str] = []
    monitor_cfg = cfg.get("inventory_monitor", {})
    if monitor_cfg.get("enabled", True):
        from copper_forecast.inventory_refresh import refresh_inventory_monitor

        refresh_notes = refresh_inventory_monitor(project_root, monitor_cfg.get("path"))
        monitor = sync_monitor_to_manual(project_root, monitor_cfg.get("path"))

    try:
        existing = _load_records(history_path)
        existing = filter_inventory_records(existing, monitor)
        fetched = collect_all(config_dir, project_root, monitor)
        fetched.records = filter_inventory_records(fetched.records, monitor)
    except Exception as exc:
        _restore({manual_path: manual_blob})
        decision = GateDecision(
            status="failed",
            publish=False,
            notify=True,
            exit_code=1,
            reasons=[f"collect_failed:{exc}"],
        )
        _write_status(
            project_root / "data" / "audit" / "run_status.json",
            decision.as_dict({"as_of": as_of.isoformat(), "fetch_errors": [str(exc)]}),
        )
        print(f"Unattended status: failed\n  - collect_failed:{exc}")
        return 1
    finally:
        _restore({manual_path: manual_blob})

    fetched.warnings.extend(refresh_notes)
    unique, dropped = dedupe_incoming(fetched.records)
    from copper_forecast.inventory_refresh import retire_mismatched_inventory

    existing, retire_notes = retire_mismatched_inventory(existing, unique)
    protected, notes = protect_trusted_rows(existing, unique, config_dir)
    notes = retire_notes + notes
    protected = filter_inventory_records(protected, monitor)
    decision = evaluate_gate(
        existing, protected, fetched, config_dir, as_of, notes, dropped
    )

    guarded = [
        history_path,
        live_path,
        project_root / "data" / "validated" / "latest.csv",
        project_root / "data" / "clean" / "latest.csv",
        project_root / "data" / "audit" / "anomalies.json",
        project_root / "data" / "audit" / "fetch_log.json",
        project_root / "data" / "forecast" / "latest.json",
    ]
    snapshots = _snapshot(guarded)
    report_path = ""
    if decision.publish:
        try:
            write_fetched_csv(live_path, protected)
            write_fetched_csv(history_path, protected)
            write_fetch_log(project_root / "data" / "audit" / "fetch_log.json", fetched)
            from copper_forecast.cli import run_pipeline
            from copper_forecast.report import timestamped_report_path

            report_target = output or timestamped_report_path(project_root / "reports")
            code = run_pipeline(
                live_path, report_target, config_dir, project_root / "data"
            )
            if code != 0:
                raise RuntimeError(f"report_exit_{code}")
            report_path = str(report_target)
        except Exception as exc:
            _restore(snapshots)
            decision = GateDecision(
                status="failed",
                publish=False,
                notify=True,
                exit_code=1,
                reasons=decision.reasons + [f"report_failed:{exc}"],
                categories=decision.categories,
            )
    else:
        _restore(snapshots)

    payload = decision.as_dict(
        {
            "as_of": as_of.isoformat(),
            "record_count": len(protected) if decision.publish else len(existing),
            "fetch_errors": fetched.errors,
            "fetch_warnings": fetched.warnings,
            "report": report_path,
        }
    )
    _write_status(project_root / "data" / "audit" / "run_status.json", payload)
    print(f"Unattended status: {decision.status}")
    print(f"Publish: {'yes' if decision.publish else 'no'}")
    print(f"Notify: {'yes' if decision.notify else 'no'}")
    for reason in decision.reasons:
        print(f"  - {reason}")
    return decision.exit_code

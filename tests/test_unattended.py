"""Tests for the copper unattended quality gate."""

from datetime import date, datetime
from pathlib import Path

from copper_forecast.collector import write_fetched_csv
from copper_forecast.fetchers import FetchedRecord, FetchResult
from copper_forecast.unattended import (
    dedupe_incoming,
    evaluate_gate,
    protect_trusted_rows,
    run_unattended,
    update_fail_streak,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def _rec(
    indicator: str,
    day: str,
    value: float,
    *,
    unit: str,
    frequency: str = "daily",
) -> FetchedRecord:
    return FetchedRecord(
        date=date.fromisoformat(day),
        indicator=indicator,
        value=value,
        unit=unit,
        source="test",
        source_url="https://example.test",
        frequency=frequency,
        confidence="A",
        updated_at=datetime(2026, 10, 1, 8, 0, 0),
    )


def _price(day: str, value: float) -> FetchedRecord:
    return _rec("lme_copper_price", day, value, unit="USD/ton")


def _dxy(day: str, value: float) -> FetchedRecord:
    return _rec("dxy", day, value, unit="index")


def _rate(day: str, value: float) -> FetchedRecord:
    return _rec("us_10y_real_rate", day, value, unit="pct")


def _base(day: str) -> list[FetchedRecord]:
    return [_price(day, 9000.0), _dxy(day, 102.0), _rate(day, 1.8)]


def test_duplicates_collapse_to_last_value():
    rows, dropped = dedupe_incoming([_price("2026-10-14", 9000.0), _price("2026-10-14", 9010.0)])
    assert dropped == 1
    assert rows[0].value == 9010.0


def test_anomaly_does_not_overwrite_trusted_price():
    existing = _base("2026-10-13")
    incoming = _base("2026-10-13")
    incoming[0] = _price("2026-10-13", 10000.0)
    protected, notes = protect_trusted_rows(existing, incoming, CONFIG)
    copper = next(rec for rec in protected if rec.indicator == "lme_copper_price")
    assert copper.value == 9000.0
    assert any(note.startswith("anomaly_kept_previous:lme_copper_price") for note in notes)


def test_rejected_row_is_dropped():
    existing = _base("2026-10-14")
    bad = _price("2026-10-15", 9010.0)
    bad.unit = ""
    protected, notes = protect_trusted_rows(existing, [bad], CONFIG)
    assert all(rec.date.isoformat() != "2026-10-15" for rec in protected)
    assert any(note.startswith("rejected_dropped:lme_copper_price") for note in notes)


def test_weekday_critical_fetch_error_fails():
    existing = _base("2026-10-14")
    fetched = FetchResult(
        records=list(existing),
        errors=["yahoo:lme_copper_price: Too Many Requests"],
    )
    decision = evaluate_gate(existing, existing, fetched, CONFIG, date(2026, 10, 15), [], 0)
    assert decision.status == "failed"
    assert decision.publish is False
    assert decision.notify is True
    assert decision.exit_code == 1


def test_weekend_without_new_bar_is_unchanged():
    existing = _base("2026-10-16")
    fetched = FetchResult(records=list(existing))
    decision = evaluate_gate(existing, existing, fetched, CONFIG, date(2026, 10, 17), [], 0)
    assert decision.status == "unchanged"
    assert decision.publish is False
    assert "market_closed_no_new_bar" in decision.reasons


def test_monthly_inside_lag_is_not_a_failure():
    existing = _base("2026-10-14")
    existing.append(_rec("china_pmi", "2026-09-01", 50.1, unit="index", frequency="monthly"))
    fetched = FetchResult(records=list(existing))
    decision = evaluate_gate(existing, existing, fetched, CONFIG, date(2026, 10, 15), [], 0)
    assert decision.status == "unchanged"
    assert any(item.startswith("china_pmi:") for item in decision.categories["not_published"])


def test_new_confirmed_bar_publishes():
    existing = _base("2026-10-14")
    incoming = [_price("2026-10-15", 9050.0), _dxy("2026-10-15", 102.1), _rate("2026-10-15", 1.81)]
    protected, _notes = protect_trusted_rows(existing, incoming, CONFIG)
    fetched = FetchResult(records=incoming)
    decision = evaluate_gate(existing, protected, fetched, CONFIG, date(2026, 10, 15), [], 0)
    assert decision.status == "success"
    assert decision.publish is True


def test_repeated_run_does_not_rewrite_history_or_add_a_second_report(tmp_path, monkeypatch):
    history = tmp_path / "data" / "raw" / "history.csv"
    existing = _base("2026-10-14")
    write_fetched_csv(history, existing)
    original = history.read_bytes()
    calls = {"n": 0}

    def _fetch(_config, _root, _monitor=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return FetchResult(
                records=[
                    _price("2026-10-15", 9050.0),
                    _dxy("2026-10-15", 102.1),
                    _rate("2026-10-15", 1.81),
                ]
            )
        return FetchResult(records=[])

    monkeypatch.setattr("copper_forecast.unattended.collect_all", _fetch)
    first = run_unattended(CONFIG, tmp_path, as_of=date(2026, 10, 15))
    reports = list((tmp_path / "reports").rglob("*.md"))
    assert first == 0
    assert len(reports) == 1
    after_first = history.read_bytes()
    assert after_first != original

    second = run_unattended(CONFIG, tmp_path, as_of=date(2026, 10, 15))
    reports = list((tmp_path / "reports").rglob("*.md"))
    assert second == 0
    assert len(reports) == 1
    assert history.read_bytes() == after_first
    status = (tmp_path / "data" / "audit" / "run_status.json").read_text(encoding="utf-8")
    assert '"status": "unchanged"' in status


def test_fetch_failure_does_not_overwrite_history_file(tmp_path, monkeypatch):
    history = tmp_path / "data" / "raw" / "history.csv"
    write_fetched_csv(history, _base("2026-10-14"))
    original = history.read_bytes()
    monkeypatch.setattr(
        "copper_forecast.unattended.collect_all",
        lambda *_args, **_kwargs: FetchResult(
            errors=["yahoo:lme_copper_price: Too Many Requests"]
        ),
    )
    code = run_unattended(CONFIG, tmp_path, as_of=date(2026, 10, 15))
    assert code == 1
    assert history.read_bytes() == original
    assert not list((tmp_path / "reports").rglob("*.md"))


def test_report_failure_restores_history(tmp_path, monkeypatch):
    history = tmp_path / "data" / "raw" / "history.csv"
    write_fetched_csv(history, _base("2026-10-14"))
    original = history.read_bytes()

    def _fetch(_config, _root, _monitor=None):
        return FetchResult(
            records=[
                _price("2026-10-15", 9050.0),
                _dxy("2026-10-15", 102.1),
                _rate("2026-10-15", 1.81),
            ]
        )

    monkeypatch.setattr("copper_forecast.unattended.collect_all", _fetch)
    monkeypatch.setattr("copper_forecast.cli.run_pipeline", lambda *_args, **_kwargs: 1)
    code = run_unattended(CONFIG, tmp_path, as_of=date(2026, 10, 15))
    assert code == 1
    assert history.read_bytes() == original
    status = (tmp_path / "data" / "audit" / "run_status.json").read_text(encoding="utf-8")
    assert '"status": "failed"' in status
    assert '"publish": false' in status


def test_fail_streak_resets_after_success():
    assert update_fail_streak(0, "failed") == 1
    assert update_fail_streak(2, "failed") == 3
    assert update_fail_streak(3, "success") == 0
    assert update_fail_streak(3, "unchanged") == 0

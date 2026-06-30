"""Tests for report output paths."""

from datetime import datetime
from pathlib import Path

from copper_forecast.report import timestamped_report_path


def test_timestamped_report_path_under_runs():
    when = datetime(2026, 6, 30, 17, 11, 59)
    path = timestamped_report_path(Path("reports"), when=when)
    assert path == Path("reports/runs/live_2026-06-30_171159.md")

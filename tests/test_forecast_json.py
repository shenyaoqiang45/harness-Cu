"""Tests for forecast JSON export used by the dashboard."""

import json
from datetime import date, datetime
from pathlib import Path

from copper_forecast.data_loader import DataRow
from copper_forecast.indicators import ModuleScore, SignalDetail
from copper_forecast.json_export import (
    forecast_to_dict,
    timestamped_forecast_history_path,
    write_forecast_json,
)
from copper_forecast.scoring import (
    CrossValidationGroup,
    CrossValidationResult,
    ForecastResult,
)
from copper_forecast.validator import ValidationIssue, ValidationResult


def _row(**kwargs) -> DataRow:
    defaults = dict(
        date=date(2026, 7, 13),
        indicator="lme_copper_price",
        value=13828,
        unit="USD/ton",
        source="yahoo",
        source_url="https://example.com",
        updated_at=datetime(2026, 7, 13, 12, 0, 0),
        frequency="daily",
        confidence="A",
        status="confirmed",
    )
    defaults.update(kwargs)
    return DataRow(**defaults)


def _sample_forecast() -> tuple[ForecastResult, ValidationResult]:
    modules = {
        "china_demand": ModuleScore(
            "china_demand",
            1.0,
            signals=[SignalDetail("pmi", 1.0, "China PMI 50.3")],
        ),
        "inventory": ModuleScore("inventory", 1.0),
        "macro_liquidity": ModuleScore(
            "macro_liquidity",
            -1.0,
            signals=[
                SignalDetail(
                    "real_rate",
                    -0.8,
                    "US 10Y real rate up",
                    confidence="B",
                    raw_score=-1.0,
                )
            ],
        ),
        "global_cycle": ModuleScore("global_cycle", 0.2),
        "supply": ModuleScore("supply", 0.95),
        "trend": ModuleScore("trend", 0.6),
    }
    forecast = ForecastResult(
        total_score=0.495,
        direction="偏多",
        week_outlook="中性偏多（低置信）",
        month_outlook="中性偏多（低置信）",
        confidence=0.25,
        data_health=0.85,
        module_scores=modules,
        supporting_factors=["[trend] Price > MA20"],
        suppressing_factors=["[macro_liquidity] real rate up"],
        risks=["Section 232 unsigned"],
        invalidation_conditions=["Tariff scheme rejected"],
        data_cutoff=date(2026, 7, 13),
        generated_at=datetime(2026, 7, 14, 0, 2, 42),
        cross_validation=CrossValidationResult(
            groups=[
                CrossValidationGroup(
                    "A",
                    "基本面/现货组",
                    0.992,
                    "看多",
                    ["china_demand", "inventory", "supply"],
                ),
                CrossValidationGroup(
                    "B",
                    "宏观/价格组",
                    -0.429,
                    "偏空",
                    ["macro_liquidity", "global_cycle", "trend"],
                ),
            ],
            agreement="相互背离",
            note="A/B 两组方向冲突",
        ),
        confidence_note="方向为低置信信号",
        low_confidence=True,
    )
    issue = ValidationIssue(
        row=_row(indicator="korea_exports_yoy", date=date(2026, 3, 1)),
        severity="pending",
        reason="YoY MoM jump > 18pp",
    )
    validation = ValidationResult(confirmed=[_row()], pending=[issue])
    return forecast, validation


def test_forecast_to_dict_shape():
    forecast, validation = _sample_forecast()
    payload = forecast_to_dict(forecast, validation)

    assert payload["total_score"] == 0.495
    assert payload["direction"] == "偏多"
    assert payload["week_outlook"] == "中性偏多（低置信）"
    assert payload["confidence"] == 0.25
    assert payload["data_health"] == 0.85
    assert payload["low_confidence"] is True
    assert payload["data_cutoff"] == "2026-07-13"
    assert payload["generated_at"].startswith("2026-07-14T00:02:42")

    assert len(payload["modules"]) == 6
    china = payload["modules"][0]
    assert china["key"] == "china_demand"
    assert china["label"] == "中国需求"
    assert china["score"] == 1.0
    assert china["signals"][0]["description"] == "China PMI 50.3"

    macro = next(m for m in payload["modules"] if m["key"] == "macro_liquidity")
    assert macro["signals"][0]["confidence"] == "B"
    assert macro["signals"][0]["raw_score"] == -1.0

    cv = payload["cross_validation"]
    assert cv is not None
    assert cv["agreement"] == "相互背离"
    assert len(cv["groups"]) == 2
    assert cv["groups"][0]["direction"] == "看多"

    assert len(payload["anomalies"]) == 1
    assert payload["anomalies"][0]["severity"] == "pending"
    assert payload["anomalies"][0]["indicator"] == "korea_exports_yoy"
    assert payload["anomalies"][0]["date"] == "2026-03-01"


def test_write_forecast_json_paths(tmp_path: Path):
    forecast, validation = _sample_forecast()
    when = datetime(2026, 7, 14, 0, 2, 42)
    latest, history = write_forecast_json(
        forecast, validation, tmp_path / "forecast", when=when
    )

    assert latest == tmp_path / "forecast" / "latest.json"
    assert history == tmp_path / "forecast" / "history" / "2026-07-14_000242.json"
    assert latest.exists()
    assert history.exists()

    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["total_score"] == 0.495
    history_payload = json.loads(history.read_text(encoding="utf-8"))
    assert history_payload == payload


def test_timestamped_forecast_history_path():
    when = datetime(2026, 7, 14, 8, 47, 0)
    path = timestamped_forecast_history_path(Path("data/forecast"), when=when)
    assert path == Path("data/forecast/history/2026-07-14_084700.json")

"""Tests for scoring and direction labels."""

from datetime import date, datetime, timedelta
from pathlib import Path

from copper_forecast.data_loader import DataRow
from copper_forecast.indicators import ModuleScore, SignalDetail, compute_all_module_scores
from copper_forecast.scoring import (
    _direction_label,
    compute_cross_validation,
    compute_data_health,
    compute_forecast,
)
from copper_forecast.validator import ValidationResult

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_direction_thresholds():
    thresholds = {
        "strong_bullish": 0.50,
        "bullish": 0.20,
        "bearish": -0.20,
        "strong_bearish": -0.50,
    }
    assert _direction_label(0.55, thresholds) == "看多"
    assert _direction_label(0.35, thresholds) == "偏多"
    assert _direction_label(0.0, thresholds) == "中性"
    assert _direction_label(-0.35, thresholds) == "偏空"
    assert _direction_label(-0.55, thresholds) == "看空"


def test_total_score_weighted():
    module_scores = {
        "china_demand": ModuleScore("china_demand", 1.0),
        "inventory": ModuleScore("inventory", 1.0),
        "macro_liquidity": ModuleScore("macro_liquidity", -1.0),
        "global_cycle": ModuleScore("global_cycle", 0.5),
        "supply": ModuleScore("supply", 0.0),
        "trend": ModuleScore("trend", 1.0),
    }
    row = DataRow(
        date=date(2026, 6, 29),
        indicator="lme_copper_price",
        value=9500,
        unit="USD/ton",
        source="lme",
        source_url="https://example.com",
        updated_at=datetime(2026, 6, 29),
        frequency="daily",
        confidence="A",
        status="confirmed",
    )
    forecast = compute_forecast(
        module_scores,
        ValidationResult(confirmed=[row]),
        [row],
        CONFIG_DIR,
    )
    # 0.30*1 + 0.25*1 + 0.20*(-1) + 0.10*0.5 + 0.10*0 + 0.05*1 = 0.45
    assert abs(forecast.total_score - 0.45) < 0.001
    assert forecast.direction == "偏多"
    assert forecast.cross_validation is not None


def test_cross_validation_detects_group_divergence():
    module_scores = {
        "china_demand": ModuleScore("china_demand", 1.0),
        "inventory": ModuleScore("inventory", 1.0),
        "macro_liquidity": ModuleScore("macro_liquidity", -1.0),
        "trend": ModuleScore("trend", -1.0),
    }
    module_weights = {
        "china_demand": 0.3,
        "inventory": 0.2,
        "macro_liquidity": 0.3,
        "trend": 0.2,
    }
    thresholds = {
        "strong_bullish": 0.50,
        "bullish": 0.20,
        "bearish": -0.20,
        "strong_bearish": -0.50,
    }
    cross_cfg = {
        "groups": {
            "A": {"label": "A", "modules": ["china_demand", "inventory"]},
            "B": {"label": "B", "modules": ["macro_liquidity", "trend"]},
        }
    }

    result = compute_cross_validation(
        module_scores, module_weights, thresholds, cross_cfg
    )

    assert result is not None
    assert result.agreement == "相互背离"
    assert [group.direction for group in result.groups] == ["看多", "看空"]


def test_data_health_uses_latest_freshness_and_ignores_optional(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "validation_rules.yaml").write_text(
        "source_confidence_map:\n  A: 1.0\n  B: 0.8\n",
        encoding="utf-8",
    )
    (config_dir / "indicators.yaml").write_text(
        "modules:\n  inventory:\n    indicators:\n      - required_indicator\n      - optional_indicator\n",
        encoding="utf-8",
    )
    (config_dir / "sources.yaml").write_text(
        "optional:\n  - optional_indicator\n",
        encoding="utf-8",
    )
    (config_dir / "weights.yaml").write_text(
        "confidence:\n  data_quality_weights:\n    source: 0.0\n    freshness: 0.5\n    cross_check: 0.0\n    completeness: 0.5\n",
        encoding="utf-8",
    )

    today = date.today()
    rows = [
        DataRow(
            date=today - timedelta(days=120),
            indicator="required_indicator",
            value=1,
            unit="index",
            source="test",
            source_url="https://example.com",
            updated_at=datetime.combine(today, datetime.min.time()),
            frequency="daily",
            confidence="A",
            status="confirmed",
        ),
        DataRow(
            date=today,
            indicator="required_indicator",
            value=2,
            unit="index",
            source="test",
            source_url="https://example.com",
            updated_at=datetime.combine(today, datetime.min.time()),
            frequency="daily",
            confidence="A",
            status="confirmed",
        ),
    ]

    health = compute_data_health(rows, ValidationResult(confirmed=rows), config_dir)

    assert health == 1.0


def test_trend_score_from_price_series():
    rows = []
    price = 9000.0
    for i in range(130):
        d = date(2026, 2, 1)
        from datetime import timedelta

        day = d + timedelta(days=i)
        price += 5
        rows.append(
            DataRow(
                date=day,
                indicator="lme_copper_price",
                value=price,
                unit="USD/ton",
                source="lme",
                source_url="https://example.com",
                updated_at=datetime.combine(day, datetime.min.time()),
                frequency="daily",
                confidence="A",
                status="confirmed",
            )
        )
    scores = compute_all_module_scores(rows, str(CONFIG_DIR))
    assert scores["trend"].score > 0


def test_china_demand_prefers_authoritative_grid_over_newer_proxy():
    rows = [
        DataRow(
            date=date(2026, 3, 28),
            indicator="grid_investment",
            value=43.3,
            unit="pct",
            source="国家能源局",
            source_url="https://example.com",
            updated_at=datetime(2026, 6, 29),
            frequency="monthly",
            confidence="A",
            status="confirmed",
        ),
        DataRow(
            date=date(2026, 5, 28),
            indicator="grid_investment",
            value=-17.1,
            unit="pct",
            source="东方财富-固定资产投资代理",
            source_url="https://example.com",
            updated_at=datetime(2026, 6, 29),
            frequency="monthly",
            confidence="C",
            status="confirmed",
        ),
    ]

    scores = compute_all_module_scores(rows, str(CONFIG_DIR))
    grid_signal = scores["china_demand"].signals[0]

    assert grid_signal.score == 1.0
    assert "+43.3%" in grid_signal.description

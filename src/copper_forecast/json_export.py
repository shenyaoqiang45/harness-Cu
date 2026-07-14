"""Serialize forecast results to JSON for the dashboard."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from copper_forecast.indicators import ModuleScore, SignalDetail
from copper_forecast.report import MODULE_LABELS
from copper_forecast.scoring import ForecastResult
from copper_forecast.validator import ValidationIssue, ValidationResult


def _signal_to_dict(sig: SignalDetail) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": sig.name,
        "score": sig.score,
        "description": sig.description,
    }
    if sig.confidence is not None:
        payload["confidence"] = sig.confidence
    if sig.raw_score is not None:
        payload["raw_score"] = sig.raw_score
    return payload


def _module_to_dict(mod: ModuleScore) -> dict[str, Any]:
    return {
        "key": mod.module,
        "label": MODULE_LABELS.get(mod.module, mod.module),
        "score": mod.score,
        "signals": [_signal_to_dict(s) for s in mod.signals],
        "data_gaps": list(mod.data_gaps),
    }


def _anomaly_to_dict(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "indicator": issue.row.indicator,
        "date": issue.row.date.isoformat(),
        "reason": issue.reason,
    }


def forecast_to_dict(
    forecast: ForecastResult,
    validation: ValidationResult,
) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    for key in MODULE_LABELS:
        mod = forecast.module_scores.get(key)
        if mod:
            modules.append(_module_to_dict(mod))

    cross: dict[str, Any] | None = None
    if forecast.cross_validation:
        cv = forecast.cross_validation
        cross = {
            "agreement": cv.agreement,
            "note": cv.note,
            "groups": [
                {
                    "name": g.name,
                    "label": g.label,
                    "score": g.score,
                    "direction": g.direction,
                    "modules": list(g.modules),
                }
                for g in cv.groups
            ],
        }

    return {
        "generated_at": forecast.generated_at.isoformat(timespec="seconds"),
        "data_cutoff": forecast.data_cutoff.isoformat() if forecast.data_cutoff else None,
        "total_score": forecast.total_score,
        "direction": forecast.direction,
        "week_outlook": forecast.week_outlook,
        "month_outlook": forecast.month_outlook,
        "confidence": forecast.confidence,
        "data_health": forecast.data_health,
        "confidence_note": forecast.confidence_note,
        "low_confidence": forecast.low_confidence,
        "modules": modules,
        "cross_validation": cross,
        "supporting_factors": list(forecast.supporting_factors),
        "suppressing_factors": list(forecast.suppressing_factors),
        "risks": list(forecast.risks),
        "invalidation_conditions": list(forecast.invalidation_conditions),
        "anomalies": [_anomaly_to_dict(a) for a in validation.anomalies],
    }


def timestamped_forecast_history_path(
    forecast_dir: Path,
    when: datetime | None = None,
) -> Path:
    when = when or datetime.now()
    stamp = when.strftime("%Y-%m-%d_%H%M%S")
    return forecast_dir / "history" / f"{stamp}.json"


def write_forecast_json(
    forecast: ForecastResult,
    validation: ValidationResult,
    forecast_dir: Path,
    when: datetime | None = None,
) -> tuple[Path, Path]:
    """Write latest.json and a history snapshot. Returns (latest, history)."""
    when = when or datetime.now()
    payload = forecast_to_dict(forecast, validation)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    forecast_dir.mkdir(parents=True, exist_ok=True)
    latest_path = forecast_dir / "latest.json"
    latest_path.write_text(text, encoding="utf-8")

    history_path = timestamped_forecast_history_path(forecast_dir, when=when)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(text, encoding="utf-8")

    return latest_path, history_path

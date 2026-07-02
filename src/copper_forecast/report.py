"""Generate Markdown forecast reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from copper_forecast.indicators import SignalDetail
from copper_forecast.scoring import ForecastResult
from copper_forecast.validator import ValidationIssue, ValidationResult

DEFAULT_REPORT_STEM = "live.md"
RUNS_SUBDIR = "runs"

MODULE_LABELS = {
    "china_demand": "中国需求",
    "inventory": "库存现货",
    "macro_liquidity": "美元利率",
    "global_cycle": "全球制造业",
    "supply": "供应扰动",
    "trend": "价格趋势",
}


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _format_signal_score(sig: SignalDetail) -> str:
    """Show confidence-adjusted score; expose raw score when discounted."""
    sign = "+" if sig.score > 0 else ""
    if sig.confidence and sig.raw_score is not None and sig.confidence != "A":
        raw_sign = "+" if sig.raw_score > 0 else ""
        return f"{sign}{sig.score:.1f} {sig.confidence} (raw {raw_sign}{sig.raw_score:.0f})"
    if abs(sig.score - round(sig.score)) < 1e-9:
        return f"{sign}{sig.score:.0f}"
    return f"{sign}{sig.score:.1f}"


def _score_bar(score: float) -> str:
    if score >= 0.5:
        return "🟢 强多"
    if score >= 0.2:
        return "🟡 偏多"
    if score <= -0.5:
        return "🔴 强空"
    if score <= -0.2:
        return "🟠 偏空"
    return "⚪ 中性"


def render_report(
    forecast: ForecastResult,
    validation: ValidationResult,
) -> str:
    lines: list[str] = [
        "# 伦敦铜走势判断报告",
        "",
        f"生成日期：{forecast.generated_at.strftime('%Y-%m-%d %H:%M')}",
        f"数据截止：{forecast.data_cutoff.isoformat() if forecast.data_cutoff else 'N/A'}",
        "",
        "## 结论",
        "",
        f"1 周判断：**{forecast.week_outlook}**",
        f"1 月判断：**{forecast.month_outlook}**",
        f"总分：**{forecast.total_score:+.3f}**（{forecast.direction}）",
        f"置信度：**{_pct(forecast.confidence)}**",
        f"数据健康度：**{_pct(forecast.data_health)}**",
    ]
    if forecast.confidence_note:
        lines.append(f"\n> ⚠ {forecast.confidence_note}")
    lines += [
        "",
        "## 模块分数",
        "",
        "| 模块 | 分数 | 状态 |",
        "|---|---:|---|",
    ]

    for key, label in MODULE_LABELS.items():
        mod = forecast.module_scores.get(key)
        if mod:
            gaps = f"（缺口: {len(mod.data_gaps)}）" if mod.data_gaps else ""
            lines.append(
                f"| {label} | {mod.score:+.3f} | {_score_bar(mod.score)}{gaps} |"
            )

    if forecast.cross_validation:
        lines.extend(["", "## A/B 交叉验证", ""])
        lines.append(f"结论：**{forecast.cross_validation.agreement}**。{forecast.cross_validation.note}")
        lines.extend(["", "| 组别 | 模块 | 分数 | 方向 |", "|---|---|---:|---|"])
        for group in forecast.cross_validation.groups:
            modules = "、".join(MODULE_LABELS.get(m, m) for m in group.modules)
            lines.append(
                f"| {group.label} | {modules} | {group.score:+.3f} | {group.direction} |"
            )

    lines.extend(["", "## 主要支撑", ""])
    for i, factor in enumerate(forecast.supporting_factors, 1):
        lines.append(f"{i}. {factor}")
    if not forecast.supporting_factors:
        lines.append("1. （暂无显著支撑因子）")

    lines.extend(["", "## 主要压制", ""])
    for i, factor in enumerate(forecast.suppressing_factors, 1):
        lines.append(f"{i}. {factor}")
    if not forecast.suppressing_factors:
        lines.append("1. （暂无显著压制因子）")

    lines.extend(["", "## 风险提示", ""])
    for i, risk in enumerate(forecast.risks, 1):
        lines.append(f"{i}. {risk}")

    lines.extend(["", "## 判断失效条件", ""])
    for i, cond in enumerate(forecast.invalidation_conditions, 1):
        lines.append(f"{i}. {cond}")

    lines.extend(["", "## 数据异常", ""])
    anomalies = validation.anomalies
    if anomalies:
        for i, issue in enumerate(anomalies[:10], 1):
            lines.append(
                f"{i}. [{issue.severity}] {issue.row.indicator} "
                f"({issue.row.date}): {issue.reason}"
            )
    else:
        lines.append("1. 无异常数据")

    lines.extend(["", "## 模块信号明细", ""])
    for key, label in MODULE_LABELS.items():
        mod = forecast.module_scores.get(key)
        if not mod or not mod.signals:
            continue
        lines.append(f"### {label}")
        lines.append("")
        for sig in mod.signals:
            lines.append(f"- [{_format_signal_score(sig)}] {sig.description}")
        if mod.data_gaps:
            lines.append(f"- ⚠ 数据缺口: {', '.join(mod.data_gaps)}")
        lines.append("")

    lines.append("---")
    lines.append("*本报告由 copper-forecast MVP 生成，仅供研究参考，不构成投资建议。*")
    return "\n".join(lines)


def timestamped_report_path(
    reports_dir: Path,
    when: datetime | None = None,
) -> Path:
    """Return a non-destructive report path under reports/runs/."""
    when = when or datetime.now()
    stamp = when.strftime("%Y-%m-%d_%H%M%S")
    return reports_dir / RUNS_SUBDIR / f"live_{stamp}.md"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

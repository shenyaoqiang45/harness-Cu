"""Compute module scores from validated indicator data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

from copper_forecast.data_loader import DataRow, group_by_indicator, load_supply_events


@dataclass
class SignalDetail:
    name: str
    score: float
    description: str
    confidence: str | None = None
    raw_score: float | None = None


@dataclass
class ModuleScore:
    module: str
    score: float
    signals: list[SignalDetail] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)


def _latest_numeric(series: list[DataRow]) -> tuple[date | None, float | None]:
    nums = [(r.date, r.numeric_value) for r in series if r.numeric_value is not None]
    if not nums:
        return None, None
    d, v = nums[-1]
    return d, v


def _latest_preferred_numeric(
    series: list[DataRow], blocked_source_terms: tuple[str, ...]
) -> tuple[date | None, float | None, DataRow | None]:
    nums = [r for r in series if r.numeric_value is not None]
    if not nums:
        return None, None, None

    preferred = [
        r
        for r in nums
        if not any(term in r.source for term in blocked_source_terms)
    ]
    row = preferred[-1] if preferred else nums[-1]
    return row.date, row.numeric_value, row


def _value_n_days_ago(series: list[DataRow], n: int) -> float | None:
    nums = [(r.date, r.numeric_value) for r in series if r.numeric_value is not None]
    # P0 fix: when history is insufficient, return None instead of falling back
    # to the current value. The old fallback made prev == current, which turned
    # a flat / data-missing momentum into a spurious bearish (-1) signal.
    if len(nums) <= n:
        return None
    return nums[-1 - n][1]


# Momentum tolerance: changes within +/- this band are treated as flat (neutral).
MOM_FLAT_TOL = 1e-9


def _mom_score(current: float, previous: float, tol: float = MOM_FLAT_TOL) -> float:
    """Momentum sign with a flat band. Returns +1 / -1 / 0 (neutral)."""
    delta = current - previous
    if abs(delta) <= tol:
        return 0.0
    return 1.0 if delta > 0 else -1.0


def _same_source_prev(series: list[DataRow]) -> tuple[float | None, bool]:
    """Return the previous numeric value and whether it shares the latest row's
    source. Used to suppress momentum signals computed across a source switch
    (e.g. FRED history spliced with a different statistical agency print), where
    a month-over-month difference is not comparable.
    """
    nums = [r for r in series if r.numeric_value is not None]
    if len(nums) < 2:
        return None, False
    latest, prev = nums[-1], nums[-2]
    same = (latest.source or "").strip().lower() == (prev.source or "").strip().lower()
    return prev.numeric_value, same


def _ma(series: list[DataRow], window: int) -> float | None:
    nums = [r.numeric_value for r in series if r.numeric_value is not None]
    if len(nums) < window:
        return None
    return sum(nums[-window:]) / window


def _pct_change(series: list[DataRow], days: int) -> float | None:
    nums = [r.numeric_value for r in series if r.numeric_value is not None]
    if len(nums) <= days:
        return None
    old, new = nums[-1 - days], nums[-1]
    if old == 0:
        return None
    return (new - old) / old


def _abs_change(series: list[DataRow], periods: int) -> float | None:
    nums = [r.numeric_value for r in series if r.numeric_value is not None]
    if len(nums) <= periods:
        return None
    old, new = nums[-1 - periods], nums[-1]
    return new - old


def _avg_signals(signals: list[SignalDetail]) -> float:
    if not signals:
        return 0.0
    return sum(s.score for s in signals) / len(signals)


def _value_on_or_before(observations: list[tuple[date, float]], target: date) -> float | None:
    last: float | None = None
    for d, v in observations:
        if d > target:
            break
        last = v
    return last


def _global_inventory_series(
    grouped: dict[str, list[DataRow]],
    inv_keys: list[str],
) -> list[tuple[date, float]]:
    """Sum exchange inventories by date; forward-fill each venue to align stale prints."""
    per_exchange: dict[str, list[tuple[date, float]]] = {}
    all_dates: set[date] = set()
    for key in inv_keys:
        series = grouped.get(key, [])
        obs = sorted(
            (r.date, r.numeric_value) for r in series if r.numeric_value is not None
        )
        if obs:
            per_exchange[key] = obs
            all_dates.update(d for d, _ in obs)

    if not per_exchange:
        return []

    totals: list[tuple[date, float]] = []
    for d in sorted(all_dates):
        total = 0.0
        contributors = 0
        for obs in per_exchange.values():
            v = _value_on_or_before(obs, d)
            if v is not None:
                total += v
                contributors += 1
        if contributors:
            totals.append((d, total))
    return totals


def _percentile_rank(series: list[DataRow], lookback: int = 756) -> float | None:
    """Approximate percentile rank over lookback observations (~3 years daily)."""
    nums = [r.numeric_value for r in series if r.numeric_value is not None]
    if not nums:
        return None
    window = nums[-lookback:] if len(nums) >= lookback else nums
    current = window[-1]
    below = sum(1 for v in window if v < current)
    return below / len(window)


def score_trend(grouped: dict[str, list[DataRow]]) -> ModuleScore:
    series = grouped.get("lme_copper_price", [])
    signals: list[SignalDetail] = []
    gaps: list[str] = []

    if not series:
        return ModuleScore("trend", 0.0, data_gaps=["lme_copper_price missing"])

    _, price = _latest_numeric(series)
    if price is None:
        return ModuleScore("trend", 0.0, data_gaps=["lme_copper_price not numeric"])

    for window, label in [(20, "20d"), (60, "60d"), (120, "120d")]:
        ma = _ma(series, window)
        if ma is None:
            gaps.append(f"MA{window} insufficient history")
            continue
        score = 1.0 if price > ma else -1.0
        signals.append(
            SignalDetail(
                f"price_vs_ma{window}",
                score,
                f"Price {price:.0f} {'>' if score > 0 else '<='} MA{window} ({ma:.0f})",
            )
        )

    for days, label in [(20, "20d"), (60, "60d")]:
        ret = _pct_change(series, days)
        if ret is None:
            gaps.append(f"{label} return insufficient history")
            continue
        score = 1.0 if ret > 0 else -1.0
        signals.append(
            SignalDetail(
                f"return_{label}",
                score,
                f"{label} return {ret:+.2%}",
            )
        )

    return ModuleScore("trend", _avg_signals(signals), signals, gaps)


def score_inventory(grouped: dict[str, list[DataRow]]) -> ModuleScore:
    signals: list[SignalDetail] = []
    gaps: list[str] = []

    inv_keys = ["lme_inventory", "shfe_inventory", "comex_inventory"]
    gaps: list[str] = []
    for key in inv_keys:
        if not grouped.get(key):
            gaps.append(f"{key} missing")

    global_series = _global_inventory_series(grouped, inv_keys)
    if global_series:
        global_rows = [
            DataRow(
                d,
                "global_inventory",
                v,
                "ton",
                "",
                "",
                __import__("datetime").datetime.min,
                "daily",
                "B",
            )
            for d, v in global_series
        ]

        for days, label in [(20, "20d"), (60, "60d")]:
            chg = _pct_change(global_rows, days)
            if chg is None:
                gaps.append(f"global inventory {label} change unavailable")
                continue
            score = -1.0 if chg > 0 else 1.0  # falling inventory = bullish
            signals.append(
                SignalDetail(
                    f"global_inv_chg_{label}",
                    score,
                    f"Global inventory {label} change {chg:+.2%}",
                )
            )

        pct = _percentile_rank(global_rows)
        if pct is not None:
            if pct <= 0.25:
                signals.append(
                    SignalDetail(
                        "inv_low_percentile",
                        1.0,
                        f"Global inventory at {pct:.0%} 3y percentile (low)",
                    )
                )
            elif pct >= 0.75:
                signals.append(
                    SignalDetail(
                        "inv_high_percentile",
                        -1.0,
                        f"Global inventory at {pct:.0%} 3y percentile (high)",
                    )
                )

    premium_series = grouped.get("spot_premium", [])
    premium_is_derived = False
    if premium_series:
        last_prem_row = premium_series[-1]
        premium_is_derived = "derived" in (last_prem_row.source or "").lower()
        _, prem = _latest_numeric(premium_series)
        if prem is not None:
            score = 1.0 if prem > 0 else -1.0
            # P0 fix: this series is the SHFE-vs-COMEX cross-market spread
            # (derived in fetchers/derived.py), NOT a physical spot-vs-futures
            # premium. Label it accurately and drop the contradictory
            # "contango/premium" wording.
            stance = "SHFE rich vs COMEX" if prem > 0 else "SHFE cheap vs COMEX"
            signals.append(
                SignalDetail(
                    "shfe_comex_spread",
                    score,
                    f"SHFE-COMEX spread {prem:+.1f} USD/ton ({stance})",
                )
            )

    term_series = grouped.get("term_structure", [])
    if term_series:
        last_term_row = term_series[-1]
        term_is_derived = "derived" in (last_term_row.source or "").lower()
        # P0 fix: when term_structure is mechanically derived from the sign of
        # spot_premium (see fetchers/derived.py: premium_to_curve), it carries
        # no information independent of the spread signal above. Counting it as
        # a separate vote double-counts the same spread. Only score it when it
        # comes from an independent (non-derived) source, or when the spread
        # signal itself is absent.
        independent = not (term_is_derived and premium_is_derived and premium_series)
        if independent:
            label = str(last_term_row.value).lower()
            if label == "backwardation":
                signals.append(
                    SignalDetail("term_structure", 1.0, "Term structure: backwardation")
                )
            elif label == "contango":
                signals.append(
                    SignalDetail("term_structure", -1.0, "Term structure: contango")
                )

    if not signals:
        return ModuleScore("inventory", 0.0, data_gaps=gaps or ["no inventory data"])

    return ModuleScore("inventory", _avg_signals(signals), signals, gaps)


def score_china_demand(grouped: dict[str, list[DataRow]]) -> ModuleScore:
    signals: list[SignalDetail] = []
    gaps: list[str] = []

    pmi_series = grouped.get("china_pmi", [])
    if pmi_series:
        _, pmi = _latest_numeric(pmi_series)
        prev, same_src = _same_source_prev(pmi_series)
        if pmi is not None:
            signals.append(
                SignalDetail(
                    "china_pmi_level",
                    1.0 if pmi > 50 else -1.0,
                    f"China PMI {pmi:.1f}",
                )
            )
        if pmi is not None and prev is not None and same_src:
            mom = _mom_score(pmi, prev)
            if mom != 0.0:
                signals.append(
                    SignalDetail(
                        "china_pmi_mom",
                        mom,
                        f"China PMI mom {pmi - prev:+.1f}",
                    )
                )
        elif pmi is not None and prev is not None and not same_src:
            gaps.append("china_pmi mom skipped (source switch, not comparable)")
    else:
        gaps.append("china_pmi missing")

    no_series = grouped.get("china_new_orders_pmi", [])
    if no_series:
        _, no_pmi = _latest_numeric(no_series)
        if no_pmi is not None:
            signals.append(
                SignalDetail(
                    "new_orders_pmi",
                    1.0 if no_pmi > 50 else -1.0,
                    f"New orders PMI {no_pmi:.1f}",
                )
            )
    else:
        gaps.append("china_new_orders_pmi missing")

    sf_series = grouped.get("social_financing", [])
    m1_series = grouped.get("m1", [])
    sf_improved = False
    if sf_series:
        _, sf = _latest_numeric(sf_series)
        prev_sf = _value_n_days_ago(sf_series, 1)
        if sf is not None and prev_sf is not None:
            sf_improved = sf > prev_sf
    if m1_series:
        _, m1 = _latest_numeric(m1_series)
        prev_m1 = _value_n_days_ago(m1_series, 1)
        if m1 is not None and prev_m1 is not None and m1 > prev_m1:
            sf_improved = True
    if sf_series or m1_series:
        signals.append(
            SignalDetail(
                "credit_impulse",
                1.0 if sf_improved else -1.0,
                "Social financing / M1 improving" if sf_improved else "Credit/M1 not improving",
            )
        )
    else:
        gaps.append("social_financing / m1 missing")

    grid_series = grouped.get("grid_investment", [])
    if grid_series:
        _, grid, grid_row = _latest_preferred_numeric(grid_series, ("代理",))
        if grid is not None:
            source_note = f" ({grid_row.source})" if grid_row else ""
            signals.append(
                SignalDetail(
                    "grid_investment",
                    1.0 if grid > 0 else -1.0,
                    f"Grid investment YoY {grid:+.1f}%{source_note}",
                )
            )
    else:
        gaps.append("grid_investment missing")

    return ModuleScore(
        "china_demand",
        _avg_signals(signals) if signals else 0.0,
        signals,
        gaps,
    )


def score_macro_liquidity(grouped: dict[str, list[DataRow]]) -> ModuleScore:
    signals: list[SignalDetail] = []
    gaps: list[str] = []

    for key, label in [("dxy", "DXY"), ("us_10y_real_rate", "US 10Y real rate")]:
        series = grouped.get(key, [])
        if not series:
            gaps.append(f"{key} missing")
            continue
        for days in (20, 60):
            chg = _pct_change(series, days)
            if chg is None:
                gaps.append(f"{key} {days}d change unavailable")
                continue
            # Falling DXY / real rates = bullish for copper
            score = 1.0 if chg < 0 else -1.0
            signals.append(
                SignalDetail(
                    f"{key}_{days}d",
                    score,
                    f"{label} {days}d change {chg:+.2%}",
                )
            )

    return ModuleScore(
        "macro_liquidity",
        _avg_signals(signals) if signals else 0.0,
        signals,
        gaps,
    )


def score_global_cycle(grouped: dict[str, list[DataRow]]) -> ModuleScore:
    signals: list[SignalDetail] = []
    gaps: list[str] = []

    for key, label in [
        ("us_ism_manufacturing", "US ISM"),
        ("global_manufacturing_pmi", "Global PMI"),
    ]:
        series = grouped.get(key, [])
        if not series:
            gaps.append(f"{key} missing")
            continue
        _, val = _latest_numeric(series)
        prev, same_src = _same_source_prev(series)
        if val is not None:
            signals.append(
                SignalDetail(
                    f"{key}_level",
                    1.0 if val > 50 else -1.0,
                    f"{label} {val:.1f}",
                )
            )
        # P1 fix: skip mom across a source switch (e.g. derived -> S&P Global);
        # P0 fix: flat / insufficient history yields no momentum signal.
        if val is not None and prev is not None and same_src:
            mom = _mom_score(val, prev)
            if mom != 0.0:
                signals.append(
                    SignalDetail(
                        f"{key}_mom",
                        mom,
                        f"{label} mom {val - prev:+.1f}",
                    )
                )
        elif val is not None and prev is not None and not same_src:
            gaps.append(f"{key} mom skipped (source switch, not comparable)")

    korea = grouped.get("korea_exports_yoy", [])
    if korea:
        _, val = _latest_numeric(korea)
        # P1 fix: only compute the month-over-month "improving" signal when the
        # latest point shares the same source as the previous one. The history
        # comes from FRED while the latest print may come from a national
        # statistics agency on a different basis, making the diff non-comparable.
        prev, same_src = _same_source_prev(korea)
        if val is not None and prev is not None and same_src:
            mom = _mom_score(val, prev)
            if mom != 0.0:
                signals.append(
                    SignalDetail(
                        "korea_exports",
                        mom,
                        f"Korea exports YoY {val:+.1f}% "
                        f"({'improving' if mom > 0 else 'deteriorating'})",
                    )
                )
        elif val is not None and prev is not None and not same_src:
            gaps.append("korea_exports_yoy mom skipped (source switch, not comparable)")
    else:
        gaps.append("korea_exports_yoy missing")

    return ModuleScore(
        "global_cycle",
        _avg_signals(signals) if signals else 0.0,
        signals,
        gaps,
    )


def score_supply(
    grouped: dict[str, list[DataRow]],
    events_path: str | None = None,
) -> ModuleScore:
    signals: list[SignalDetail] = []
    gaps: list[str] = []

    tc_series = grouped.get("tc_rc_spot", [])
    if tc_series:
        delta = _abs_change(tc_series, 1)
        pct = _percentile_rank(tc_series, lookback=36)
        if delta is not None:
            # Falling spot TC (USD/ton) = tighter concentrate = bullish
            score = 1.0 if delta < 0 else -1.0
            signals.append(
                SignalDetail(
                    "tc_rc_spot_change",
                    score,
                    f"TC/RC spot mom Δ {delta:+.1f} USD/ton",
                )
            )
        if pct is not None and pct <= 0.25:
            signals.append(
                SignalDetail(
                    "tc_rc_spot_low",
                    1.0,
                    f"TC/RC spot at {pct:.0%} historical percentile (low)",
                )
            )
    else:
        gaps.append("tc_rc_spot missing")

    if events_path:
        from pathlib import Path

        for event in load_supply_events(Path(events_path)):
            raw = float(event["score"])
            conf = event["confidence"]
            conf_mult = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4}.get(conf, 0.5)
            adj_score = max(-1.0, min(1.0, raw * conf_mult))
            signals.append(
                SignalDetail(
                    event["event"],
                    adj_score,
                    f"{event['note']} (source: {event['source']})",
                    confidence=conf,
                    raw_score=raw,
                )
            )

    return ModuleScore(
        "supply",
        _avg_signals(signals) if signals else 0.0,
        signals,
        gaps,
    )


def compute_all_module_scores(
    confirmed_rows: list[DataRow],
    config_dir: str | None = None,
) -> dict[str, ModuleScore]:
    """Compute scores for all six modules."""
    grouped = group_by_indicator(confirmed_rows)
    events_path = None
    if config_dir:
        from pathlib import Path

        cfg_path = Path(config_dir)
        with (cfg_path / "indicators.yaml").open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        raw_events = cfg.get("modules", {}).get("supply", {}).get("events_file")
        if raw_events:
            events_path = str(cfg_path.parent / raw_events)

    return {
        "trend": score_trend(grouped),
        "inventory": score_inventory(grouped),
        "china_demand": score_china_demand(grouped),
        "macro_liquidity": score_macro_liquidity(grouped),
        "global_cycle": score_global_cycle(grouped),
        "supply": score_supply(grouped, events_path),
    }

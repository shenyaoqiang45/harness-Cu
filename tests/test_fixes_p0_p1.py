"""Regression tests for the P0/P1 fixes.

P0-1: momentum no longer fabricated from a single data point (flat/insufficient
      history must NOT produce a bearish -1 signal).
P0-2: term_structure derived from spot_premium sign must not be double-counted;
      spot_premium label must not say the contradictory "contango/premium".
P1-1: source switch suppresses month-over-month momentum signals.
P1-2: low confidence / cross-validation divergence downgrades the outlook.
"""

from datetime import date, datetime

from copper_forecast.data_loader import DataRow
from copper_forecast.indicators import (
    _value_n_days_ago,
    _mom_score,
    _same_source_prev,
    score_inventory,
    score_global_cycle,
)
from copper_forecast.scoring import _hedge_outlook


def _row(indicator, d, value, source="test", unit="index", freq="monthly"):
    return DataRow(
        date=d,
        indicator=indicator,
        value=value,
        unit=unit,
        source=source,
        source_url="https://example.com",
        updated_at=datetime.combine(d, datetime.min.time()),
        frequency=freq,
        confidence="A",
        status="confirmed",
    )


# ---------- P0-1: momentum regression ----------

def test_value_n_days_ago_returns_none_when_history_insufficient():
    series = [_row("us_ism_manufacturing", date(2026, 5, 1), 54.0)]
    # Only one point -> previous value must be None, not the current value.
    assert _value_n_days_ago(series, 1) is None


def test_mom_score_flat_is_neutral():
    assert _mom_score(54.0, 54.0) == 0.0
    assert _mom_score(55.0, 54.0) == 1.0
    assert _mom_score(53.0, 54.0) == -1.0


def test_single_point_ism_produces_no_momentum_signal():
    grouped = {"us_ism_manufacturing": [_row("us_ism_manufacturing", date(2026, 5, 1), 54.0)]}
    mod = score_global_cycle(grouped)
    names = {s.name for s in mod.signals}
    # Level signal present, but NO fabricated mom signal.
    assert "us_ism_manufacturing_level" in names
    assert "us_ism_manufacturing_mom" not in names


# ---------- P1-1: source-switch suppresses momentum ----------

def test_same_source_prev_detects_switch():
    series = [
        _row("korea_exports_yoy", date(2026, 4, 1), 48.8, source="FRED", unit="pct"),
        _row("korea_exports_yoy", date(2026, 5, 1), 53.2, source="MOTIE", unit="pct"),
    ]
    prev, same = _same_source_prev(series)
    assert prev == 48.8
    assert same is False


def test_korea_momentum_skipped_on_source_switch():
    grouped = {
        "korea_exports_yoy": [
            _row("korea_exports_yoy", date(2026, 4, 1), 48.8, source="FRED", unit="pct"),
            _row("korea_exports_yoy", date(2026, 5, 1), 53.2, source="MOTIE", unit="pct"),
        ]
    }
    mod = score_global_cycle(grouped)
    names = {s.name for s in mod.signals}
    assert "korea_exports" not in names  # not comparable across sources


def test_global_pmi_momentum_kept_when_same_source():
    grouped = {
        "global_manufacturing_pmi": [
            _row("global_manufacturing_pmi", date(2026, 5, 1), 49.5, source="S&P Global"),
            _row("global_manufacturing_pmi", date(2026, 6, 1), 50.3, source="S&P Global"),
        ]
    }
    mod = score_global_cycle(grouped)
    moms = [s for s in mod.signals if s.name == "global_manufacturing_pmi_mom"]
    assert len(moms) == 1
    assert moms[0].score == 1.0  # 49.5 -> 50.3 is a real improvement


# ---------- P0-2: term_structure de-dup & label ----------

def test_derived_term_structure_not_double_counted():
    grouped = {
        "spot_premium": [
            _row("spot_premium", date(2026, 6, 29), 1791.98, source="derived", unit="USD/ton", freq="daily"),
        ],
        "term_structure": [
            _row("term_structure", date(2026, 6, 29), "backwardation", source="derived", unit="label", freq="daily"),
        ],
    }
    mod = score_inventory(grouped)
    names = [s.name for s in mod.signals]
    # The spread is counted once; the derived term_structure is suppressed.
    assert "shfe_comex_spread" in names
    assert "term_structure" not in names


def test_spot_premium_label_has_no_contradictory_contango_premium():
    grouped = {
        "spot_premium": [
            _row("spot_premium", date(2026, 6, 29), 1791.98, source="derived", unit="USD/ton", freq="daily"),
        ],
    }
    mod = score_inventory(grouped)
    spread = next(s for s in mod.signals if s.name == "shfe_comex_spread")
    assert "contango/premium" not in spread.description
    assert "SHFE-COMEX spread" in spread.description


def test_independent_term_structure_still_counts():
    grouped = {
        "term_structure": [
            _row("term_structure", date(2026, 6, 29), "backwardation", source="LME", unit="label", freq="daily"),
        ],
    }
    mod = score_inventory(grouped)
    names = [s.name for s in mod.signals]
    assert "term_structure" in names  # independent source is still scored


# ---------- P1-2: low-confidence outlook downgrade ----------

def test_hedge_outlook_downgrades_directional_labels():
    assert _hedge_outlook("偏多") == "中性偏多（低置信）"
    assert _hedge_outlook("偏空") == "中性偏空（低置信）"
    assert _hedge_outlook("中性") == "中性"

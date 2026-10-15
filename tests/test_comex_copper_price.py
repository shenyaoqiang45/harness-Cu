"""COMEX copper price stays in USD/lb and is visible in the report."""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml

from copper_forecast.data_loader import DataRow
from copper_forecast.fetchers.yahoo import LB_TO_TON, fetch_eastmoney_quote_fallback, fetch_yahoo
from copper_forecast.indicators import ModuleScore
from copper_forecast.report import render_report
from copper_forecast.scoring import PriceQuote, compute_forecast, copper_price_quotes
from copper_forecast.validator import ValidationResult, validate_rows

CONFIG = Path(__file__).resolve().parents[1] / "config"


def _modules() -> dict[str, ModuleScore]:
    return {name: ModuleScore(name, 0.0) for name in (
        "china_demand",
        "inventory",
        "macro_liquidity",
        "global_cycle",
        "supply",
        "trend",
    )}


def _row(
    indicator: str,
    value: float,
    day: str = "2026-10-14",
    unit: str = "USD/lb",
    source: str = "Yahoo Finance",
) -> DataRow:
    return DataRow(
        date=date.fromisoformat(day),
        indicator=indicator,
        value=value,
        unit=unit,
        source=source,
        source_url="https://finance.yahoo.com/quote/HG=F",
        updated_at=datetime(2026, 10, 15, 8, 0, 0),
        frequency="daily",
        confidence="B",
    )


def test_sources_config_reuses_yahoo_without_unit_conversion():
    with (CONFIG / "sources.yaml").open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)["sources"]["yahoo"]["indicators"]["comex_copper_price"]
    assert cfg["ticker"] == "HG=F"
    assert cfg["unit"] == "USD/lb"
    assert cfg["frequency"] == "daily"
    assert "transform" not in cfg


def test_yahoo_fetcher_keeps_hg_close_in_usd_per_lb(monkeypatch):
    frame = pd.DataFrame({"Date": [pd.Timestamp("2026-10-14")], "Close": [5.5]})
    monkeypatch.setattr(
        "copper_forecast.fetchers.yahoo._history",
        lambda ticker, lookback: frame,
    )
    with (CONFIG / "sources.yaml").open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)["sources"]["yahoo"]["indicators"]["comex_copper_price"]
    result = fetch_yahoo({"comex_copper_price": cfg}, 30)
    assert result.errors == []
    assert len(result.records) == 1
    record = result.records[0]
    assert record.date == date(2026, 10, 14)
    assert record.value == 5.5
    assert record.value != round(5.5 * LB_TO_TON, 4)
    assert record.unit == "USD/lb"
    assert record.source == "Yahoo Finance"
    assert record.frequency == "daily"


def test_eastmoney_fallback_does_not_convert_raw_comex_price(monkeypatch):
    monkeypatch.setattr(
        "copper_forecast.fetchers.yahoo._eastmoney_klines",
        lambda secid, limit: ["2026-10-14,6.70,5.50,6.80,5.40,1000,0"],
    )
    with (CONFIG / "sources.yaml").open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)["sources"]["yahoo"]["indicators"]["comex_copper_price"]
    result = fetch_eastmoney_quote_fallback(
        "comex_copper_price",
        cfg,
        30,
        before=date(2026, 10, 15),
    )
    assert result.records[0].value == 5.5
    assert result.records[0].unit == "USD/lb"
    assert "Not converted" in result.records[0].note


def test_validation_accepts_lb_price_and_flags_ton_scale_and_jump():
    ok = validate_rows([_row("comex_copper_price", 5.5)], CONFIG)
    assert len(ok.confirmed) == 1
    assert ok.pending == []

    ton_scale = validate_rows([_row("comex_copper_price", 14000)], CONFIG)
    assert ton_scale.confirmed == []
    assert any("USD/lb" in issue.reason for issue in ton_scale.pending)

    jump = validate_rows(
        [
            _row("comex_copper_price", 5.0, day="2026-10-13"),
            _row("comex_copper_price", 6.0, day="2026-10-14"),
        ],
        CONFIG,
    )
    pending_days = {issue.row.date.isoformat() for issue in jump.pending}
    assert pending_days == {"2026-10-14"}


def test_missing_comex_price_is_marked_in_the_report():
    london = _row("lme_copper_price", 14561.5, unit="USD/ton", source="Yahoo Finance")
    quotes = copper_price_quotes([london], CONFIG)
    missing = next(quote for quote in quotes if quote.indicator == "comex_copper_price")
    assert missing.missing is True
    assert missing.date is None
    assert missing.unit == "USD/lb"

    forecast = compute_forecast(_modules(), ValidationResult(confirmed=[london]), [london], CONFIG)
    text = render_report(forecast, ValidationResult(confirmed=[london]))
    assert "| comex_copper_price | 缺失 | — | USD/lb | — |" in text
    assert "| lme_copper_price | 2026-10-14 | 14561.5000 | USD/ton | Yahoo Finance |" in text
    assert "USD/lb" in text


def test_report_shows_comex_observation_date_and_source():
    forecast = compute_forecast(
        _modules(),
        ValidationResult(),
        [],
        CONFIG,
    )
    forecast.price_quotes = [
        PriceQuote(
            indicator="comex_copper_price",
            unit="USD/lb",
            date=date(2026, 10, 14),
            value=5.5,
            source="Yahoo Finance",
        )
    ]
    text = render_report(forecast, ValidationResult())
    assert "| comex_copper_price | 2026-10-14 | 5.5000 | USD/lb | Yahoo Finance |" in text

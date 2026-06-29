"""Generate sample CSV data for MVP demo."""

import csv
from datetime import date, datetime, timedelta
from pathlib import Path


def generate() -> Path:
    root = Path(__file__).resolve().parents[1] / "data" / "raw"
    root.mkdir(parents=True, exist_ok=True)
    out = root / "sample.csv"

    start = date(2026, 2, 1)
    end = date(2026, 6, 29)
    days = (end - start).days + 1

    def rows():
        price = 9200.0
        lme_inv = 110000.0
        shfe_inv = 85000.0
        comex_inv = 25000.0
        dxy = 104.5
        real_rate = 2.1
        for i in range(days):
            d = start + timedelta(days=i)
            price += 8 if i % 7 < 4 else -3
            lme_inv += -200 if i % 5 < 3 else 150
            shfe_inv += -150 if i % 6 < 3 else 100
            comex_inv += -50 if i % 8 < 4 else 40
            dxy += -0.05 if i % 10 < 5 else 0.08
            real_rate += -0.01 if i % 12 < 6 else 0.015
            ts = datetime.combine(d, datetime.min.time()).isoformat()
            base = {
                "source": "sample_feed",
                "source_url": "https://example.com",
                "updated_at": ts,
                "confidence": "B",
            }

            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "lme_copper_price",
                "value": round(price, 2),
                "unit": "USD/ton",
                "frequency": "daily",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "lme_inventory",
                "value": round(lme_inv),
                "unit": "ton",
                "frequency": "daily",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "shfe_inventory",
                "value": round(shfe_inv),
                "unit": "ton",
                "frequency": "daily",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "comex_inventory",
                "value": round(comex_inv),
                "unit": "ton",
                "frequency": "daily",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "dxy",
                "value": round(dxy, 3),
                "unit": "index",
                "frequency": "daily",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "us_10y_real_rate",
                "value": round(real_rate, 3),
                "unit": "pct",
                "frequency": "daily",
            }
            prem = 45 if i % 9 < 6 else -20
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "spot_premium",
                "value": prem,
                "unit": "USD/ton",
                "frequency": "daily",
            }
            term = "backwardation" if i % 11 < 7 else "contango"
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "term_structure",
                "value": term,
                "unit": "label",
                "frequency": "daily",
            }

        months = [date(2026, m, 28) for m in range(1, 7)]
        pmi_vals = [49.2, 49.8, 50.1, 50.4, 50.6, 51.0]
        for d, pmi in zip(months, pmi_vals):
            ts = datetime.combine(d, datetime.min.time()).isoformat()
            base = {
                "source": "nbs",
                "source_url": "https://example.com/nbs",
                "updated_at": ts,
                "confidence": "A",
                "frequency": "monthly",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "china_pmi",
                "value": pmi,
                "unit": "index",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "china_new_orders_pmi",
                "value": pmi + 0.5,
                "unit": "index",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "social_financing",
                "value": 2100 + d.month * 50,
                "unit": "CNY_bn",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "m1",
                "value": 68000 + d.month * 200,
                "unit": "CNY_bn",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "grid_investment",
                "value": -2 + d.month,
                "unit": "CNY_bn_yoy_pct",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "us_ism_manufacturing",
                "value": 48 + d.month * 0.5,
                "unit": "index",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "global_manufacturing_pmi",
                "value": 49.5 + d.month * 0.3,
                "unit": "index",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "korea_exports_yoy",
                "value": -5 + d.month * 2,
                "unit": "pct",
            }
            yield {
                **base,
                "date": d.isoformat(),
                "indicator": "tc_rc",
                "value": 85 - d.month,
                "unit": "USD/ton",
            }

    cols = [
        "date",
        "indicator",
        "value",
        "unit",
        "source",
        "source_url",
        "updated_at",
        "frequency",
        "confidence",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows())
    return out


if __name__ == "__main__":
    path = generate()
    print(f"Generated {path}")

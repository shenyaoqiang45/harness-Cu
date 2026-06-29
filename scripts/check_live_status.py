import csv
from collections import defaultdict
from pathlib import Path

rows = list(csv.DictReader(Path("data/raw/live.csv").open(encoding="utf-8")))
by_ind = defaultdict(list)
sources = {}
for r in rows:
    by_ind[r["indicator"]].append(r["date"])
    sources[r["indicator"]] = r["source"]

for k in sorted(by_ind):
    d = sorted(by_ind[k])
    print(f"{k}\t{len(d)}\t{d[0]}..{d[-1]}\t{sources[k]}")

print("---MISSING---")
expected = [
    "china_pmi", "china_new_orders_pmi", "social_financing", "m1", "grid_investment",
    "lme_inventory", "shfe_inventory", "comex_inventory", "spot_premium", "term_structure",
    "dxy", "us_10y_real_rate", "us_ism_manufacturing", "global_manufacturing_pmi",
    "korea_exports_yoy", "tc_rc_spot", "lme_copper_price",
]
for e in expected:
    if e not in by_ind:
        print(e)

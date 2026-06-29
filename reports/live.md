# 伦敦铜走势判断报告

生成日期：2026-06-29 16:02
数据截止：2026-06-30

## 结论

1 周判断：**中性**
1 月判断：**中性**
总分：**+0.160**（中性）
置信度：**4%**
数据健康度：**87%**

## 模块分数

| 模块 | 分数 | 状态 |
|---|---:|---|
| 中国需求 | +0.200 | 🟡 偏多 |
| 库存现货 | +1.000 | 🟢 强多（缺口: 1） |
| 美元利率 | -1.000 | 🔴 强空 |
| 全球制造业 | -0.600 | 🔴 强空 |
| 供应扰动 | +1.000 | 🟢 强多 |
| 价格趋势 | +0.200 | 🟡 偏多 |

## A/B 交叉验证

结论：**相互背离**。A/B 两组方向冲突，方向置信度应下调

| 组别 | 模块 | 分数 | 方向 |
|---|---|---:|---|
| 基本面/现货组 | 中国需求、库存现货、供应扰动 | +0.631 | 看多 |
| 宏观/价格组 | 美元利率、全球制造业、价格趋势 | -0.714 | 看空 |

## 主要支撑

1. [trend] Price 13690 > MA60 (13607)
2. [trend] Price 13690 > MA120 (13185)
3. [trend] 60d return +10.41%

## 主要压制

1. [trend] Price 13690 <= MA20 (13965)
2. [trend] 20d return -2.36%
3. [macro_liquidity] US 10Y real rate 60d change +9.50%

## 风险提示

1. 多空模块严重分裂，方向判断不确定性较高
2. inventory 存在数据缺口: comex_inventory missing

## 判断失效条件

1. 任一核心模块分数突破 ±0.5 将触发方向调整
2. 库存或宏观流动性出现单边趋势性变化
3. 中国需求数据出现方向性拐点

## 数据异常

1. [pending] lme_copper_price (2025-07-08): LME copper daily change > 8%
2. [pending] lme_copper_price (2025-07-31): LME copper daily change > 8%

## 模块信号明细

### 中国需求

- [-1] China PMI 50.0
- [-1] China PMI mom -0.3
- [+1] New orders PMI 51.8
- [+1] Social financing / M1 improving
- [+1] Grid investment YoY +43.3% (国家能源局)

### 库存现货

- [+1] Global inventory 20d change -84.91%
- [+1] Global inventory 60d change -87.14%
- [+1] Global inventory at 0% 3y percentile (low)
- [+1] Spot premium +1413.6 (contango/premium)
- [+1] Term structure: backwardation
- ⚠ 数据缺口: comex_inventory missing

### 美元利率

- [-1] DXY 20d change +2.33%
- [-1] DXY 60d change +1.57%
- [-1] US 10Y real rate 20d change +4.78%
- [-1] US 10Y real rate 60d change +9.50%

### 全球制造业

- [-1] US ISM 48.5
- [-1] US ISM mom +0.0
- [+1] Global PMI 50.2
- [-1] Global PMI mom -0.1
- [-1] Korea exports YoY +48.8% (deteriorating)

### 供应扰动

- [+1] TC/RC at 0% historical percentile (low)
- [+1] confirmed strike at major mine (source: official_news)

### 价格趋势

- [-1] Price 13690 <= MA20 (13965)
- [+1] Price 13690 > MA60 (13607)
- [+1] Price 13690 > MA120 (13185)
- [-1] 20d return -2.36%
- [+1] 60d return +10.41%

---
*本报告由 copper-forecast MVP 生成，仅供研究参考，不构成投资建议。*
# 伦敦铜走势判断报告

生成日期：2026-06-29 14:55
数据截止：2026-06-29

## 结论

1 周判断：**中性**
1 月判断：**中性**
总分：**-0.060**（中性）
置信度：**2%**
数据健康度：**86%**

## 模块分数

| 模块 | 分数 | 状态 |
|---|---:|---|
| 中国需求 | -0.200 | 🟠 偏空 |
| 库存现货 | +0.600 | 🟢 强多（缺口: 1） |
| 美元利率 | -1.000 | 🔴 强空 |
| 全球制造业 | -0.600 | 🔴 强空 |
| 供应扰动 | +1.000 | 🟢 强多 |
| 价格趋势 | +0.200 | 🟡 偏多 |

## 主要支撑

1. [trend] Price 13707 > MA60 (13607)
2. [trend] Price 13707 > MA120 (13185)
3. [trend] 60d return +10.55%

## 主要压制

1. [trend] Price 13707 <= MA20 (13966)
2. [trend] 20d return -2.23%
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
- [-1] Grid investment YoY -17.1%

### 库存现货

- [+1] Global inventory 20d change -15.07%
- [+1] Global inventory 60d change -28.50%
- [-1] Global inventory at 75% 3y percentile (high)
- [+1] Spot premium +1405.0 (contango/premium)
- [+1] Term structure: backwardation
- ⚠ 数据缺口: comex_inventory missing

### 美元利率

- [-1] DXY 20d change +2.41%
- [-1] DXY 60d change +1.65%
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

- [-1] Price 13707 <= MA20 (13966)
- [+1] Price 13707 > MA60 (13607)
- [+1] Price 13707 > MA120 (13185)
- [-1] 20d return -2.23%
- [+1] 60d return +10.55%

---
*本报告由 copper-forecast MVP 生成，仅供研究参考，不构成投资建议。*
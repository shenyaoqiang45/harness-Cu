# 伦敦铜走势判断报告

生成日期：2026-06-29 17:30
数据截止：2026-06-30

## 结论

1 周判断：**中性**
1 月判断：**中性**
总分：**+0.115**（中性）
置信度：**3%**
数据健康度：**85%**

## 模块分数

| 模块 | 分数 | 状态 |
|---|---:|---|
| 中国需求 | +0.200 | 🟡 偏多 |
| 库存现货 | +0.500 | 🟢 强多 |
| 美元利率 | -1.000 | 🔴 强空 |
| 全球制造业 | +0.200 | 🟡 偏多 |
| 供应扰动 | +1.000 | 🟢 强多 |
| 价格趋势 | +0.200 | 🟡 偏多 |

## A/B 交叉验证

结论：**相互背离**。A/B 两组方向冲突，方向置信度应下调

| 组别 | 模块 | 分数 | 方向 |
|---|---|---:|---|
| 基本面/现货组 | 中国需求、库存现货、供应扰动 | +0.438 | 偏多 |
| 宏观/价格组 | 美元利率、全球制造业、价格趋势 | -0.486 | 偏空 |

## 主要支撑

1. [trend] Price 13633 > MA60 (13606)
2. [trend] Price 13633 > MA120 (13184)
3. [trend] 60d return +9.96%

## 主要压制

1. [trend] Price 13633 <= MA20 (13962)
2. [trend] 20d return -2.76%
3. [macro_liquidity] US 10Y real rate 60d change +9.50%

## 风险提示

1. 宏观数据发布窗口可能引发短期波动
2. 地缘政治与供应扰动未完全量化入模

## 判断失效条件

1. 任一核心模块分数突破 ±0.5 将触发方向调整
2. 库存或宏观流动性出现单边趋势性变化
3. 中国需求数据出现方向性拐点

## 数据异常

1. 无异常数据

## 模块信号明细

### 中国需求

- [-1] China PMI 50.0
- [-1] China PMI mom -0.3
- [+1] New orders PMI 51.8
- [+1] Social financing / M1 improving
- [+1] Grid investment YoY +5.2% (国家能源局)

### 库存现货

- [-1] Global inventory 20d change +0.62%
- [+1] Global inventory 60d change -2.79%
- [+1] Spot premium +1552.4 (contango/premium)
- [+1] Term structure: backwardation

### 美元利率

- [-1] DXY 20d change +2.40%
- [-1] DXY 60d change +1.64%
- [-1] US 10Y real rate 20d change +4.78%
- [-1] US 10Y real rate 60d change +9.50%

### 全球制造业

- [+1] US ISM 54.0
- [-1] US ISM mom +0.0
- [+1] Global PMI 50.3
- [-1] Global PMI mom -2.3
- [+1] Korea exports YoY +53.2% (improving)

### 供应扰动

- [+1] TC/RC spot mom Δ -7.5 USD/ton
- [+1] TC/RC spot at 0% historical percentile (low)
- [+1] confirmed strike at major mine (source: official_news)

### 价格趋势

- [-1] Price 13633 <= MA20 (13962)
- [+1] Price 13633 > MA60 (13606)
- [+1] Price 13633 > MA120 (13184)
- [-1] 20d return -2.76%
- [+1] 60d return +9.96%

---
*本报告由 copper-forecast MVP 生成，仅供研究参考，不构成投资建议。*
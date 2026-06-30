# 伦敦铜走势判断报告

生成日期：2026-06-30 15:51
数据截止：2026-06-30

## 结论

1 周判断：**偏多**
1 月判断：**偏多**
总分：**+0.355**（偏多）
置信度：**15%**
数据健康度：**85%**

## 模块分数

| 模块 | 分数 | 状态 |
|---|---:|---|
| 中国需求 | +1.000 | 🟢 强多 |
| 库存现货 | +0.500 | 🟢 强多 |
| 美元利率 | -1.000 | 🔴 强空 |
| 全球制造业 | +0.200 | 🟡 偏多 |
| 供应扰动 | +1.000 | 🟢 强多 |
| 价格趋势 | +0.200 | 🟡 偏多 |

## A/B 交叉验证

结论：**相互背离**。A/B 两组方向冲突，方向置信度应下调

| 组别 | 模块 | 分数 | 方向 |
|---|---|---:|---|
| 基本面/现货组 | 中国需求、库存现货、供应扰动 | +0.808 | 看多 |
| 宏观/价格组 | 美元利率、全球制造业、价格趋势 | -0.486 | 偏空 |

## 主要支撑

1. [trend] Price 13857 > MA60 (13630)
2. [trend] Price 13857 > MA120 (13188)
3. [trend] 60d return +12.99%

## 主要压制

1. [trend] Price 13857 <= MA20 (13926)
2. [trend] 20d return -3.66%
3. [macro_liquidity] US 10Y real rate 60d change +7.92%

## 风险提示

1. 多空模块严重分裂，方向判断不确定性较高

## 判断失效条件

1. 全球显性库存连续两周大幅累库（>5%）
2. 美元指数突破近期高点且实际利率持续上行
3. 中国 PMI 跌破 50 且新订单分项走弱

## 数据异常

1. 无异常数据

## 模块信号明细

### 中国需求

- [+1] China PMI 50.3
- [+1] China PMI mom +0.3
- [+1] New orders PMI 51.2
- [+1] Social financing / M1 improving
- [+1] Grid investment YoY +5.2% (国家能源局)

### 库存现货

- [-1] Global inventory 20d change +0.62%
- [+1] Global inventory 60d change -2.79%
- [+1] Spot premium +1792.0 (contango/premium)
- [+1] Term structure: backwardation

### 美元利率

- [-1] DXY 20d change +2.08%
- [-1] DXY 60d change +1.23%
- [-1] US 10Y real rate 20d change +5.83%
- [-1] US 10Y real rate 60d change +7.92%

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

- [-1] Price 13857 <= MA20 (13926)
- [+1] Price 13857 > MA60 (13630)
- [+1] Price 13857 > MA120 (13188)
- [-1] 20d return -3.66%
- [+1] 60d return +12.99%

---
*本报告由 copper-forecast MVP 生成，仅供研究参考，不构成投资建议。*
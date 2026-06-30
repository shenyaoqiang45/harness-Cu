# 伦敦铜走势预测系统 (MVP)

研究辅助 / 交易决策参考 / 风险预警系统。判断伦敦铜未来多空力量强弱，不预测精确点位。

## 快速开始

```bash
pip install -e ".[dev]"

# 1) 拉取真实数据 → data/raw/live.csv
python -m copper_forecast.cli fetch

# 2) 生成报告
python -m copper_forecast.cli report -i data/raw/live.csv -o reports/live.md

# 或一步完成（自动同步 metal_inventory_monitor.csv → 报告写入 reports/live.md）
python -m copper_forecast.cli run
```

### 数据源

| 指标 | 来源 |
|------|------|
| LME 铜价（COMEX 代理） | Yahoo `HG=F` |
| DXY | Yahoo `DX-Y.NYB` |
| 美国 10Y 实际利率 | FRED `DFII10`（可用 `FRED_API_KEY`） |
| 中国 PMI / 社融 / M1 | 东方财富 / akshare |
| 电网投资 | 东方财富固定资产投资代理；优先用人工录入的中电联/能源局/国网电网工程投资同比覆盖 |
| 韩国出口同比 | FRED 出口额衍生 |
| 现货升贴水 / 期限结构 | SHFE vs COMEX 衍生 |
| ISM / 全球 PMI / TC/RC 现货 | `data/raw/manual_indicators.csv` 人工维护 |

### 交易所铜库存（库存现货模块）

项目内统一单位为 **公吨**（`ton`）；SHFE 官方「吨」与公吨等价入库。

| 指标 | 交易所 | 数据类型 | 官方来源 | 自动抓取 | 优先覆盖 |
|------|--------|----------|----------|----------|----------|
| `lme_inventory` | 伦敦 LME | 铜库存（公吨） | [LME](https://www.lme.com) | 东方财富 / akshare 日更 | `metal_inventory_monitor.csv` → `import_metal_inventory_monitor.py` |
| `shfe_inventory` | 上海 SHFE | 铜仓单日报（吨） | [SHFE](https://www.shfe.com.cn) | akshare `futures_inventory_em` 日更 | 同上 |
| `comex_inventory` | 纽约 COMEX | 铜库存（官方短吨 → 入库公吨） | [CME Group](https://www.cmegroup.com) | `Copper_Stocks.xls`（易 403） | `metal_inventory_monitor.csv`（`cli run` 自动同步） |

`cli run` / `cli fetch` 在存在 `data/raw/metal_inventory_monitor.csv` 时，会：

1. 自动导入三所库存到 `manual_indicators.csv`
2. 跳过东方财富/akshare/CME 的库存自动抓取
3. 剔除 cutover 日之前的旧库存行
4. 生成报告到 `reports/live.md`

也可单独导入监控表后拉数：

```bash
python scripts/import_metal_inventory_monitor.py --run
```

监控表日期范围内仅以 `金属库存监控` 来源为准；东方财富自动源在部分时段与监控表量级不一致。

复制 `.env.example` 为 `.env` 并填入 `FRED_API_KEY`（可选）。

`tc_rc_spot`：Argus CIF Asia 现货 TC（USD/ton），月频人工录入；供应模块环比用绝对值变化 `Δ = new - old`（下降 = 精矿更紧 = 看多）。`tc_rc` 行可保留年度谈判基准作参考，不参与打分。

电网投资自动源当前为宽口径固定资产投资代理，置信度为 C。拿到真实电网工程投资完成额同比后，可在 `data/raw/manual_indicators.csv` 添加同月 `grid_investment` 记录；月频数据按指标+月份合并，人工记录会覆盖同月代理值。

### A/B 交叉验证

报告会将模块分成两组做交叉验证：

- A 组：基本面/现货组（中国需求、库存现货、供应扰动）
- B 组：宏观/价格组（美元利率、全球制造业、价格趋势）

两组分别按模块权重归一化打分。若 A/B 同向，说明信号相互确认；若背离，说明基本面与宏观/价格信号冲突，方向置信度应谨慎解读。

## 数据格式

CSV 必须包含以下列：

```text
date,indicator,value,unit,source,source_url,updated_at,frequency,confidence
```

核心规则：**无来源不入库、单位不明不入库、异常数据进入待复核**。

## 项目结构

```text
config/          # 指标、权重、校验规则
data/raw/
  live.csv                      # 主数据表（fetch 输出）
  history.csv                   # live 累积备份
  manual_indicators.csv         # 人工/导入覆盖
  metal_inventory_monitor.csv   # 三所库存监控源表
  电网指标监控数据_*.csv          # 电网监控源表
  supply_events.csv             # 供应扰动事件
data/validated/  # 校验后数据（latest.csv）
data/clean/      # confirmed 数据（latest.csv）
data/audit/      # 拉取/校验日志
reports/         # live.md
src/copper_forecast/
tests/
```

## MVP 范围

已实现：CSV 读取、数据校验、六模块打分、总分与置信度、Markdown 报告、异常日志。

未实现：自动抓数、机器学习、Web 前端、自动交易。

详见 [problem-framing.md](problem-framing.md)。

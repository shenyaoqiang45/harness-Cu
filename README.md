# 伦敦铜走势预测系统 (MVP)

研究辅助 / 交易决策参考 / 风险预警系统。判断伦敦铜未来多空力量强弱，不预测精确点位。

## 快速开始

```bash
pip install -e ".[dev]"

# 1) 拉取真实数据 → data/raw/live.csv
python -m copper_forecast.cli fetch

# 2) 生成报告
python -m copper_forecast.cli report -i data/raw/live.csv -o reports/latest.md

# 或一步完成
python -m copper_forecast.cli run
```

### 数据源

| 指标 | 来源 |
|------|------|
| LME 铜价（COMEX 代理） | Yahoo `HG=F` |
| DXY | Yahoo `DX-Y.NYB` |
| 美国 10Y 实际利率 | FRED `DFII10`（可用 `FRED_API_KEY`） |
| LME 库存 | akshare / 东方财富 |
| SHFE 库存 | akshare `futures_inventory_em` |
| 中国 PMI / 社融 / M1 | 东方财富 / akshare |
| 电网投资 | 东方财富固定资产投资代理；优先用人工录入的中电联/能源局/国网电网工程投资同比覆盖 |
| 韩国出口同比 | FRED 出口额衍生 |
| 现货升贴水 / 期限结构 | SHFE vs COMEX 衍生 |
| ISM / 全球 PMI / TC/RC | `data/raw/manual_indicators.csv` 人工维护 |

复制 `.env.example` 为 `.env` 并填入 `FRED_API_KEY`（可选）。

未覆盖：`comex_inventory`（东方财富仅金银库存）、`tc_rc`（需人工录入）。

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
data/raw/        # 原始输入
data/validated/  # 校验后数据
data/clean/      # 模型使用的 confirmed 数据
data/audit/      # 异常日志
reports/         # Markdown 报告
src/copper_forecast/
tests/
```

## MVP 范围

已实现：CSV 读取、数据校验、六模块打分、总分与置信度、Markdown 报告、异常日志。

未实现：自动抓数、机器学习、Web 前端、自动交易。

详见 [problem-framing.md](problem-framing.md)。

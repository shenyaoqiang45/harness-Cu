# 关键事件 Checklist（滚动 30 天）

> 用于按月滚动、事件驱动更新 `reports/runs/live_*.md`。  
> 窗口：**2026-07-02 → 2026-08-02**（含首尾）  
> 上次刷新：**2026-07-02**

---

## 使用说明

1. **事件触发后**：勾选 `[x]`，按「触发动作」更新数据 / `supply_events.csv`，再执行 `python -m copper_forecast.cli run`。
2. **报告落地后 Push**：`cli run` 成功且检查项通过后，**commit 并 `git push origin HEAD`**（见 `.cursor/rules/report-push.mdc`）。
3. **无固定日期的监控项**：放在「持续监控」；有结论时再勾选并记备注日期。
4. **月底滚动**：将窗口整体前移 30 天；已完成项移至文末「归档」；未发生项按新日历重排或删除。
5. **录入纪律**：供应扰动见 `config/supply_event_rules.yaml`；指标覆盖见 `data/raw/manual_indicators.csv`；无可靠来源不录入。
6. **优先级**：先处理 **P0**，再 P1；P2/P3 按常规节奏。供应突变、失效条件相关项一律视为 P0。

### 优先级定义

| 级别 | 标签 | 判定标准 | 响应时限 |
|:---:|---|---|---|
| **P0** | 紧急 | 供应/政策突变；或可能翻转总分方向、触发报告失效条件 | 确认后 **24h 内** 更新数据并 `cli run` |
| **P1** | 高 | 直接进入模块打分的核心指标发布（需求、库存、宏观、PMI） | **发布当日** 录入并 `cli run` |
| **P2** | 中 | 维持数据新鲜度；纪要/衍生指标；例行周频跟踪 | 纳入常规 `cli fetch` / 周检 |
| **P3** | 低 | 背景宏观、交叉验证、流程性复盘 | 按需查阅，不强制当日 run |

---

## 持续监控（窗口内每日 / 每周）

| 状态 | 优先级 | 频率 | 事件 | 影响模块 | 触发动作 |
|:---:|---|---|---|---|---|
| [ ] | P1 | 日 | LME/COMEX 铜价、DXY、美 10Y 实际利率 | 美元利率、价格趋势 | `cli fetch`；异常记入 `data/audit/` |
| [ ] | P1 | 日 | LME / SHFE / COMEX 铜库存 | 库存现货 | 优先 `metal_inventory_monitor.csv` → `import_metal_inventory_monitor.py` |
| [ ] | P2 | 日 | SHFE–COMEX 价差、期限结构 | 库存现货 | `cli fetch`（衍生指标） |
| [ ] | P0↑ | 周 | 智利重大矿山罢工进展 | 供应扰动 | 有官方来源则更新 `supply_events.csv`（`chile_mine_strike`）；**有变化升 P0** |
| [ ] | P1 | 周 | 美国精炼铜 232 总统签署窗口（起算 2026-06-30，约 **90 天至 2026-09-28**） | 供应扰动 | 签署 → confidence **A**；拒签/过期 → score **0** 或删行；**签署/拒签升 P0** |
| [ ] | P1 | 月 | Argus CIF Asia 现货 TC/RC | 供应扰动 | 录入 `manual_indicators.csv` → `tc_rc_spot` |
| [ ] | P1 | 批 | 电网招标 / 变压器招标 / 线缆产量等监控表 | 中国需求 | `import_grid_monitoring.py` 或手工 CSV |

---

## 按时间排序（固定日程）

### 2026-07

| 状态 | 优先级 | 日期 | 事件 | 影响模块 | 触发动作 |
|:---:|---|---|---|---|---|
| [ ] | P1 | **07-03 ~ 07-04** | 全球制造业 PMI（6 月，S&P Global / JPMorgan） | 全球制造业 | 发布后记 `global_manufacturing_pmi`；`cli run` |
| [ ] | P2 | **07-06** | FOMC 会议纪要（6/16–17 会议） | 美元利率 | 阅读纪要要点；利率预期变化时关注 DXY / 实际利率 |
| [ ] | P1 | **07-10 ~ 07-15** | 中国金融数据：社融、M1（6 月，央行） | 中国需求 | 录入 `social_financing`、`m1`；`cli run` |
| [ ] | P3 | **07-15 前后** | 中国 CPI / PPI（6 月，统计局） | —（宏观背景） | 不直接打分；需求走弱时复核 PMI / 新订单 |
| [ ] | P3 | **07-15 前后** | 中国规模以上工业增加值等（6 月） | 中国需求（间接） | 与 PMI、电网投资交叉验证 |
| [ ] | P2 | **07-17 ~ 07-18** | 中国用电量 / 能源数据（6 月，能源局） | 中国需求 | 有同比则录 `power_consumption_yoy` |
| [ ] | P1 | **07-20 ~ 07-25** | 中国电网工程投资完成额（6 月，能源局/中电联） | 中国需求 | 优先人工 `grid_investment` 覆盖代理值 |
| [ ] | P0 | **07-28 ~ 07-29** | **FOMC 议息会议**（7 月场次） | 美元利率、价格趋势 | 决议日关注 DXY、美债、铜价波动；次日 `cli run` |
| [ ] | P0 | **07-31** | 中国官方制造业 PMI（7 月，统计局，月末） | 中国需求 | 录 `china_pmi`、`china_new_orders_pmi`；`cli run`；**PMI 跌破 50 时复核失效条件** |
| [ ] | P3 | **07-31** | 中国财新制造业 PMI（7 月，若发布） | —（交叉验证） | 与官方 PMI 背离时下调需求模块置信度 |

### 2026-08（窗口内）

| 状态 | 优先级 | 日期 | 事件 | 影响模块 | 触发动作 |
|:---:|---|---|---|---|---|
| [ ] | P1 | **08-01** | 美国 ISM 制造业 PMI（7 月） | 全球制造业 | 录 `us_ism_manufacturing`；`cli run` |
| [ ] | P1 | **08-01** | 韩国出口同比（7 月） | 全球制造业 | 录 `korea_exports_yoy`；注意基数切换异常 |
| [ ] | P1 | **08-03 ~ 08-04** | 全球制造业 PMI（7 月） | 全球制造业 | 录 `global_manufacturing_pmi`；`cli run` |
| [ ] | P2 | **08-02** | **窗口截止 · 生成月报对照** | 全模块 | 对比月初 `reports/runs/` 快照；更新下月 checklist |

---

## 供应 / 政策事件（待发生 · 无固定日）

| 状态 | 优先级 | 事件 | 影响模块 | 触发动作 |
|:---:|---|---|---|---|
| [ ] | P0 | 智利罢工解除或扩大 | 供应扰动 | 解除 → `chile_mine_strike` score **0**；扩大 → 升 confidence / score |
| [ ] | P0 | 冶炼厂减产 / 停产（全球） | 供应扰动 | 新行 `smelter_cutback`，confidence **A** 需官方来源 |
| [ ] | P0 | 美国总统签署精炼铜 232 方案 | 供应扰动 | `us_copper_232_refined_tariff` confidence **B→A** |
| [ ] | P0 | 总统 90 天内未签署 232 方案 | 供应扰动 | score **0** 或删行；报告失效条件 #1 触发 |
| [ ] | P1 | 中国废铜 / 进口政策变动 | 供应扰动、库存 | 按 `supply_event_rules.yaml` 新事件类型评估后录入 |

---

## 报告更新检查项（每次 `cli run` 后）

- [ ] `data/audit/anomalies.json` 无新增 **pending** 核心指标
- [ ] `supply_events.csv` 与 checklist 供应项状态一致
- [ ] A/B 组是否同向；若背离，结论是否标注低置信
- [ ] 失效条件（232、累库、美元、中国 PMI）是否仍适用
- [ ] 新报告已写入 `reports/runs/live_YYYY-MM-DD_*.md`
- [ ] **已 commit 并 `git push origin HEAD`**（仅含本次报告链路文件；message 含日期与触发事件）

### Push 快速命令（PowerShell）

```powershell
git add reports/runs/live_<时间戳>.md data/raw/ data/validated/latest.csv data/clean/latest.csv data/audit/
# 若本次有改：git add data/raw/supply_events.csv data/raw/manual_indicators.csv checklist.md
git commit -m "report: live YYYY-MM-DD <事件简述>"
git push origin HEAD
```

---

## 下月滚动模板（复制后改日期）

```text
窗口：YYYY-MM-DD → YYYY-MM-DD
上月归档：reports/runs/live_<月初>_*  vs  live_<月末>_*
待延续：232 签署窗口 / 智利罢工 / 未发布的社融·PMI
```

---

## 归档（已完成 · 2026-07-02 前）

| 优先级 | 日期 | 事件 | 备注 |
|---|---|---|---|
| P0 | 2026-06-30 | 美国商务部提交精炼铜 232 最终报告 | 已录入 `supply_events.csv`，confidence **B** |
| P0 | 2026-06-15 | 智利重大矿山罢工确认 | 已录入 `chile_mine_strike`，confidence **A** |
| P1 | 2026-07-01 | 美国 ISM 制造业 PMI（6 月） | 已反映于最新报告（53.3） |
| P1 | 2026-07-01 | 韩国出口同比（6 月） | 已入模型；exports 异常待复核 |

---

*本清单为研究流程辅助，不构成投资建议。宏观发布日如遇节假日顺延，以官方实际发布时间为准。*

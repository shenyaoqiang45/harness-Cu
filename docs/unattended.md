# 无人值守数据更新

定时工作流只做三件事：抓数、沿用 `validate_rows()` 校验、在确认数据发生变化时生成报告和 dashboard 用的 `data/forecast/latest.json`。它不改权重、不改供应事件、不自动交易，也不补人工指标。

工作流文件：`.github/workflows/unattended.yml`  
入口命令：`python -m copper_forecast.cli run --unattended`

## 还没完成的人工配置

下面两项没有配好之前，**不能**把这条流水线当成已经在云端无人值守运行：

1. 把本分支推到 GitHub 默认分支，让 `schedule` 生效。`workflow_dispatch` 也要等工作流出现在 Actions 页面之后才能手动点。
2. 在仓库 Settings → Secrets and variables → Actions 里按需添加：

| Secret | 是否必须 | 用途 |
|---|---|---|
| `FRED_API_KEY` | 否 | 传给 FRED 抓取。不填时仍会尝试无密钥访问，额度更低 |
| `ALERT_WEBHOOK_URL` | 否 | 失败、连续失败、关键数据缺失或异常激增时 POST JSON。不填则只在 Actions 日志里打印，不会外发 |

不要把密钥写进仓库。`.env` 已在 `.gitignore` 中。

## 调度

- cron：`30 0 * * *`（UTC）
- 运行时区：`TZ=Asia/Shanghai`，对应每天 **08:30**
- 选择这个时间是因为 COMEX 铜上一交易日结算通常已经出来。周六、周日如果没有新的确认 K 线，门禁状态是 `unchanged`，不写新报告、不提交
- 同一天重复跑，确认后的指标日期和数值不变时同样跳过
- 超时 30 分钟。并发组 `copper-unattended`，不取消正在写仓库的那一次

## 状态

每次运行都写 `data/audit/run_status.json`。失败或无变化时不提交。

| status | 退出码 | 是否发布 | 含义 |
|---|---:|---|---|
| `success` | 0 | 是 | 关键日频数据有新的确认值，源组没有失败 |
| `partial` | 0 | 是 | 确认数据有更新，但有非关键源失败，或异常点被挡下 |
| `unchanged` | 0 | 否 | 休市、数据尚未更新，或第二次跑没有新确认值 |
| `failed` | 1 | 否 | 关键序列抓取失败、缺失，或新鲜度超出允许空窗。历史 CSV 保持原字节 |

门禁规则在 `config/unattended.yaml`。关键日频序列是铜价、美元指数、美国 10 年期实际利率。月度序列在 `monthly_lag_days` 窗口内记为尚未发布，不判失败。异常值仍走 `config/validation_rules.yaml`：拒绝入库的行丢掉；会覆盖旧值的异常行保留旧值。

库存监控表会在抓取前按公开序列续写。LME 用 Westmetall，SHFE 用东方财富，COMEX 用 MetalCharts 上的 CME 仓库总量（注册仓单加合格库存，短吨换公吨）。和表内重叠日期量级不一致时，替换该列而不是把两套数接在一天上。COMEX 连续段开始之前的旧单元格清空。抓取失败或没有重叠日期时，该列保持原样。`manual_indicators.csv` 和 `supply_events.csv` 不会被这次提交改掉。监控表本身在确认数据有变化时会一并提交。

## 提交范围

只有 `publish=true` 且文件有差异时才提交并推送。提交内容限于：

- `data/raw/live.csv`、`data/raw/history.csv`、`data/raw/metal_inventory_monitor.csv`
- `data/validated/latest.csv`、`data/clean/latest.csv`
- `data/audit/fetch_log.json`、`anomalies.json`、`run_status.json`
- `data/forecast/latest.json` 和 `data/forecast/history/`
- `reports/runs/` 下新的时间戳报告

权限只有 `contents: write`。

## 通知

`scripts/notify_unattended.py` 在 job 结束时总会执行。

- `run_status.json` 里 `notify=true`：关键抓取失败、关键数据不合格，或新异常达到 `anomaly_surge_min`
- 连续 `failed` 达到 2 次也会再发一次。计数放在 Actions cache `.unattended-state/fail_streak`
- 请求体是 JSON：`text`、`status`、`fail_streak`、`reasons`

## 日志和排查

1. GitHub → Actions → Unattended copper data。手动运行用 Run workflow。
2. 成功或失败都会上传 artifact `run-status`。
3. 发布成功后，报告在 `reports/runs/live_*.md`，dashboard 读 `data/forecast/latest.json`。
4. 常见情况：
   - 作业是红的，历史铜价没变：Yahoo/FRED 失败，门禁拒绝覆盖。看 `fetch_errors`
   - 作业是绿的但没有新提交：`unchanged`，多半是休市或当天已经抓过
   - 报告分数变了、状态是 `partial`：非关键源失败，或异常点被退回旧值
   - 通知没送到：`ALERT_WEBHOOK_URL` 还没配。日志里会有 `ALERT_WEBHOOK_URL is unset`

本地可先做一次不推送的检查：

```bash
python -m copper_forecast.cli run --unattended
```

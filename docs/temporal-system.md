# 时间情报与预测系统

## 定位

这是 Hiro2 内部边界独立的时间情报子系统，不是旧 hiro 仿真器，也不是 rss2cubox 的复制版。它只回答一个问题：

> 技术和产业信号正在如何变化，这些变化是否可能影响岗位能力要求？

旧项目只提供参考经验：RSS 适配、来源优先级、时间边界、信号簇和预测复盘。Hiro2 重新定义数据模型、运行入口和岗位连接方式。

## 数据链路

```text
RSS / 历史日报 / 技术生态
  -> FeedItem
  -> Article Evidence
  -> TrendSignal
  -> SignalCluster
  -> ForecastResult
  -> JobImpactSuggestion
  -> 人工审核
  -> PublishedJobVersion
```

### 来源类型

| 类型 | 作用 | 结论边界 |
| --- | --- | --- |
| 官方发布/研究 | 技术和政策先导信号 | 不能单独证明岗位需求 |
| 开源生态 | 技术采用和工程活动 | 不能直接等同招聘要求 |
| 中文产业资讯 | 国内行业和应用信号 | 需要交叉验证 |
| 招聘 JD | 企业岗位需求验证 | 可参与岗位版本更新 |
| 职业标准/Excel | 能力本体和专家基线 | 不能当作历史时点的真值 |

## 两种运行模式

### 历史回测

```text
选择 as_of_date（数据截止日）
  -> 只加载 available_at <= as_of_date 的数据
  -> 构建当时信号和岗位基线
  -> 预测未来 30/60/90 天
  -> 读取未来窗口后验数据
  -> 比较预测和实际
```

历史补录数据必须标记 `ingestion_mode=backfill`。如果没有当时的抓取日志，只能称为“基于发布时间的历史回放”。

### 未来预测

```text
当前 RSS 增量
  -> 更新信号簇和时间特征
  -> ForecastEngine
  -> 输出有效期内的趋势和岗位影响建议
```

两种模式共用 `ForecastEngine`，区别只有数据截止时间和运行模式。

## 预测规则版本

`ForecastEngine` 的规则由回测驱动迭代，不一次性拍定：

| 版本 | 规则 | 依据 |
| --- | --- | --- |
| v1 动量延续 | 近期/基准加权比 >=1.3 判 up，<=0.7 判 down | 人工先验基线 |
| v2 回测修正 | 过热抑制（ratio>=3.0 判 flat）+ down 阈值收紧到 0.5 | v1 回测 136 条错误结构分析：up 预测 84% 误判于过热追涨（错误条 ratio 最大 16.67 vs 命中条上限 2.94），down 错误 48% 为反弹 |

v2 在三个预测期一致改进（30 天 +5.0 / 60 天 +14.0 / 90 天 +12.8 点），仍逊于平基线如实保留在复盘页。规则阈值必须来自错误分布的结构特征，禁止逐点调参刷分。`backtest.py --rule` 可重放任一版本，产物按规则版本隔离（`backtest-h{H}-r{N}.json`），复盘页提供 v1/v2 对比。

## 核心边界

- 确定性代码计算频次、增长、时间衰减、来源覆盖和评测指标。
- Agent 判断文章语义、证据冲突、技术到岗位的可能映射并生成解释。
- 预测只能生成 `JobImpactSuggestion`，不能直接修改正式岗位版本。
- 建议审核动作持久化到审核事实日志（`POST /temporal/suggestions/{id}/review`，与岗位审核同一份 append-only 记录）；已接受建议在岗位更新流程中人工承接，不自动落版本。
- 日报是先导信号，JD 是市场验证，人工审核决定是否发布。
- 每个预测保存模型、Prompt、规则、数据集版本和 `evidence_ids`。

### 与其他域的连接

```text
时间情报域
  -> `JobImpactSuggestion`
  -> 岗位图谱域审核
  -> `PublishedJobVersion`
  -> 人岗诊断域
```

时间系统没有岗位表、候选人表和 Neo4j 写权限。它不能把趋势预测直接写成岗位必备技能。旧 hiro 和 rss2cubox 只通过 raw 导入适配器提供数据，不共享数据库和运行状态。

## 最小数据对象

```text
FeedSource       订阅源配置
FeedItem         原始 RSS 条目
Evidence         可回链的正文片段
TrendSignal      技术/产业/招聘信号
SignalCluster    长期主题簇
ForecastResult   某时点的预测结果
BacktestRun      历史回测运行
JobImpactSuggestion 岗位影响建议
```

关键时间字段：

```text
published_at  内容发布时间
available_at  系统首次可获取时间
collected_at  本次抓取时间
observed_at   信号观察时间
```

## 精简运行频率

```text
每 3 小时：RSS 抓取、解析、去重
每天：正文增强、信号提取、信号簇更新
每周：生成趋势预测和岗位影响建议
到期后：预测复盘和错误分析
```

首期订阅源控制在 20-40 个高质量来源，不直接导入旧项目的全部源清单。

## CLI

```text
hiro2 temporal ingest
hiro2 temporal extract --item ITEM_ID
hiro2 temporal cluster --window 30d
hiro2 temporal forecast --mode live
hiro2 temporal backtest --as-of 2025-06-30 --horizon 90
hiro2 temporal review --run RUN_ID
hiro2 temporal trace --run RUN_ID
```

CLI 是后端调试和调优入口，前端只负责查看运行结果、证据和复盘。

CLI 与 HTTP API 使用同一应用层用例；每次运行保存 `run_id`、数据集版本、模型/Prompt/规则版本、输入输出和错误分类，保证调优可复现。

## 不做

- 不做 Cubox 或通用阅读器。
- 不做泛新闻舆情平台。
- 不把单篇文章直接变成岗位必备技能。
- 不让预测绕过证据和人工审核。
- 不把旧实验项目的兼容表、旧数据库和页面全部迁入。

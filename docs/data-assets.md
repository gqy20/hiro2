# 数据资产总览

> 本文只回答一个问题：Hiro2 有哪些数据、从哪来、怎么处理、规模多大、质量如何。
> 字段级定义见 [`data-dictionary.md`](data-dictionary.md)；采集与处理进度见
> [`roadmap-data.md`](roadmap-data.md)；来源登记的权威源文件是 `data/SOURCES.yml`。

## 总览

```text
17 个登记来源通道（data/SOURCES.yml）
├── 4 条业务主链数据：能力矩阵（专家基线）、招聘 JD（市场验证）、日报（先导信号）、简历（候选人输入）
├── 4 条对照与扩展数据：政策/大典（官方锚点）、O*NET/ESCO（国际对照）、arXiv/PyPI（技术上游）、RSS（实时源）
└── 3 条学练赛证数据：证书目录（证）、竞赛目录（赛）、职业标准工作要求（学）

核心产物规模（data/processed/，2026-08-31 审计）：
  10,384 条 JD 解析记录（28 平台，AI 域 7,325 条） | 10,379 个日报事件 | 14,174 条证据实体
  17 个已发布岗位版本 | 7,474 条历史信号 | 839 条回测记录
  916 张证书目录 | 1,269 场竞赛目录 | 431 项标准工作要求（含 1,679 能力 + 1,643 知识条目）
  23 个候选人画像 | 22 份匹配报告 | 164 份简历档案
```

## 数据分层与流转

```text
data/raw/          原始快照，只读不覆盖（manifest + 哈希登记）
   │  采集脚本（ingest/rssget/jdcorp/arxivget/certget/raceget...）
   ▼
data/processed/    清洗与标准化产物，可重建
   │  ├─ norm-*.jsonl      标准化层
   │  ├─ curated           质量门后正式数据
   │  └─ <域>/             各域分析产物（evidence/jobversions/temporal/certs/races...）
   ▼
PostgreSQL         事实主库（migration 0001-0009，dbimport/xlzszdb 幂等导入）
   │
   └─ data/runs/<run_id>/  每次运行的 config/events/metrics（714 次运行留痕）
```

质量规则：原始记录不覆盖、清洗结果可从 raw 重建、失败进隔离队列、
LLM 产物必须带 prompt_version/model_version、合成数据永不进评测指标。

## 数据来源明细

### 一、业务主链数据（岗位标准的四路证据）

| 来源 | 通道 | 规模 | 采集方式 | 时间范围 |
| --- | --- | --- | --- | --- |
| Excel 能力矩阵 | 专家基线 | 46 岗位 × 30 能力 × 7 分组 | 团队整理（`ingest.py excel`） | 2026-08 |
| 招聘 JD（平台） | 51job / boss | 搜索 1,150 条 | 浏览器 CDP + mitm 网络层（`jdauto/jdboss`） | 2025-09~2026-08 |
| 招聘 JD（企业官网） | 字节/阿里/腾讯 | 682 条 | 官方 API 直连（`jdcorp`，无 WAF） | 2026-01~08 |
| 招聘 JD（前沿 AI 实验室） | OpenAI/xAI/Moonshot 等 10 家 | 1,626 条 | Ashby/Greenhouse 公开板 API（`ashby.py` + `jdcorp greenhouse`，2026-08-31 新增） | 2026-03~08 |
| 招聘 JD（历史快照） | Wayback 字节/腾讯 | 全部 200 快照 | CDX 枚举（`jdarchive`） | 2022~2025 |
| 日报 | AI 早报公众号 | 697 篇 → 10,379 事件 | Markdown 归档（`ingest.py wechat`，backfill） | 2017-11~2026-08 |
| 简历（学术集） | resume-ner | 240 份文档 | GitHub 直取（对照检验用） | 2018 |

JD 解析最终语料：**10,384 条入库记录**（`jdxtract` 三源合并 + 2026-08-31 新增 10 家前沿
AI 公司 1,626 条：OpenAI 742 / xAI 249 / ElevenLabs 248 / Cohere 146 / LangChain 107 /
Perplexity 93 / Moonshot 19 / LlamaIndex 14 / Runway 4 / StabilityAI 4，28 平台，
AI 域 7,325 条）。前沿实验室源补齐了 AI Safety / Agent Infra / Context Engineering /
Post-Training 等方向的覆盖盲区（此前仅 Anthropic 一家）。

### 二、对照与扩展数据

| 来源 | 通道 | 规模 | 用途 |
| --- | --- | --- | --- | --- |
| 政策文件 | gov.cn 统一检索 | 109 条 | 岗位演化政策锚点 |
| 职业分类大典 | osta.org.cn API | 1,676 职业（2022 版）+ 2015 版对照 | 官方职业编码基线 |
| O*NET 历史 | onetcenter.org | 5 个代表版本（2005-2025） | 美国侧技能演化对照 |
| ESCO | v1.2.1 职业页 | 142MB 结构化 | 国际职业对照 |
| arXiv | export API | 14,830 篇（13 关键词 × 12 年） | 技术先导信号最上游 |
| PyPI/npm | 官方 API + ClickHouse | 209+24 包，127 个月下载史 | 技术萌芽与采用信号 |
| RSS | 24 个直连源 | live 增量 | 实时信号补充 |

### 三、学练赛证数据（2026-08-30 新增，详见 `research/xlzsz-channels.md`）

| 来源 | 通道 | 规模 | 采集方式 |
| --- | --- | --- | --- |
| 人社部国家职业标准 | osta.org.cn 标准库 | **702 条标准**（含 10 份核心标准 PDF 原文） | 公开 JSON API（`certget.py osta/pdf`） |
| 教育部 1+X 证书 | vslc.ncb.edu.cn | **106 张证书 + 74 项等级标准**（数字技术域子集） | 公开 POST API + 关键词遍历（`certget.py onex`） |
| 华为职业认证 | apigw.huawei.com | **108 个认证**（HCIA/HCIP/HCIE，AI 方向 9 个） | 公开 JSON（`certget.py huawei`） |
| 讯飞 AI 开发者大赛 | challenge.xfyun.cn | **629 场赛事**（含往届全届次，算法+应用双轨） | 公开 JSON（`raceget.py xfyun`） |
| 阿里天池 | tianchi.aliyun.com | **270 场赛事** | 公开 JSON（`raceget.py tianchi`） |
| DataFountain | datafountain.cn | **370 场赛事**（tags 即技能标签） | 公开 JSON（`raceget.py datafountain`） |

讯飞 AI 大学堂认证（7 张认证卡）与高教学会竞赛目录（56 项）无 API，
以人工审定映射层形式登记在 `data/CERTS.yml` / `data/CONTESTS.yml`。

## 处理流程（按数据域）

### 1. JD → 岗位版本（招聘主链）

```text
采集（三通道）→ jdclean 修复（标题/公司/日期）
  → jdxtract 解析（prompt jd-skill v2：职责/要求/技能/AI 域判定，LLM）
  → resolve 词典归一（SKILLS.yml v6：3 层体系，JD 命中率 37%）
  → rolemap 岗位映射（规则 83 + LLM 语义 168 = 94% 映射到 46 岗位）
  → jobver 版本组装（必备/加分 + 证据引用 + changeset）
  → 人工审核（review-actions 留痕）
  → jobpub 发布（不可变 PUBLISHED，17 个版本）
```

### 1b. JD → 涌现岗位候选（自动发现）

```text
emergscan 扫描全量 AI 域 JD 标题 n-gram 聚簇
  → 判据：近 90 天 ≥10 条 AND 增长比 ≥1.5（或从无到有）
           AND 标题变体 ≥3 AND 跨平台 ≥2
  → 去噪：地名/职能泛词/已知领域词子串过滤 + Jaccard 重叠合并
  → 产物 emerging-roles.json：候选 + 月度分布（monthly）
           + 近期 JD 原文链接（sampleJds，Greenhouse 精确到单岗）
           + 内容画像（职责/要求/技能/场景聚合）
  → 前端 /new-jobs 审核工作台（趋势图 + JD 链接 + 接受/拒绝）
```

验证样本：FDE（Forward Deployed Engineer）190 条 / 12 平台 / 117 变体 /
增长 16.6 倍，2026-08 检出后随前沿实验室源扩展证据增强。

### 2. 日报 → 信号 → 预测（时间主链）

```text
697 篇 Markdown → extract（prompt v3：8 类事件 + 事实分级）→ 10,379 事件
  → evdedup 去重（24.2% 速览/转载重复，并查集聚类）
  → resolve 技能归一（中高频覆盖率 87.2%，时间闸门可回溯）
  → evidence 证据实体化（14,174 条，含回链与质量分）
  → sigbuild 信号聚合（7,474 条月度信号）
  → backtest 滚动回测（动量规则 v1/v2，839 条记录）
  → forecast 预测（JobImpactSuggestion 进审核队列，不直接改岗位）
```

### 3. 简历 → 诊断 → 学习路径（求职主链）

```text
PDF/DOCX/TXT → parse（PyMuPDF/python-docx 薄适配器）
  → LLM 结构化（prompt resume-parse：技能/项目/证书）
  → 双层归一（词典 37% + 简历专属 LLM 归层 63% = 综合 99%）
  → match 匹配引擎（match-v1：四档判定，证书证据分支经 CERTS.yml 反查）
  → learning_path 学练赛证路径（赛/证段引用真实证书与赛事，零 LLM）
  → 22 份匹配报告 + 8 步路径产物
```

### 4. 学练赛证目录（2026-08-30 新增）

```text
certget 三源目录采集（osta/onex/huawei，公开 JSON）
  → cert-catalog.jsonl 归一（916 条：cert_id/issuer/level/effective_from）
raceget 三源赛事采集（xfyun/tianchi/df）
  → race-catalog.jsonl 归一（1,269 场：organizer/bonus/team_count/tags）
certparse 标准 PDF 结构化（零 LLM：列优先 X 簇间隙分界 + 编号深度切分 + 等级分离）
  → std-requirements/（10 份 → 431 工作内容 / 1,679 能力 / 1,643 知识）
人工审定映射（业务事实，version 管理）
  → CERTS.yml（15 张证书 ↔ 能力域）+ CONTESTS.yml（13 项赛事 ↔ 能力域 + 获奖换算）
  → xlzszdb 入 PostgreSQL（migration 0009 三表）
```

## 质量与可信性机制

| 机制 | 覆盖 | 现状 |
| --- | --- | --- |
| manifest + 哈希登记 | 全部 raw 来源 | 16 通道完整（boss/har 通道后补） |
| 时间闸门（as_of） | 词典/证据/回测 | 回测无规则泄漏已验证 |
| 去重 | 日报事件 | 24.2% 重复已标记，下游只消费主记录 |
| 事实分级 | 日报事件 | fact/report/opinion 加权 1.0/0.6/0.3 |
| 证据回链 | 岗位版本字段 | 17 版本 151/151 技能字段 100% supports 覆盖 + 76 contradicts |
| 审核留痕 | 岗位发布/预标注采纳 | review-actions append-only |
| 合成数据隔离 | 简历/评测 | SYNTHETIC 标记，0 混入冻结样本 |
| LLM 产物版本化 | 全部 prompt 产物 | prompt_version/model_version 随产物落盘 |
| 不可变发布 | 岗位版本 | version_hash 幂等保护 |

## 数据库表（PostgreSQL，migration 0001-0009）

业务主表：`candidates / candidate_profiles / match_reports / job_versions /
growth_tasks / candidate_proofs / candidate_targets / review_actions / outbox_events`

时间与治理表：`pipeline_runs / trend_signals / backtest_records / forecasts /
job_impact_suggestions / dataset_versions / evidence / sources`

域扩展表（0008）：`policies / dadian_careers / arxiv_papers / resume_archive`

学练赛证表（0009）：`cert_catalog（916）/ race_catalog（1,269）/
std_requirements（431）`——已导入本地 PG。

## 已知局限（诚实标注）

- **Ashby 源 JD 原文链接只能到招聘板级**：首采时 jd_id 截断 UUID 前 12 位且未留存
  jobUrl，无法回构单岗页链接；涌现候选的 sampleJds 对 Ashby 源回退到
  `jobs.ashbyhq.com/{company}`（Greenhouse 源可精确到单岗页）。
  采集器已改为留存完整 jobUrl，重采后即恢复单岗链接。
- **2025 基准窗 JD 稀缺**：51job 在招职位随时间下架，基准窗仅 ~24 条（平台物理上限，
  不可回补），主案例 2 两窗口调整为 2026-03~04 / 2026-06~07。
- **boss JD 无发布日期**：仅作标注素材，不进时间分析。
- **讯飞认证与高教学会目录无 API**：映射层为人工整理（调研结论存
  `research/xlzsz-channels.md`），更新依赖人工周期。
- **1+X 证书 API 分页参数实测失效**：服务端忽略 pageNum（任何页返回同一首页），
  无法拉全量 1237 条；采集口径为数字技术域关键词遍历 + 去重聚合（106 张），
  局限与排查过程见 `research/xlzsz-known-limits.md`。
- **certparse 覆盖 10 份标准**：osta 标准库共 702 份，当前只解析了数字技术域核心
  10 份；扩量仅需下载 + 重跑（脚本幂等）。
- **Ashby 源无单岗 URL**：Ashby posting API 的 jobUrl 未在早期采集中留存，
  已修正采集器（`ashby.py` 新增 jobUrl 字段）；存量数据 sampleJds 回退到招聘板页。
- **评测指标待真人抽检**：540 条 AI 预标注采纳需 ~50 条真人复核后方可宣称正式指标
  （roadmap D9）。

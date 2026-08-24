# 数据 Roadmap

> 范围：Excel 能力矩阵、职业标准、招聘 JD、日报 RSS、技能本体、岗位阶梯、证据链、时间快照和评测数据。
> 原则：原始数据不覆盖，处理结果可重建，正式结论必须有证据和审核。
> 当前阶段：D0。状态只使用：未开始、进行中、阻塞、待验收、完成。

## 数据关系

```text
Excel/职业标准      -> 能力本体与专家基线
招聘 JD             -> 市场岗位、等级和需求证据
日报 RSS/历史归档    -> 技术与产业先导信号
候选人简历          -> 人岗匹配输入

以上数据 -> 清洗整理 -> Evidence / SkillSignal / JobSnapshot
```

## 数据分层

目录遵循 `AGENTS.md` 的 `raw / processed / fixtures / runs` 四层；清洗深度用 `data/processed/<source_id>/` 内的文件名前缀表达：

```text
data/raw/                                原始文件和快照，只读
data/processed/<src>/manifest.json       原始件哈希与清单
data/processed/<src>/reports*.jsonl      首层结构化（staged）
data/processed/<src>/norm*.jsonl         标准化结果（normalized）
data/processed/<src>/curated*.jsonl      通过质量门的正式分析数据
data/processed/<src>/feat*.jsonl         日/周/月特征和历史快照
data/runs/                               清洗、回测和评测运行产物
```

## 阶段计划

### D0 数据盘点与清单

| 任务 | 状态 | 退出条件 |
| --- | --- | --- |
| 建立 source registry | 完成 | 每个来源有类型、许可、时间和使用范围（`data/SOURCES.yml`） |
| 导入 Excel 能力矩阵 | 完成 | 46 岗位、30 能力、7 分组可解析（`uv run scripts/ingest.py excel`） |
| 导入 JD CSV/JSONL | 完成 | 搜索层和详情层分开统计（`uv run scripts/ingest.py jd`） |
| 导入日报归档 | 完成 | 生成报告 manifest，标记 `backfill`（`uv run scripts/ingest.py wechat`） |
| 建立数据字典 | 未开始 | 每个字段有类型、含义、来源和质量规则 |

D0 盘点结论（2026-08-24）：

- Excel 矩阵 46 x 30 x 7 全部解析通过，30 能力即 D4 初始能力域。
- JD 搜索层 1190 条（51job 650 / boss 540），仅关键词“AI 工程师”；boss 行全部缺发布时间，51job 有 40 个重复 id；详情层 70 条中正文 >=200 字仅 38 条，18 条标题字段损坏（可用搜索层按 jobId 修复）。**详情可用量距 D5 退出条件（100~200 条）缺口最大，补抓是当前关键路径。**
- 日报归档：索引 707 行，其中 329 行正文从未保存；磁盘实际 697 篇全部保留（378 篇索引内 + 319 篇索引外早期文件，后者元数据降级为文件名日期），时间跨度 2017-11（置顶旧文 1 篇）~ 2026-08。

### D1 结构清洗

处理编码、空值、列名、日期、HTML/Markdown 噪声、损坏文件、非法 URL 和文件哈希。原始记录不覆盖，清洗结果可从 raw 重建，失败记录进入隔离队列。

### D2 身份与重复清洗

处理 URL、GUID、内容哈希、标题/公司/时间相似度、转载和模板 JD。输出 `canonical_record_id`、`duplicate_group_id`、`is_primary` 和 `duplicate_reason`。重复记录保留原文，只标记主记录和关系。

### D3 岗位目录与岗位阶梯

建立：

```text
岗位族 -> 标准岗位 -> 岗位别名 -> 岗位等级
```

等级统一为 `L1 初级 / L2 中级 / L3 高级 / L4 专家或负责人 / UNKNOWN`。判断综合标题、经验、薪资、职责复杂度、架构责任、指导和管理责任；冲突时进入 `REVIEW`。

退出条件：至少 100 条完整 JD 完成岗位和等级人工标注，映射有置信度和证据。

### D4 技能本体与归一化

进行中：
- `data/SKILLS.yml` v4（人工先验：Excel 30 能力 + 技能点 + 别名）与 `data/SKILLS-EARNED.yml`（语料习得别名，带 `effective_from` 首见日期）。
- `backend/skills/resolver.py` 确定性匹配；`resolve --as-of T` 时首见日期晚于 T 的习得别名不参与匹配（防回测规则泄漏：词典不得携带未来知识回翻译过去）。
- `scripts/resolve.py events` 输出逐条映射、分桶覆盖率（中高频 >=2 次为验收口径，目标 >=80%；31 篇样本下中高频已 100%）与带上下文的未命中词单 `unmatched-words.jsonl`；`dates` 子命令重算首见日期。
- 词典迭代以全量语料 top 未命中词为依据；未命中是新词队列，反复出现的新词经人工审核进入词典并递增 version。

每个映射保存 `raw_mention`、`canonical_skill_id`、`skill_point_id`、`mapping_method`、`confidence`、`evidence_ids` 和 `review_status`。

Excel 的 30 个能力维度作为初始能力域，并继续拆出技能点和别名：

```text
RAG/知识库 -> 文档切分 / Embedding / 向量数据库 / Reranking / 检索评测
API开发    -> REST / OpenAPI / 认证 / 权限 / 接口监控
```

每个映射保存 `raw_mention`、`canonical_skill_id`、`skill_point_id`、`mapping_method`、`confidence`、`evidence_ids` 和 `review_status`。

### D5 JD 详情与技能证据

JD 分为：

```text
SearchIndex    用于发现、去重和详情补抓
DetailEvidence 用于职责、要求、技能和岗位版本
```

只有详情完整、来源和发布时间可信的 JD 才能进入正式岗位分析。退出条件：100～200 条完整 JD 具备职责、任职要求、技能片段、岗位/等级映射和人工标注。

### D6 日报事件与趋势信号

进行中：`prompts/report-event.yml` v2 + `backend/temporal` 抽取管线已冒烟通过（.env 网关，单篇约 100s、15 事件/篇），全量 697 篇待跑。

```text
Markdown -> ReportEvent -> Evidence -> TrendSignal -> SignalCluster
```

事件类型至少包括研究、规范发布、模型发布、开源、产品化、采用、政策和传闻。事实、报道和观点分级保存。

退出条件：日报可按日期重建，事件可回到正文和引用链接，历史回填与实时数据分开。

### D7 证据质量与融合

```text
完整性 -> 时间 -> 去重 -> 交叉验证 -> 幻觉/异常拦截
```

来源职责固定为：Excel/标准提供能力基线，日报提供技术先导信号，JD 提供企业需求验证，简历提供候选人输入。每条证据还需标记它支持的字段/变化、支持或反证关系、时间和质量状态。

退出条件：岗位、技能、趋势和匹配结论均能通过 `evidence_id` 回链原文；正式岗位字段和关键匹配结论的证据覆盖率为 100%；来源冲突、单一来源热点和低置信结论进入审核队列，不能静默聚合为岗位事实。

### D8 时间快照与历史回测数据

为每个 `as_of_date` 构建：

```text
JobSnapshot(T)
SkillSnapshot(T)
SignalSnapshot(T)
```

只使用 `available_at <= T` 的数据。预测窗口结束后再构建实际结果，不能用当前 Excel 倒推历史 ground truth。

退出条件：至少一个主题完成多时间点滚动回测，输出预测、实际、差异和错误分类。

### D9 评测集与发布

建立 JD 解析、岗位/等级、技能归一化、历史趋势和人岗匹配评测集。退出条件：输入、标准答案、实际输出、人工判定和指标脚本可复现；合成数据不能进入真实指标。

## 数据状态

```text
RAW -> STAGED -> NORMALIZED -> CURATED -> SNAPSHOT
                                      └-> REVIEW / REJECTED
```

数据状态由数据模块维护，业务模块不能跳过质量门直接读取 RAW。

## 与其他 Roadmap 的依赖

| 数据阶段 | 前端依赖 | 后端依赖 |
| --- | --- | --- |
| D3 岗位目录/阶梯 | 岗位筛选、等级视图 | Job/Level Repository |
| D4 技能归一化 | 技能点图谱 | Skill Resolver |
| D5 JD 证据 | 岗位 Diff、证据抽屉 | Posting/Evidence API |
| D6-D8 趋势回测 | 信号流、回测、复盘 | ForecastEngine |
| D9 评测集 | 评测中心 | Evaluation CLI |

数据 Roadmap 是前后端的上游依赖；没有对应数据退出条件，不得把页面或算法标记为完成。

## 数据完成定义

- [ ] 每个原始文件都有 manifest、哈希、来源和导入模式。
- [ ] 原始、清洗、标准化、正式和实验数据分层保存。
- [ ] 岗位族、标准岗位、别名和等级可解释。
- [ ] 技能映射保留原始提及、规范技能、技能点和证据。
- [ ] JD 和日报都能按时间重建状态。
- [ ] 失败、冲突和低置信记录进入审核队列。
- [ ] 正式岗位字段、岗位变化和关键匹配结论均能回链具体证据片段；证据区分支持与反证。
- [ ] 评测集与调优数据隔离。

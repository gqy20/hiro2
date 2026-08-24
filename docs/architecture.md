# 技术架构

## 结论

完整系统链路见 [`overview.md`](overview.md)。

采用模块化单体：一个 FastAPI 后端、一个 Next.js 前端和一个后台 worker。逻辑模块严格解耦，部署暂不拆微服务。

```text
Next.js
  -> FastAPI API / Application
  -> Domain Modules
  -> PostgreSQL（事实主库）
       ├── Neo4j（图谱投影）
       ├── pgvector（相似检索）
       └── Object Storage（原始文件）
```

## 技术栈

| 层 | 选择 | 用途 |
| --- | --- | --- |
| 前端 | Next.js、TypeScript、Ant Design 6、Ant Design X 2.x、Tailwind、@xyflow/react、Phosphor Icons | 结构化任务流程、AI 交互和图谱 |
| API | Python、FastAPI、Pydantic | 接口、DTO、任务入口 |
| 主库 | PostgreSQL | 事实、版本、审核、评测 |
| 图谱 | Neo4j | 多跳关系和可视化 |
| 向量 | pgvector | 相似 JD、技能候选、证据召回 |
| 文件 | 本地目录/MinIO | PDF、DOCX、原始 JD |
| 解析 | PyMuPDF、python-docx、PaddleOCR（可选） | 文本与页面定位 |
| 测试 | pytest、Ruff、coverage、scikit-learn、Playwright | 质量和评测 |

## 模块边界

```text
sources       来源、采集、原始记录
postings      JD 实体和处理状态
extraction    JD/简历抽取和原文定位
skills        技能本体、别名、技能点
evidence      证据、质量和结论引用
jobs          新岗位、岗位 diff、岗位版本
candidates    候选人画像和用户修正
matching      多维匹配和报告
learning      缺口排序和学习路径
review        审核、发布、回滚
evaluation    测试集、指标和错误案例
graph         Neo4j 投影适配器
temporal      RSS 信号、历史回测和未来预测
```

## 业务域解耦

```text
Temporal Intelligence
  -> Job Capability Graph
  -> Candidate Matching

Frontend / CLI
  -> Application API
```

| 业务域 | 负责 | 对外输出 |
| --- | --- | --- |
| Temporal Intelligence | RSS、日报、信号、回测、预测 | `TrendSignal`、`ForecastResult`、`JobImpactSuggestion` |
| Job Capability Graph | Excel/标准/JD、岗位版本、审核、图谱 | `PublishedJobVersion`、图谱查询 |
| Candidate Matching | 候选画像、匹配和学习路径 | `MatchReport` |
| Frontend / CLI | 页面、调试和任务入口 | API 请求和展示状态 |

Temporal Intelligence 不得直接写岗位表或 Neo4j。Candidate Matching 只接受 `CandidateProfile + PublishedJobVersion`，不读取日报、预测或 Excel 原文件。

依赖方向：

```text
API -> Application -> Domain Interfaces -> Infrastructure Adapters
```

领域模块禁止直接导入数据库 driver、LLM SDK、PDF 库或其他模块的内部表。

前端和 CLI 共同调用 Application Use Case，不能各自实现业务逻辑：

```text
CLI ───────┐
           ├── Application Use Case -> Domain -> Repository
Frontend ──┘
```

## 数据流

```text
SourceRecord
  -> Posting
  -> ExtractionResult
  -> SkillSignal + EvidenceRef
  -> JobChangeSet / EmergingJobCandidate
  -> ReviewAction
  -> PublishedJobVersion
  -> GraphProjection
  -> CandidateProfile
  -> MatchReport
```

## 时间预测层

详细边界、运行模式和 CLI 见 [`temporal-system.md`](temporal-system.md)。

历史回测和未来预测共用一个 `ForecastEngine`，只通过数据截止时间和运行模式区分：

```text
RSS / 历史日报 / JD / 技术生态
  -> FeedItem
  -> SkillSignal
  -> 日/周/月时间特征
  -> ForecastEngine
       ├── Backtest：指定 as_of_date，预测未来并等待后验数据
       └── Forecast：使用当前数据，生成有效期内的预测
  -> EmergingJobCandidate / JobChangeSuggestion
  -> 人工审核
  -> PublishedJobVersion
```

日报是技术和产业先导信号，JD 是企业需求验证，Excel 能力矩阵是专家基线。预测结果只能生成岗位变化建议，不能直接修改正式图谱。

### 时间字段

所有时间信号至少保存：

```text
published_at  内容实际发布时间
available_at   系统首次可获取时间
collected_at   本次抓取时间
observed_at    信号被观察到的时间
```

历史回测只使用 `available_at <= as_of_date` 的数据；后续数据只能用于 ground truth。历史补录数据必须标记 `ingestion_mode=backfill`，不能伪装成当时在线采集。

### 预测模块边界

确定性代码负责热度、增长、时间衰减、跨来源覆盖、版本 diff 和评测指标；LLM/Agent 负责信号语义、证据冲突解释和风险提示。所有输出保留 `model_version`、`prompt_version`、`rule_version` 和证据 ID。

## 存储原则

- PostgreSQL 是唯一事实主库。
- Neo4j、pgvector 和缓存都是可重建投影。
- 原始文件只放对象存储，数据库保存元数据和哈希。
- 岗位版本发布后不可变；修改创建新版本。
- 图谱同步失败不应回滚已发布的业务版本。
- 原始 RSS/日报只在 raw 区和对象存储保存，业务模块读取 `FeedItem`、`ReportEvent` 和 `Evidence`。
- 旧 hiro 和 rss2cubox 不共享数据库、表、运行状态或前端状态，只允许通过导入适配器进入 Hiro2。

### 失败隔离

RSS 单源失败、LLM 解析失败、ForecastEngine 失败、Neo4j 不可用和前端不可用都不能破坏 PostgreSQL 中已发布的岗位版本。失败任务进入重试或人工队列，Neo4j 和向量索引可以重建。

## LLM 边界

LLM 只负责：JD/简历语义抽取、岗位定义草稿、证据范围内的解释。

确定性代码负责：去重、时效权重、交叉统计、版本 diff、匹配分数和评测指标。

所有模型输出必须经过 Pydantic 校验、原文定位和技能标准化；无证据技能进入审核队列，不得直接发布。

## 异步任务

长任务使用 `pipeline_runs` 和 `outbox_events`：

```text
业务事务提交 -> outbox_events -> worker -> Neo4j/向量/评测投影
```

事件必须带 `event_id` 并幂等处理。前端通过 SSE 或轮询读取进度。

## 部署

```text
web / api / worker / postgres / neo4j / minio
```

Docker Compose 必须提供 schema 初始化、案例数据导入、图谱约束创建和 `/health` 检查。Neo4j 不可用时，岗位和匹配仍可由 PostgreSQL 支持。

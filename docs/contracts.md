# 数据与接口契约

## 规则

1. 模块只通过公开 DTO、Repository、命令和事件通信。
2. 业务模块不直接查询其他模块的表。
3. 所有岗位、技能、变更和匹配结论引用 `evidence_id`。
4. LLM 不能直接写正式岗位版本或 Neo4j。
5. 发布版本不可变。
6. Temporal Intelligence 只能提交岗位影响建议，不能直接发布岗位版本。
7. PostgreSQL 是事实主库，Neo4j 和向量索引是可重建投影。

## 可信岗位版本语义

`JobVersion` 是岗位发现、岗位更新、图谱、匹配和培养输出的唯一标准锚点。所有面向用户的岗位结论必须能回答：当前结论、相对基准的变化、证据与审核依据、可执行的下一步。

```text
Evidence + JobChangeSet / JobImpactSuggestion
-> ReviewAction
-> JobVersion(PUBLISHED)
-> Graph / MatchReport / TrainingTask
```

- `Evidence` 证明具体字段或变化，不只证明整份文档存在。
- `ReviewAction` 必须保存接受、修改或拒绝的理由；修改后的字段仍要保留其 `evidence_ids`。
- `JobImpactSuggestion` 始终是候选建议；只有审核后创建的 `JobVersion(PUBLISHED)` 能被图谱、匹配和培养读取。
- `MatchReport` 必须暴露 `job_version_id`、岗位依据和候选人证据，不能只返回总分。

## 核心对象

### Evidence

```text
evidence_id
source_id
source_span
published_at
collected_at
content_hash
claim_type
quality_score
review_status
```

### SkillSignal

```text
posting_id
skill_id
role: required | preferred
weight
evidence_ids[]
valid_at
confidence
```

### JobVersion

```text
job_id
version_id
status: DRAFT | REVIEWING | PUBLISHED | ARCHIVED
title
required_skill_ids[]
preferred_skill_ids[]
valid_from
valid_until
evidence_ids[]
review_action_ids[]
```

### CandidateProfile

```text
candidate_id
raw_extraction_id
effective_skills[]
experience[]
education[]
projects[]
user_corrections[]
```

### MatchReport

```text
match_id
candidate_id
job_version_id
algorithm_version
dimensions[]
overall_score
gaps[]
evidence_ids[]
job_evidence_ids[]
candidate_evidence_ids[]
status
```

### FeedSource

```text
source_id
name
feed_url
publisher
category
reliability
license_status
poll_interval
enabled
```

### FeedItem

```text
item_id
source_id
guid
url
title
summary
published_at
available_at
collected_at
content_hash
ingestion_mode: live | backfill
status
```

### ReportEvent

早报事件抽取输出（`prompts/report-event.yml`，Pydantic 模型 `ReportEventList`）。

```text
event_id
item_id
event_type: research | standard_release | model_release | open_source | productization | adoption | policy | rumor
title
summary
entities[]
fact_grade: fact | report | opinion
urls[]
skill_mentions[]      # 原词，不做归一化；归一化属于 skills 模块
prompt_version
model_version
```

LLM 只产出该结构化候选；解析失败重试后进隔离队列（区分 `validation_failed` 与 `api_error`），不得静默接受自由文本。

### TrendSignal

```text
signal_id
item_id
entity_type: skill | technology | industry | job
canonical_skill_id
signal_type: mention | adoption | job_requirement | release | policy
observed_at
evidence_span
confidence
evidence_ids[]
```

### ForecastResult

```text
forecast_id
skill_id
mode: backtest | forecast
as_of_date
horizon_days
current_phase
predicted_direction
predicted_heat
confidence
forecast_valid_until
model_version
prompt_version
rule_version
evidence_ids[]
```

### BacktestRun

```text
run_id
as_of_date
horizon_days
dataset_version
forecast_ids[]
ground_truth_ids[]
metrics
status
```

### PromptSpec

Prompt 文件使用 YAML，运行时解析为：

```text
id
version
task
system
input_schema
output_schema
limits:
  timeout_seconds
  max_tokens
  max_cost
enabled
```

YAML 可以维护字段描述、枚举提示、必填标记和模型限制，但不单独实现类型系统。`output_schema` 必须指向 Pydantic 模型；Pydantic 是运行时 Schema 的唯一校验来源。

每次运行保存 `prompt_id`、`prompt_version`、`model_version` 和 `schema_version`。Prompt 版本不可被历史运行静默替换。

### Schema 分层

```text
Prompt YAML
  -> 任务说明、字段描述、模型限制
Pydantic Agent Model
  -> 类型、枚举、范围、嵌套结构和输出校验
Domain Model
  -> 证据、技能、版本和状态业务规则
API View Model
  -> 前端可消费的聚合结果
```

禁止为同一个对象分别维护 Prompt JSON、TypedDict、Pydantic 和前端手写四套字段定义。新增或修改字段时，先更新 Pydantic 和 `contracts.md`，再同步 YAML 描述和 OpenAPI 类型。

建议提供一致性命令：

```text
hiro2 prompt check
```

检查 `output_schema` 是否存在、YAML 字段是否属于 Pydantic 模型、枚举值是否一致、Prompt 版本是否有效。

### LogEvent

```text
ts
level: DEBUG | INFO | WARN | ERROR
run_id
parent_run_id
correlation_id
stage
event
component
status: started | progress | succeeded | failed | skipped
item_id
source_id
dataset_version
model_version
prompt_version
duration_ms
count
error_type
error_message
```

原始内容、完整 Prompt 和个人信息不进入日志；通过对象 ID、内容哈希和脱敏摘要关联原文。

### JobImpactSuggestion

```text
suggestion_id
forecast_id
job_id
skill_id
change_type: add | remove | modify | promote | demote
suggested_level
reason
evidence_ids[]
review_status: PENDING | ACCEPTED | MODIFIED | REJECTED
```

`JobImpactSuggestion` 是时间预测域与岗位图谱域之间唯一的业务出口。只有审核命令接受或修改后，才允许创建 `JobVersion`。

### ReviewTask

```text
task_id
task_type: jd_annotation | role_level | skill_mapping | evidence_audit | forecast_review | job_review | match_review | ux_test
source_record_id
run_id
dataset_version
priority
assignee_id
status: PENDING | CLAIMED | IN_REVIEW | SUBMITTED | ADJUDICATING | RESOLVED
system_output
evidence_ids[]
```

### EvaluationAnnotation

```text
annotation_id
task_id
reviewer_id
decision: ACCEPT | MODIFY | REJECT | UNKNOWN
corrected_payload
error_type
rationale
evidence_ids[]
submitted_at
```

同一 `case_id` 的至少 20% 样本必须分配给两位独立审核者；分歧自动创建复核任务，不能静默覆盖。

## 状态机

### JD

```text
RAW -> NORMALIZED -> EXTRACTED -> QUALITY_PASSED -> AVAILABLE
                                      └-> QUALITY_REVIEW / REJECTED
```

### 新岗位候选

```text
DISCOVERED -> GENERATED -> REVIEWING
                         -> ACCEPTED / MODIFIED / REJECTED
                         -> PUBLISHED -> SUPERSEDED
```

### 岗位版本

```text
DRAFT -> REVIEWING -> PUBLISHED -> ARCHIVED
```

### Pipeline Run

```text
PENDING -> RUNNING -> SUCCEEDED
                   -> FAILED -> RETRYING
```

## API

```text
POST /api/v1/postings/import
GET  /api/v1/emerging-jobs
POST /api/v1/emerging-jobs/{id}/generate
POST /api/v1/emerging-jobs/{id}/review
GET  /api/v1/jobs/published
GET  /api/v1/jobs/detected-changes
GET  /api/v1/jobs/{id}/diff?base=v1&target=v2
GET  /api/v1/jobs/{id}/training-output
POST /api/v1/jobs/{id}/versions/{version}/publish
GET  /api/v1/career/home
POST /api/v1/candidates/profiles
POST /api/v1/candidates/resumes
POST /api/v1/matches
GET  /api/v1/matches/{id}
GET  /api/v1/diagnosis/{candidate_id}
GET  /api/v1/pipeline-runs?limit=50&since_days=7
GET  /api/v1/pipeline-runs/{id}
POST /api/v1/temporal/suggestions/{id}/review
GET  /api/v1/temporal/dataset
GET  /api/v1/temporal/timeline
GET  /api/v1/tasks/my
POST /api/v1/tasks/{id}/decision
GET  /api/v1/quality/overview
GET  /api/v1/dashboard/overview
GET  /api/v1/evaluation/overview
GET  /api/v1/datasets/overview
GET  /api/v1/evaluation/runs/{id}/compare
GET  /health/live
GET  /health/ready

质量看板在配置 `DATABASE_URL` 时从 PostgreSQL `review_tasks` 与 `review_actions` 聚合；数据库不可用时回退离线评测产物。
数据资产在配置 `DATABASE_URL` 时从 PostgreSQL `dataset_versions` 读取每个数据域的最新导入快照；离线开发时回退扫描本地处理产物。
`scripts/outbox.py enqueue <version_id>` 写入 `JobVersionPublished`，`scripts/outbox.py consume` 领取并幂等投影到 Neo4j。
```

### JD 导入请求

```json
{
  "source_type": "job_board",
  "source_url": "https://example.com/job/1",
  "title": "AI 应用工程师",
  "company_name": "示例公司",
  "published_at": "2026-08-01T00:00:00Z",
  "raw_text": "...",
  "synthetic": false
}
```

### 匹配请求

```json
{
  "candidate_profile_id": "candidate_01",
  "job_version_id": "job_ai_agent:v2",
  "algorithm_version": "match-v1"
}
```

匹配只接受 `PUBLISHED` 岗位版本。

匹配不接受日报、预测结果或 Excel 文件作为直接输入。

## 领域事件

```text
SourceImported
ExtractionCompleted
SkillResolutionCompleted
EvidenceQualityScored
JobChangeSetGenerated
JobVersionPublished
CandidateProfileUpdated
MatchReportGenerated
FeedItemImported
TrendSignalExtracted
ForecastCompleted
BacktestCompleted
```

事件只传 ID、版本和必要元数据，不传完整简历或大段正文。事件通过 `outbox_events` 持久化，使用 `event_id` 保证幂等。

预测事件只能触发岗位候选或岗位影响建议，正式岗位版本仍需经过审核命令。

## CLI 与 API

CLI 和前端 API 使用同一 Application Use Case。例如 `run_backtest(request)` 同时服务：

```text
hiro2 temporal backtest
POST /api/v1/temporal/backtests
```

前端只消费 API View Model；CLI 负责调试、回测、Trace 和 JSON/Markdown 导出。

CLI、API 和 worker 使用同一 `RunContext` 写入 `data/runs/<run_id>/events.jsonl`，终端文本只是人类摘要，不作为机器审计来源。

## 版本与修正

岗位修改：

```text
published v1 -> draft v2 -> review -> published v2
```

候选人修正：

```text
raw_extraction + user_correction = effective_profile
```

原始抽取永不覆盖，用户修正可审计。

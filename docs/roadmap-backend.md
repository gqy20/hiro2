# 后端 Roadmap

> 范围：数据、领域模块、API、异步任务、LLM 适配、图谱投影、评测和部署。
> 依赖：[`architecture.md`](architecture.md)、[`contracts.md`](contracts.md)、[`roadmap-data.md`](roadmap-data.md)。
> 当前阶段：T1-T3 主体完成（2026-08-25 审计）。状态只使用：未开始、进行中、阻塞、待验收、完成。

## 共享阶段

| 阶段 | 目标 | 后端退出条件 | 实际状态 |
| --- | --- | --- | --- |
| T1 数据与证据 | 建立事实主库和证据链 | D1-D5 数据退出条件满足 | ✅ 9/9（B-T1.7 部分达标） |
| T2 岗位演化 | 完成候选发现、Diff、审核和版本 | 两个主案例可发布岗位版本 | ✅ 8/8（12 个岗位版本已发布，jobver 已参数化） |
| T3 图谱与诊断 | 完成图谱、简历解析和匹配 | 返回稳定的 MatchReport | △ 6/7（B-T3.2 部分：图谱查询为内存构建非 Neo4j） |
| T4 评测与交付 | 完成指标、部署和稳定性 | 评测可重跑，Compose 可启动 | △ 5/12（部署类未做） |

## 任务清单

### B-T1 数据与证据

| ID | 任务 | 依赖 | 状态 | 验收 | 实现 |
| --- | --- | --- | --- | --- | --- |
| B-T1.1 | PostgreSQL schema 和 migration | contracts | **完成** | 核心表、索引、版本约束 | `migrations/0001_init.sql`（12 表，FK+CHECK+部分索引） |
| B-T1.2 | Source / Posting Repository | B-T1.1 | **完成** | 可导入、查询和标记 | `backend/application/repos.py` FileRepository（Phase B 换 Postgres） |
| B-T1.3 | Evidence Repository | B-T1.1 | **完成** | 来源、片段、时间、哈希 | `evidence.jsonl` 6645 条 + PostgreSQL evidence 表 |
| B-T1.4 | PDF/DOCX 文本提取 | - | **完成** | 能输出文本 | PyMuPDF + python-docx 薄适配器（`backend/candidates/parse.py`） |
| B-T1.5 | LLM Provider Adapter | 环境变量 | **完成** | 结构化输出 Pydantic 校验 | AnthropicProvider + MockProvider + PromptSpec YAML |
| B-T1.6 | 技能标准和归一化 | Skill Catalog | **完成** | 别名、技能点、待审核 | SkillResolver v6 + SKILLS-EARNED 755 别名 + 时间闸门 |
| B-T1.7 | 五道质量门 | B-T1.2-6 | **完成** | 完整性、去重、时效、交叉验证、幻觉拦截 | `scripts/quality.py run` 输出统一 JSON 报告并保留 run 产物 |
| B-T1.8 | RSS 来源登记与采集 | B-T1.1/3 | **完成** | 保存 feed、原始 XML、时间 | SOURCES.yml 6 来源 + wechat-mp 697 篇归档 |
| B-T1.9 | 历史日报回填 | B-T1.3 | **完成** | 区分 live/backfill | ingestion_mode=backfill 标记 + 时间戳回填 3459 条 |

### B-T2 岗位演化

| ID | 任务 | 依赖 | 联调 | 状态 | 验收 | 实现 |
| --- | --- | --- | --- | --- | --- | --- |
| B-T2.1 | 新岗位候选评分 | B-T1.7 | I1 | **完成** | 增长、公司数、来源数、置信度 | `newjob.py` 五路证据（涌现/组合/扩散/信号/定义卡） |
| B-T2.2 | 新岗位定义生成 | B-T1.5/6 | I1 | **完成** | 五要素 + 差异理由 + evidence_ids | 定义卡五要素聚合（`emerging-agent.json`） |
| B-T2.3 | 审核命令和审计记录 | B-T1.3 | I1 | **完成** | 接受/修改/拒绝有操作者和理由 | `review-actions.jsonl` append-only + POST API |
| B-T2.4 | 岗位时间窗聚合 | B-T1.7 | I2 | **完成** | 基准和观察窗可复现 | `jddiff.py` 2026-03~04 vs 2026-06~07 |
| B-T2.5 | JobChangeSet Diff | B-T2.4 | I2 | **完成** | 新增/删除/修改带权重和证据 | 13 项变化带证据 JD + evidence_ids |
| B-T2.6 | 岗位版本发布/回滚 | B-T2.3/5 | I2 | **完成** | 发布不可变，新版本可回退 | `jobpub.py` 审核留痕校验 + hash 不可变（12 版本：ai-agent/llm-algo/ai-pm/nlp-mm/cv/mlops/ai-trainer/data-analyst/dc-ops/bigdata/sensor/data-sec） |
| B-T2.7 | 趋势信号与时间特征 | B-T1.8/9 | I1 | **完成** | 日/周/月聚合、时间衰减 | `features.py` 窗口统计 + 事实分级加权 |
| B-T2.8 | ForecastEngine | B-T2.7 | I2 | **完成** | 规则基线和 Agent 解释 | `forecast.py` v1 动量规则 + 回测负结果驱动 v2（过热抑制 + down 保守化，三 horizon 一致改进 +5~14 点） |

### B-T3 图谱与诊断

| ID | 任务 | 依赖 | 联调 | 状态 | 验收 | 实现 |
| --- | --- | --- | --- | --- | --- | --- |
| B-T3.1 | Neo4j Graph Projector | B-T2.6 | I3 | **完成** | JobVersionPublished 可幂等投影 | `backend/infra/neo4j.py` 参数化 Cypher + 约束 + `scripts/graph.py` 重建 |
| B-T3.2 | 图谱查询 API | B-T3.1 | I3 | **部分** | 技术栈、级别、技能点可筛选 | `GET /skills/graph` 内存构建 22 节点 21 边（非 Neo4j） |
| B-T3.3 | CandidateProfile 服务 | B-T1.4/6 | I4 | **完成** | 原始抽取、用户修正、生效画像 | `backend/candidates/` raw+correction→effective，双层归一 99% |
| B-T3.4 | 多维匹配算法 | B-T2.6/T3.3 | I4 | **完成** | 技能、熟练度、年限可解释 | `backend/matching/engine.py` match-v1 四档判定 |
| B-T3.5 | MatchReport API | B-T3.4 | I4 | **完成** | 差距、证据、置信度、算法版本 | `GET /diagnosis/{id}` 21 候选人 × overall 0.2~0.94 |
| B-T3.6 | 学习路径生成 | B-T3.4 | I4 | **完成** | 按必备性、权重和前置依赖排序 | `learning_path()` P0>P1>P2 学练赛证模板 |
| B-T3.7 | 岗位标准培养任务输出 | B-T2.6 | I4 | **完成** | JD 模板、训练任务、证明标准 | `backend/application/training.py` + `GET /jobs/{id}/training-output`，前端发布成功视图已接入 |

### B-T4 评测与交付

| ID | 任务 | 依赖 | 状态 | 验收 | 实现 |
| --- | --- | --- | --- | --- | --- |
| B-T4.1 | Evaluation Case schema | B-T1.1 | **完成** | 输入、标准答案、预测、判定 | `evalset.py freeze` 三层冻结样本 |
| B-T4.2 | 指标计算 CLI | B-T4.1 | **完成** | 指标可重跑 | `evalset.py score` 确定性计算 |
| B-T4.3 | 100+ JD 测试集导入 | B-T4.1 | **完成** | 真实、来源、标注、synthetic 标记 | 337 条（266 AI 域），全部真实采集 |
| B-T4.4 | 单元、契约、集成测试 | 全部 | **完成** | coverage>=60% | 38 个测试全绿，coverage 65.12%，Makefile 强制 fail-under=60 |
| B-T4.5 | Pipeline Run / Outbox | B-T2 | **完成（2026-08-29）** | 长任务可追踪，事件幂等 | 消费逻辑归位 `backend/application/outbox.consume_batch`（失败带退避回 PENDING、达上限转 FAILED，FOR UPDATE SKIP LOCKED 并发安全）；常驻 worker `outbox_worker.py`（API lifespan 挂载，HIRO2_OUTBOX_WORKER 开关默认关、compose 默认开、30s 轮询）；CLI 壳化；域单测 3 例 |
| B-T4.6 | Docker Compose 和健康检查 | 全部 | **完成** | 干净环境可启动 | `docker-compose.yml` 含 PostgreSQL/Neo4j/API/Web 健康依赖和 migration 初始化；`/health/live` + `/health/ready` |
| B-T4.7 | 历史滚动回测 CLI | B-T2.8 | **完成** | 只用截止时间前数据 | `backtest.py` 月度滚动 + 双 as_of 闸门 |
| B-T4.8 | 预测复盘与错误分析 | B-T4.7 | **完成** | 命中等级和改进建议 | error_types 分类（up->down 为主） |
| B-T4.9 | ReviewTask 与任务分配 | B-T4.1 | **完成** | 自动生成、领取、提交 | 180 条任务从 evalset 自动生成 |
| B-T4.10 | 审核标注与双人复核 | B-T4.9 | **未开始** | 20% 双人独立审核 | 无双审机制 |
| B-T4.11 | 质量指标与运行对比 API | B-T4.2/10 | **完成** | 完成率、复核率、错误分布 | `/api/v1/quality/overview` 从评测 CSV 与 append-only 审核动作计算，前端移除 mock 指标 |
| B-T4.12 | CI 与迁移验证 | Makefile | **完成（2026-08-29）** | CI 使用锁文件 | 私有仓库 gqy20/hiro2 已建并全量推送；CI 全链绿（uv frozen sync + pnpm frozen + make verify + Playwright e2e + pre-commit，约 4 分钟）；首跑暴露的三层格式债已清（11 py 文件 ruff、10 web 文件 prettier、184 文件钩子修复，test-results 入 prettier ignore） |

## 联调门

| 门 | 前端状态 | 后端提供 | 通过条件 | 实际 |
| --- | --- | --- | --- | --- |
| I1 新岗位 | ✓ 接真实数据 | Emerging Job API + Review POST | DTO/状态/证据一致 | ✅ `/new-jobs` 真实五路证据 |
| I2 岗位 Diff | ✓ 接真实数据 | Job Diff / Publish / Version API | 版本不可变，三类变化可回链 | ✅ `/jobs` 13 项变化 + ai-agent-v2 已发布 |
| I3 图谱证据 | ✓ 接真实数据 | Graph / Evidence API | 节点和证据可关联 | ✅ `/skills` 22 节点 + `/evidence/{id}` 回链 |
| I4 人岗诊断 | ✓ 接真实数据 | Resume / Match API | 修正后返回新报告 | ✅ `/diagnosis` 21 候选人 + 学习路径 |

## 后端完成定义

- [x] API DTO 与 contracts.md 一致，通过 Pydantic 校验。
- [x] LLM 不直接写正式岗位版本或 Neo4j。
- [x] 所有正式结论都有 evidence_ids。
- [x] PostgreSQL 是事实主库（12 表 6645 证据）。
- [x] 发布版本不可变（hash + 幂等保护），审核动作可审计（append-only）。
- [x] 评测脚本不依赖前端，指标可在命令行重跑（evalset score）。
- [x] 历史回测和未来预测共用 ForecastEngine（仅模式和数据截止时间不同）。
- [x] 预测只能生成岗位变化建议（JobImpactSuggestion），不能绕过审核发布。
- [ ] Docker Compose、迁移、种子和健康检查可用。
- [x] 时间情报系统不依赖旧 hiro 或 rss2cubox，可独立运行。
- [x] 审核和评测反馈以 ReviewTask 保存（180 条），不依赖线下数据包。
- [x] 任何正式岗位或匹配结论都可输出"结论、变化、依据、行动"所需的稳定 View Model。

## 剩余工作（按优先级）

1. **人工标注抽检覆盖**（标注管道已修通：预标注 -> `/tasks` 确认 -> `evalset.py score`；基线已产出：固定样本 74%→95%，冻结样本 v3 78%/96%/100%；待人工抽检确认独立性与 >90% 宣称）
2. **Docker Compose + CI**（部署分拿分项）
3. **Neo4j 图谱查询接线**（B-T3.2：投影已完成，`/skills/graph` 仍为内存构建）
4. **五道质量门统一报告**（B-T1.7，各环节有实现但未整合）
5. **Outbox 事件驱动**（B-T4.5，architecture 提到但无产品阻塞）
6. **双人 20% 复核**（B-T4.10，contracts 要求但可后补）

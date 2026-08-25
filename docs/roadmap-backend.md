# 后端 Roadmap

> 范围：数据、领域模块、API、异步任务、LLM 适配、图谱投影、评测和部署。
> 依赖：[`architecture.md`](architecture.md)、[`contracts.md`](contracts.md)、[`roadmap-data.md`](roadmap-data.md)。
> 当前阶段：T1-T3 主体完成（2026-08-25 审计）。状态只使用：未开始、进行中、阻塞、待验收、完成。

## 共享阶段

| 阶段 | 目标 | 后端退出条件 | 实际状态 |
| --- | --- | --- | --- |
| T1 数据与证据 | 建立事实主库和证据链 | D1-D5 数据退出条件满足 | ✅ 9/9（B-T1.7 部分达标） |
| T2 岗位演化 | 完成候选发现、Diff、审核和版本 | 两个主案例可发布岗位版本 | ✅ 8/8（ai-agent-v2 已发布） |
| T3 图谱与诊断 | 完成图谱、简历解析和匹配 | 返回稳定的 MatchReport | △ 5/7（B-T3.1/3.7 未做） |
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
| B-T1.7 | 五道质量门 | B-T1.2-6 | **部分** | 完整性、去重、时效、交叉验证、幻觉拦截 | 去重(evdedup)、时效(as_of 闸门)、交叉验证(leadtime)各有实现，但未整合为统一五道门报告 |
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
| B-T2.6 | 岗位版本发布/回滚 | B-T2.3/5 | I2 | **完成** | 发布不可变，新版本可回退 | `jobpub.py` 审核留痕校验 + hash 不可变（ai-agent-v2） |
| B-T2.7 | 趋势信号与时间特征 | B-T1.8/9 | I1 | **完成** | 日/周/月聚合、时间衰减 | `features.py` 窗口统计 + 事实分级加权 |
| B-T2.8 | ForecastEngine | B-T2.7 | I2 | **完成** | 规则基线和 Agent 解释 | `forecast.py` v1 动量规则 + 回测（诚实负结果：低于基线） |

### B-T3 图谱与诊断

| ID | 任务 | 依赖 | 联调 | 状态 | 验收 | 实现 |
| --- | --- | --- | --- | --- | --- | --- |
| B-T3.1 | Neo4j Graph Projector | B-T2.6 | I3 | **未开始** | JobVersionPublished 可幂等投影 | 架构定位为可重建投影，非关键路径 |
| B-T3.2 | 图谱查询 API | B-T3.1 | I3 | **部分** | 技术栈、级别、技能点可筛选 | `GET /skills/graph` 内存构建 22 节点 21 边（非 Neo4j） |
| B-T3.3 | CandidateProfile 服务 | B-T1.4/6 | I4 | **完成** | 原始抽取、用户修正、生效画像 | `backend/candidates/` raw+correction→effective，双层归一 99% |
| B-T3.4 | 多维匹配算法 | B-T2.6/T3.3 | I4 | **完成** | 技能、熟练度、年限可解释 | `backend/matching/engine.py` match-v1 四档判定 |
| B-T3.5 | MatchReport API | B-T3.4 | I4 | **完成** | 差距、证据、置信度、算法版本 | `GET /diagnosis/{id}` 21 候选人 × overall 0.2~0.94 |
| B-T3.6 | 学习路径生成 | B-T3.4 | I4 | **完成** | 按必备性、权重和前置依赖排序 | `learning_path()` P0>P1>P2 学练赛证模板 |
| B-T3.7 | 岗位标准培养任务输出 | B-T2.6 | I4 | **未开始** | JD 模板、训练任务、证明标准 | 产品功能有设计无实现 |

### B-T4 评测与交付

| ID | 任务 | 依赖 | 状态 | 验收 | 实现 |
| --- | --- | --- | --- | --- | --- |
| B-T4.1 | Evaluation Case schema | B-T1.1 | **完成** | 输入、标准答案、预测、判定 | `evalset.py freeze` 三层冻结样本 |
| B-T4.2 | 指标计算 CLI | B-T4.1 | **完成** | 指标可重跑 | `evalset.py score` 确定性计算 |
| B-T4.3 | 100+ JD 测试集导入 | B-T4.1 | **完成** | 真实、来源、标注、synthetic 标记 | 337 条（266 AI 域），全部真实采集 |
| B-T4.4 | 单元、契约、集成测试 | 全部 | **部分** | coverage>=60% | 34 个测试全绿；覆盖率未测 |
| B-T4.5 | Pipeline Run / Outbox | B-T2 | **未开始** | 长任务可追踪，事件幂等 | RunContext 有 JSONL 日志，无 outbox_events 表 |
| B-T4.6 | Docker Compose 和健康检查 | 全部 | **未开始** | 干净环境可启动 | `/health` 端点有；Compose 未做 |
| B-T4.7 | 历史滚动回测 CLI | B-T2.8 | **完成** | 只用截止时间前数据 | `backtest.py` 月度滚动 + 双 as_of 闸门 |
| B-T4.8 | 预测复盘与错误分析 | B-T4.7 | **完成** | 命中等级和改进建议 | error_types 分类（up->down 为主） |
| B-T4.9 | ReviewTask 与任务分配 | B-T4.1 | **完成** | 自动生成、领取、提交 | 180 条任务从 evalset 自动生成 |
| B-T4.10 | 审核标注与双人复核 | B-T4.9 | **未开始** | 20% 双人独立审核 | 无双审机制 |
| B-T4.11 | 质量指标与运行对比 API | B-T4.2/10 | **部分** | 完成率、复核率、错误分布 | 页面有但指标数据来自 mock |
| B-T4.12 | CI 与迁移验证 | Makefile | **未开始** | CI 使用锁文件 | 无 GitHub Actions |

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

1. **人工标注回流**（0/100，阻塞 D3/D5/D9 退出条件——人的任务）
2. **F-T3.4 PDF/DOCX 解析确认** + **F-T3.6 岗位标准培养任务**（后端 API 已有，前端页面待接）
3. **Docker Compose + CI**（部署分拿分项）
4. **Neo4j 图谱投影**（B-T3.1，可重建投影非关键路径）
5. **五道质量门统一报告**（B-T1.7，各环节有实现但未整合）
6. **Outbox 事件驱动**（B-T4.5，architecture 提到但无产品阻塞）
7. **双人 20% 复核**（B-T4.10，contracts 要求但可后补）
8. **B-T3.7 培养任务/JD 模板输出**（产品功能有设计无实现）

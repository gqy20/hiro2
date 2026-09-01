# 协作者导览

> 这份文档只回答一个问题：新加入的协作者如何理解 Hiro2 的整体逻辑，并找到自己参与完善的位置。
> 阅读时间约 10 分钟；读完后再按角色进入对应的深入文档。

## 一句话定位

Hiro2 把多源数据变成**可信岗位版本**，再驱动人岗诊断和学习路径——每个岗位结论都有版本、证据和审核记录，预测永远不直接当事实。

整体逻辑是一条主线：

```text
多源数据（Excel 基线 / 招聘需求（JD） / 日报 RSS / 简历）
  -> 证据层（原文片段、质量、时间）
  -> AI 结构化候选（只出建议，不出事实）
  -> 人工审核（接受 / 修改 / 拒绝）
  -> 已发布岗位版本（不可变，PostgreSQL 事实主库）
  -> 图谱 / 招聘模板 / 人岗诊断 / 学练赛证学习路径
```

用一个例子贯穿理解：“AI 应用工程师”岗位怎么更新——系统对比两个时间窗的招聘需求（JD），发现新增、删除、修改的能力项（每条带证据和置信度），招聘负责人审核后发布新版本，求职者再用这个版本做诊断。一个例子讲完，整个系统就串起来了。

## 三条不可违反的边界

参与任何环节前，先记住这三条。代码评审和提交都会按它们检查：

1. **AI 与事实的边界**：大模型只产出结构化候选（如“岗位影响建议”），必须经人工审核才能变成岗位版本。自由文本不能当业务事实，模型输出必须过 Pydantic 校验。
2. **数据消费的边界**：人岗匹配只接受“候选人画像 + 已发布岗位版本”，不读日报、预测或 Excel 原文件；预测建议通过审核流接力到岗位更新，不直接改图谱。
3. **存储的边界**：PostgreSQL 是唯一事实主库；Neo4j、pgvector 都是可重建投影，挂了不影响已发布版本。岗位版本发布后不可变，修改创建新版本。

## 系统怎么运转

三个业务域单向解耦，前端和命令行工具共用同一套应用层用例：

```text
时间情报域（RSS、回测、预测）
  -> 岗位图谱域（版本、审核、图谱）
  -> 人岗诊断域（画像、匹配、学习路径）
```

代码位置的对应关系：

| 目录 | 职责 |
| --- | --- |
| `backend/` | 领域模块（jobs、skills、evidence、matching、temporal 等） |
| `backend/application/` | 应用层用例，前端和命令行工具的共同入口 |
| `apps/api/` | FastAPI 入口，返回稳定的展示模型（不暴露库表结构） |
| `apps/web/` | Next.js 前端，三个工作区（招聘 / 求职 / 数据） |
| `scripts/` | 命令行短脚本（ingest、jddiff、backtest、evalset 等） |
| `prompts/` | YAML 管理的 Prompt，带版本和 Schema |
| `data/` | raw（只读）/ processed（可重建）/ runs（运行产物） |
| `evaluation/` | 冻结评测样本与标注回流 |

技术栈与模块边界的完整说明见 [`architecture.md`](architecture.md)；完整数据链路图见 [`overview.md`](overview.md)。

## 当前状态

体系闭环已通，主要缺口集中在**人工环节和收尾**（2026-08-29 核对）：

| 已达成 | 证据 |
| --- | --- |
| 数据全链路 D0-D9 | 五道质量门、10,384 条真实 JD 解析库、180 条冻结评测集、14,174 条证据、三项准确率 88/98/100 达标 |
| 岗位版本发布 | 17 个岗位版本（12 个岗位，发布不可变、审核留痕） |
| 人岗诊断 | 21 候选人的匹配报告 + 学练赛证学习路径 |
| 覆盖率 78%（143 单测 + e2e 30 全绿） | Makefile 强制下限 60% |
| 持续集成全链绿 | 依赖锁文件安装 + 完整校验 + 端到端测试，约 4 分钟 |

| 缺口 | 阻塞什么 |
| --- | --- |
| 人工抽检标注（当前 540 条判定均为 AI 预标注批量采纳） | 三项准确率无法宣称正式指标 |
| 岗位+等级双确认 0/266（`review-labels.csv`） | D3/D5/D9 退出条件 |
| 双人复核机制未实现（B-T4.10） | 评测可信度 |
| 岗位映射准确率现状 78%（评测集 eval-v3，低于 90% 线） | 岗位映射准确率指标 |
| Neo4j 投影（图谱查询现为内存构建） | B-T3.2 完全达标 |

## 需要协助的事项

按紧迫度排序，前两项**只需业务判断、不用写代码**，是最适合新协作者的入口：

### 1. 评测标注人工抽检（最紧迫）

把 AI 预标注基线升级为可宣称的正式指标。建议量：28 条非“接受”判定全部复核 + “接受”判定抽 10%（约 22 条），共约 50 条。

入口：启动系统后打开 `/tasks` 页，查看原文、系统结果、证据和置信度，提交接受、修改、拒绝或无法判断。完成后由 `evalset.py score` 重跑指标。

### 2. 岗位+等级双确认标注

`data/processed/jd-opencli/review-labels.csv` 共 266 行，人工确认列 0/266 填写，需标注 >=100 条满足 D3 退出条件。判定"这条 JD 属于哪个岗位、什么等级"，与评测任务互补不互抵。

### 3. 岗位映射规则 v4 修复

需要 Python 能力。已知三类失分点：商务/管理信号补“Engineering Manager/Manager of”（8 条空间）、“产品经理”别名优先于“大模型”（3 条）、排除规则误伤修正（3 条）。改 `scripts/rolemap.py`，用 `scripts/evalcmp.py` 做固定样本对比（锚定 `jd_id`，不锚定方法分层）。

### 4. 双人复核机制（B-T4.10）

需要后端能力。场景 E 要求 >=20% 样本双人独立审核；当前无双审机制。涉及审核任务的分配与一致性统计。

### 5. Neo4j 投影收尾（B-T3.2）

需要后端能力。图谱查询现为内存构建；Outbox worker 已具备岗位发布 -> Neo4j 投影的自动通道，需把查询切到真实 Neo4j。

## 按角色的深入阅读

| 你想做什么 | 先读 |
| --- | --- |
| 理解产品定位和验收标准 | [`product.md`](product.md)、[`user-scenarios.md`](user-scenarios.md) |
| 做数据标注或评测 | [`evaluation.md`](evaluation.md)、[`roadmap-data.md`](roadmap-data.md) |
| 写后端或 CLI | [`architecture.md`](architecture.md)、[`contracts.md`](contracts.md)、[`roadmap-backend.md`](roadmap-backend.md) |
| 写前端 | [`design.md`](design.md)、[`design-recruiting.md`](design-recruiting.md)、[`design-career.md`](design-career.md)、[`roadmap-frontend.md`](roadmap-frontend.md) |
| 理解时间预测和回测 | [`temporal-system.md`](temporal-system.md) |
| 理解为什么这样设计 | [`adr/README.md`](adr/README.md) |
| 理解比赛对标和亮点 | [`competition.md`](competition.md) |

## 上手步骤

```bash
git clone <仓库地址>
cd hiro2
make init          # uv sync + pnpm install + git hooks
make check         # 提交前必须通过
make verify        # 完整本地校验
```

本地启动（PostgreSQL / Neo4j / API / Web）：

```bash
docker compose up -d
```

日常命令统一 `uv run`（Python）和 `pnpm --dir apps/web`（Web）。提交信息遵循约定式提交：`type(scope): 摘要`，例如 `feat(temporal): 增加日报导入`。完整协作规范见根目录 [`AGENTS.md`](../AGENTS.md)。

## 协作时的质量底线

- 所有结论可复现：指标来自 `evalset.py score` 等确定性脚本，不在前端手填。
- 业务事实必须有版本、来源和审核状态；评测结果只能追加，不能覆盖。
- 每次运行生成 `run_id`，产物在 `data/runs/<run_id>/`。
- 原始数据只读；合成数据必须标记，不进真实指标。
- 提交前 `make check`；对用户可见的变更同步更新根目录 `CHANGELOG.md`。

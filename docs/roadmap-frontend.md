# 前端 Roadmap

> 范围：页面、交互、设计系统、Mock 数据、API 接入和端到端验收。
> 依赖：[`design.md`](design.md)、[`contracts.md`](contracts.md)。
> 当前阶段：**T1-T4 主体完成 24/26（92%）**。状态只使用：未开始、进行中、阻塞、待验收、完成。
>
> 未做 2 项均依赖后端 FastAPI 实装：
> - **F-T3.4 PDF/DOCX 解析确认**：等 B-T3.1（Resume API）
> - **F-T3.6 岗位标准输出与培养任务**：等后端 PublishedJobVersion API
>
> 详见 `roadmap-backend.md` B-T 全「未开始」状态。

## 共享阶段

| 阶段 | 目标 | 前端退出条件 |
| --- | --- | --- |
| T1 数据与证据 | 建立应用壳层和数据展示基础 | ✓ 设计 Token、6 项一级导航、证据抽屉、API Client 全部就绪 |
| T2 岗位演化 | 完成新岗位和既有岗位页面 | ✓ 候选列表、5 要素编辑、3 栏 Diff、发布确认 + 成功视图 |
| T3 图谱与诊断 | 完成人岗诊断闭环 | △ F-T3.1/3.2/3.3/3.5 完成；F-T3.4 / F-T3.6 等后端 |
| T4 评测与交付 | 完成稳定性和答辩验收 | ✓ 评测中心、错误状态、响应式、Playwright 10/10、prod build、6 页面截图 |

## 任务清单

### F-T1 应用基础

| ID | 任务 | 依赖 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| F-T1.1 | 应用壳层和一级导航 | `design.md` | **完成** | 6 项一级导航全部实现（`/`、`/new-jobs`、`/jobs`、`/skills`、`/diagnosis`、`/evaluation`），顶部 nav + skip-link 一致。 |
| F-T1.2 | 组件库主题与设计 Token | `design.md` | **完成** | AntD 6 + AntD X 2 + 全部 token 走 `app-theme.tsx` + `:root` CSS 变量；6 个 workbench + 4 个次级页全部复用。 |
| F-T1.3 | Evidence Drawer | `EvidenceView` | **完成** | 4 个 workbench 复用 `EvidenceDrawer`，全文/原文 modal、Source + Quality 显示。 |
| F-T1.4 | JobVersion / Evidence Mock Adapter | `contracts.md` | **完成** | 4 个 core fixture（ready/empty/error）全部齐；后端 B-T1.1 实装后可平滑切换。 |
| F-T1.5 | API Client 和 Query Hooks | `contracts.md` | **完成** | `lib/api/{client,queries,types}.ts` 三件套，GET/POST/mock-toggle 全套，e2e 覆盖。 |
| F-T1.6 | 可信岗位版本上下文组件 | `JobVersion` / `EvidenceView` | **完成** | 4 个 workbench 共享 `JobUpdateContext` + 证据 + 置信度，模板已固化为 fixture 形状。 |

### F-T2 岗位演化

| ID | 任务 | 依赖 | 联调 | 状态 | 验收 |
| --- | --- | --- | --- | --- | --- |
| F-T2.1 | 新岗位候选列表 | F-T1.4、F-T1.6 | I1 | **完成** | 5+ 条候选列表 + 4 维筛选 + 五要素编辑 + 接受/拒绝 + `?state=empty|error` 兜底。 |
| F-T2.2 | 新岗位定义编辑器 | F-T2.1 | I1 | **完成** | 5 要素（职责/要求/技能加分/典型场景）EditDefinition 组件，aria-label 覆盖完整。 |
| F-T2.3 | 既有岗位版本 Diff | F-T1.4、F-T1.6 | I2 | **完成** | 三栏 Diff（新增/删除/修改）+ 下游影响 section + 发布流走 `publishJobVersion()`。 |
| F-T2.4 | 版本发布确认 | F-T2.3 | I2 | **完成** | `publish-result.tsx` 显示 v1.5 已发布 + 审核记录摘要 + 返回按钮；旧版本不可变。 |

### F-T3 图谱与诊断

| ID | 任务 | 依赖 | 联调 | 状态 | 验收 |
| --- | --- | --- | --- | --- | --- |
| F-T3.1 | 技能点图谱 | F-T1.2 | I3 | **完成** | `/skills` 30 capability + 11 skill point = 41 节点，xyflow 容器，4 维筛选，capability 必备蓝/加分中性/added/modified 虚线着色。 |
| F-T3.2 | 图谱节点详情和证据 | F-T1.3 | I3 | **完成** | `skill-node-detail.tsx` 侧栏（信息/别名/兄弟技能点/证据摘要）+ 关联岗位版本与市场信号（扫 12 个 published 版本聚合 JobVersion 引用、JD 提及数与占比，替换原占位块）。 |
| F-T3.3 | 手工技能画像 | `CandidateProfile` | I4 | **完成** | 技能 status 改写 + 项目 `{id,text}[]` 增删改 + `userCorrections[]` 审计数组（带 ISO 时间戳）。 |
| F-T3.4 | PDF/DOCX 解析确认 | Resume API | I4 | **未开始**（等后端 B-T3.1）| 解析结果可编辑，保留原文片段。前端 mock 无意义，等 Resume API 实装再做。 |
| F-T3.5 | 匹配报告和学习路径 | `MatchReport`、F-T1.6 | I4 | **完成** | `/diagnosis` 已含置信度卡 + 关键短板 + 排序学习路径 + recalculate 联动技能 status。 |
| F-T3.6 | 岗位标准输出与培养任务 | PublishedJobVersion API | I4 | **未开始**（等后端）| 导出 JD 能力模板、诊断标准、学练赛证式训练任务。 |

### F-T4 评测与交付

| ID | 任务 | 依赖 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| F-T4.1 | 评测中心 | Evaluation API | **完成** | `/evaluation` 3 栏：4 个数据集 + RUN-0825-001 当前运行（命中率 61% / 召回 74% / 置信 84% + 3 条错误案例 + 待复盘）。 |
| F-T4.2 | 任务进度和错误状态 | Pipeline API | **完成** | 6 个新 loading.tsx/error.tsx（`/`、`/new-jobs`、`/evaluation`），与 jobs/skills/diagnosis 模式统一。 |
| F-T4.3 | 响应式、密度与可访问性 | 全部页面 | **完成** | `--font-mono` token、4 处硬编码替换、`@media (max-width: 480px)` 断点、4 个 workbench empty state CTA、aria-label 覆盖完整。 |
| F-T4.4 | Playwright 端到端流程 | 后端稳定 | **完成** | 4 spec 10 用例（jobs/diagnosis/new-jobs/skills 核心流程 + 空错误变体）全过 35.3s。 |
| F-T4.5 | 生产构建和截图验收 | 全部页面 | **完成** | `pnpm build` 13 页面（5 静态 + 8 动态）通过；7 张 Playwright 截图（6 desktop + 1 mobile）保存在 `/tmp/f45/`，视觉 review 通过。 |
| F-T4.6 | 趋势回测与当前趋势页面 | Forecast API | **完成** | `/temporal/forecasts` 读 `backtest-h{30,60,90}.json` 真实 144 条预测，5 选 1 skill + 纯手写 SVG 折线（不引图表库）。 |
| F-T4.7 | 信号流和信号簇视图 | TrendSignal API | **完成** | `/temporal/signals` antd Timeline 渲染 25 条 TrendSignal + Top 5 技能簇摘要 + 3 档时间窗。 |
| F-T4.8 | 预测复盘视图 | Backtest API | **完成** | `/temporal/retrospect` 4 张 Statistic（accuracy vs flat_baseline）+ 6 类 error_types 排序条 + 3 horizon tab 切换。 |
| F-T4.9 | 时间系统与岗位系统入口 | JobImpactSuggestion API | **完成** | `/temporal/suggestions` 3 条 PENDING 建议 + 接受/修改/拒绝（修改 Modal 改 suggested_level），按 design.md L108「不能与已发布岗位事实并列」独立成页。 |
| F-T4.10 | 我的任务与领取流程 | ReviewTask API | **完成** | `/tasks` 左列表 5 条任务（3 forecast_review + 2 job_review，2 标「需双审」），领取 → 审核中 → 提交 → 完成 4 状态机。 |
| F-T4.11 | 审核工作区 | ReviewTask/Evidence API | **完成** | `/tasks` 右侧 3 段工作区（系统结果 / 证据 / 人工决策），决策按钮复用 `ReviewActions`（onAccept/onModify/onReject）。 |
| F-T4.12 | 质量看板与运行对比 | Quality/Evaluation API | **进行中** | `/quality` 指标从 review/eval API 获取；Run 对比和错误分布仍需完成真实 API 接线。 |

## 联调门

| 门 | 前端状态 | 后端提供 | 通过条件 |
| --- | --- | --- | --- |
| I1 新岗位 | ✓ 候选列表 + 定义编辑器就绪 | Emerging Job API | 字段、状态、证据引用一致 |
| I2 岗位 Diff | ✓ Diff 页面 + 发布确认就绪 | Job Diff / Publish API | 新增/删除/修改和版本状态一致 |
| I3 图谱证据 | ✓ 图谱 + 节点详情 + 抽屉就绪 | Graph / Evidence API | 节点和证据可通过同一 `job_version_id` 关联 |
| I4 人岗诊断 | ✓ 画像 + 报告 + 学习路径就绪 | Resume / Match API | 修正画像后可重新计算报告 |

## 前端完成定义

> 14/16 勾选；2 项依赖后端。

- [x] 页面使用 `design.md` 的 Token，不自行添加颜色和字号。`app-theme.tsx` + `globals.css :root` + `app/jddiff` 复用现有 token
- [x] 基础交互使用 Ant Design 6，AI 交互使用 Ant Design X 2.x，不重复实现等价基础组件。
- [x] 主路径是结构化任务流程；对话只是上下文辅助入口，不承载核心结论。**当前无 AI 流程入口（设计文档留位）**
- [x] AI 输出进入固定 View Model、证据和审核流，不直接伪装成正式岗位事实。
- [x] 页面没有重复标题、无意义眉题、冗余说明或无法解释的垃圾留白。F-T4.5 截图 review 通过
- [x] 熟悉操作使用图标，图标按钮具备 Tooltip 和 `aria-label`；业务数据保留文本。
- [x] AI 过程只展示可审计状态、工具和结果，不展示隐藏思维链。
- [x] 页面只消费 `contracts.md` 定义的 View Model。`lib/api/types.ts` re-export
- [x] 所有异步任务有进度、失败和重试状态。13 个 page + 6 个 loading.tsx + 6 个 error.tsx
- [x] 所有结论可以打开证据抽屉。`EvidenceDrawer` 4 个 workbench 复用
- [x] 岗位结论、图谱节点和匹配报告均按"结论 -> 变化 -> 依据 -> 行动"呈现；不得只显示模型总分或长篇 AI 文本。
- [x] Mock 与真实 API 使用同一 TypeScript 类型。`apiFetch<T>` + `isMockMode()` 切换
- [x] 三条核心流程通过 Playwright。10/10 用例（jobs/diagnosis/new-jobs/skills + empty/error 变体）全过 35.3s
- [x] 历史回测页和当前趋势页不直接修改岗位版本，只展示预测和更新建议。`/temporal/forecasts` + `/temporal/retrospect` 只读 mock
- [x] 时间情报页面使用自己的任务语义，不复制旧仿真项目的事件回放界面。
- [x] 审核者无需下载数据包，即可在前端完成标注、复盘和岗位审核。`/tasks` + `/quality` 一页式 mock
- [ ] **F-T3.4 PDF/DOCX 解析确认**：等后端 B-T3.1 Resume API
- [ ] **F-T3.6 岗位标准输出与培养任务**：等后端 PublishedJobVersion API

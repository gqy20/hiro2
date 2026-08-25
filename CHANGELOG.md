# 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的记录方式，并使用语义化提交信息。

## [Unreleased]

### Added
- 增加 JD 解析管线（jdxtract）：三源合并 342 条全量解析，职责/要求（必备加分标记）/技能原词/词典归一 + 模型语义领域判定（is_ai_role+理由，staged 全量入库、curated 按判定过滤）；51job 扩采 386 条（六城），boss 详情 85 条可用。
- 增加 Excel 岗位画像抽取（exskill）：46 岗位职责简介 → 结构化职责/要求/技能原词 + 词典归一（46/46 零隔离）；46 岗位名清洗为 59 个搜索关键词用于 JD 扩采；词典 v5 补专家短形别名。
- 打通 boss直聘 采集：OpenCLI 扩展标签页导航 + mitmproxy 网络层捕获（页面零感知），jdboss 抓取 6 关键词 92 条含明文薪资与技能标签；jdserve 集成 mitm 启停，形成 51job(CDP)+boss(mitm) 双通路。

- 增加归一化时间闸门：语料习得别名独立为 `data/SKILLS-EARNED.yml` 并带首见日期，`resolve --as-of` 时未来习得词不参与匹配，防止回测规则泄漏；新增分桶覆盖率与带上下文的未命中词单。
- 事件抽取改为逐篇落盘并提升并发至 5，长批次中断不丢已完成结果。

- 建立前端 API Client（F-T1.5）：`lib/api/{types,client,queries}.ts` 三件套 + `app/jobs/{loading,error}.tsx` 路由级边界；通过 `NEXT_PUBLIC_USE_MOCK` 环境变量在 fixture 与真实后端之间切换，默认 mock，本地无后端时也不阻塞前端验证。`/jobs` 页迁入 `getJobUpdate()`，作为后续页面迁移的模板；不引入新依赖，全部用 Next.js 16 + 原生 `fetch`。

- 完成 F-T2.3 + F-T2.4：`/jobs` 页面支持空/错误态（`?state=empty|error`，与 `new-jobs`、`diagnosis` 对齐）、发布流走 `publishJobVersion()`（mock 模式 1.4s 模拟延迟，real 模式 POST `/api/v1/jobs/{id}/versions/{version}/publish`）、发布成功视图（`components/publish-result.tsx`）显示 `v1.5 已发布`、本次审核记录（已接受/已拒绝/待确认）与「返回岗位更新」按钮；新增「下游影响」section 联动技能图谱入口。`apiFetch` 增加 POST 支持与对应测试；修复 Modal `confirmLoading` 阻止首次 onOk 的状态耦合（拆出 `publishModalOpen` 与 `publishing` 两个独立 state）。`lib/api/queries.ts` 收紧为仅含客户端可调用 mutation，RSC 页面直接走 fixture 加载器，避免 `node:fs/promises` 被拉进客户端 bundle。

- 完成一级导航补齐：新建 `app/skills/page.tsx`、`app/evaluation/page.tsx` 占位骨架（F-T3.1、F-T4.1 待接入），并把原 `app/[view]` 兜底路由删除（已被具体页面接管）；`app/page.tsx` 从 `redirect("/jobs")` 改为真实工作台（4 张数字卡：新岗位待审 / 岗位更新待审 / 诊断中 / 今日回测，跳转到对应一级页面）。`use client` 因 `next/link` 引入，不引新依赖。

- 完成 F-T3.1 技能图谱：新增 `@xyflow/react` 依赖；`/skills` 从占位升级为真实图谱（30 capability + 11 skill points 共 41 节点），按 `JobVersion` 必备蓝 / 加分中性 / 新增蓝虚线 / 修改黄虚线着色；4 维筛选（技术栈 / 级别 / 能力类型 / 全部清除）；选中节点打开底部指标条 + 复用 `EvidenceDrawer`。`data/fixtures/skill{,_empty,_error}.json` + `lib/skill.ts`（类型）+ `lib/skill-fixture.ts`（RSC-safe loader）；`components/skill-graph.tsx`（xyflow 容器）+ `components/skills-workbench.tsx`（主 workbench）；RSC 页面直接处理 mock/real 切换，避免 `node:fs` 进客户端 bundle。F-T3.2 节点详情侧栏留独立 PR。

- 完成 F-T3.2 节点详情侧栏：`/skills` 从 2 栏（toolbar + stage）升级为 3 栏（toolbar + stage + 320px detail），删除底部 metrics bar（信息上移）。新增 `components/skill-node-detail.tsx`：按 design.md「结论→变化→依据→行动」组织（节点身份 + 别名表 + 父能力/兄弟/下属技能点 + 证据摘要 + JobVersion 占位）；空态显示引导「选择节点查看详情与证据」。`globals.css` 改 `.skill-graph-layout` 为三列网格 + 响应式断点（1180px 第三栏下移，980px 单列堆叠）。F-T3.5 关联 JobVersion / SkillSignal 等后端数据接入后再补「关联岗位版本」section。

- 完成 F-T3.3 简历画像增强：`/diagnosis` 项目证据从只读 `string[]` 升级为 `{id, text}[]`，新增增/改/删 UI（编辑态回滚 + 删除即移除）；技能 status 修改与项目增删改全部入 `userCorrections` 审计数组（带 ISO 时间戳 + 字段类型），UI 显示「本次会话已记录 N 条修改（仅本地）」。`DiagnosisFixture` 类型扩展：`ProjectEntry`、`UserCorrection`（含 `field`/`target`/`before`/`after`）；empty/error fixture 同步升 projects 格式 + userCorrections: []。补齐 `app/diagnosis/{loading,error}.tsx` 路由级边界（与 jobs/skills 模式一致）。后端持久化留待 I4 联调门接通后做。

- 完成 F-T4.4 Playwright 端到端：新增 `@playwright/test@1.62.1` 依赖；`apps/web/playwright.config.ts`（单 worker + webServer 自动启 dev）；`tests/e2e/` 下 4 个 spec 共 10 个用例覆盖 4 条核心流程 + 空/错误变体：jobs（接受 6 条 → 发布 → 成功视图 → 返回）、diagnosis（项目增删改 + 审计计数 + 重新计算）、new-jobs（接受候选 + 编辑 5 要素 + 保存）、skills（41 节点 + 选中 cap_04 + 切换 MCP + 3 维筛选器）。`/new-jobs` 编辑器 5 个 textarea 补 aria-label 顺带 a11y。`Makefile` 加 `test-e2e` 目标（自动 `playwright install --with-deps chromium`）；`pnpm test:e2e` 一键跑；`.github/workflows/ci.yml` 加 e2e step + timeout 30min；`apps/web/vitest.config.ts` 排除 `tests/e2e/` 避免 vitest 误抓；`.gitignore` 加 `playwright-report/` 与 `test-results/`。本地 31.8s 全过。

- 完成 F-T4.1 评测中心：3 栏 workbench（数据集列表 + 运行指标 + 错误案例 + 待复盘），4 个数据集 + 1 个当前运行 RUN-0825-001（命中率/召回率/置信度 3 项指标 + 3 条错误案例），数据全部 inline mock（后端 B-T4 未开始；EvaluationMetrics 在 contracts.md 不存在）。1180/980 响应式断点与 jobs/skills/diagnosis 对齐。`components/evaluation-workbench.tsx` + `app/evaluation/page.tsx` 升级 + `app/evaluation/{loading,error}.tsx` 路由级边界。

- 完成 F-T4.2 路由级 loading.tsx / error.tsx 补齐：`/`、`/new-jobs`、`/evaluation` 三个缺边界的页面现在与 jobs/skills/diagnosis 模式一致。`app/{loading,error}.tsx` + `app/new-jobs/{loading,error}.tsx` + `app/evaluation/{loading,error}.tsx` 共 6 个新文件，每个 ~35 行。

- 完成 F-T4.3 响应式 + 字体 token + 空状态 CTA：`globals.css` :root 加 `--font-mono` token，4 处硬编码「IBM Plex Mono」统一改 `var(--font-mono)`；加 `@media (max-width: 480px)` 断点覆盖 390px 视口（workbench padding 减、3 栏转单列、metric grid 单列、标题字号 -1）。`workflow-ui.tsx` FixtureState 加 `action` prop，4 个 workbench empty state 补明确 CTA（jobs 回工作台、new-jobs 浏览现有岗位、skills 查看岗位更新、diagnosis 查看岗位）。10 个 e2e 用例全过。

- 完成 F-T4.7/4.6/4.8/4.9 时间情报四件套：新增 4 个次级页面 `/temporal/{signals,forecasts,retrospect,suggestions}` + `/temporal` 索引页，全部 mock 数据驱动（不接后端 B-T2/B-T4）：
  * 信号流用 antd `Timeline` 渲染 25 条 TrendSignal + Top 5 技能簇摘要 + 3 档时间窗筛选
  * 趋势回测读 `data/processed/wechat-mp/backtest-h{30,60,90}.json` 真实数据，含 3 horizon + 144 条预测 + accuracy vs flat_baseline + 纯手写 SVG 折线（不引图表库）
  * 预测复盘用 4 张 `Statistic` 卡 + 6 类误差分布
  * 影响建议列表支持接受/修改/拒绝三按钮（`review-ui.tsx` 的 `ReviewActions` 新增 `onModify` 可选 prop），按 `contracts.md:108`「不能与已发布岗位事实并列」原则不污染 `/jobs` 主页
  * 数据来源：`lib/temporal-fixture.ts` 一次性从 `wechat-mp/` 4 个 JSONL/JSON 读出 → 返回 `TemporalDataset { backtests, backtestRecords, forecasts, signals, suggestions }`
  * 类型：`lib/temporal.ts` 严格照 `contracts.md:131-279` DTO 形状
- `app/page.tsx` dashboard 加 1 张「时间情报」跳转卡（仍保持 6 项一级导航不变）
- 路由级 loading.tsx / error.tsx 全部 5 页（`/temporal`、`/temporal/{signals,forecasts,retrospect,suggestions}`）照 jobs/skills/diagnosis 模板
- `globals.css` 加 ~250 行 `.temporal-*` 样式（含 1180px 响应式断点）
- 10 个 e2e 用例全过（regression 通过）

- 完成 F-T4.5 生产构建 + 截图验收：`pnpm build` 成功（13 个页面，5 个静态 + 8 个动态），本地 `pnpm start` 跑 prod build 验证 200。Playwright 桌面 1280×720 截 6 页（`/`、`/jobs`、`/skills`、`/new-jobs`、`/diagnosis`、`/evaluation`）+ 移动 390×844 截 1 页（`/skills`）。视觉 review 通过：标题无冗余、文案简短（占位 CTA 显式）、符号规范（→ `·` `/` Tag 而非 `>` `x` 字符）、desktop 信息密度合理、mobile 折行 1 列 OK、F-T4.3 的 480px 断点与 F-T4.1 的 1180px 断点都生效。截图保存在 `/tmp/f45/`（7 张 PNG）。

- 建立 D8 回测基础设施：SkillSnapshot 特征层（事实分级加权）、确定性方向预测 v1、月度滚动回测（双 as_of 闸门防泄漏）；v1 动量规则实测低于全平基线，错误集中在爆发后回落，结论如实记录。

- 完成 D4 全量归一化验收：697 篇事件 12605 次提及，中高频覆盖率 85.2%、高频 94.0%；离线归一任务（skillmap）产出 1053 个候选，665 个高置信合入习得词典；时间闸门实测词典随 as_of 正确截断。

- 建立技能归一化词典（D4）：`data/SKILLS.yml` v3 以 Excel 30 能力为骨架，含技能点与别名表；`backend/skills/resolver.py` 确定性匹配（全角/大小写归一）输出 canonical 能力与技能点；`scripts/resolve.py events` dry-run 输出逐条映射、加权覆盖率与未命中词清单。
- 增加 LLM token 消耗记录：Provider 累计 input/output tokens 与调用次数，写入每次运行 metrics。
- 建立 LLM 基础设施：Anthropic Messages 协议 Provider（读 `.env` 的 `HIRO2_LLM_*`）+ 离线 MockProvider + PromptSpec YAML 加载校验。
- 增加日报事件抽取管线（D6）：`prompts/report-event.yml`（现 v3，含输出数值边界）、`backend/temporal` Pydantic 模型与并发抽取服务、`scripts/extract.py` CLI；校验失败重试、API 异常与解析失败分型隔离，真实网关冒烟通过。
- 建立原始数据来源登记（`data/SOURCES.yml`）与四类来源导入：Excel 能力矩阵、招聘 JD、职业标准、公众号日报归档。
- 增加 `scripts/ingest.py` 数据导入 CLI：来源 manifest 与哈希、46 岗位 x 30 能力矩阵解析、日报索引分级（ok/隔离/未索引三层）与 JD 双层统计。
- 增加数据运行记录 `scripts/runlog.py`：每次导入生成 `run_id` 与 `data/runs/<run_id>/` 结构化日志。
- 增加解析器单元测试（矩阵解析、坏分值标记、时间戳归一化、日报状态分级）。
- 建立 Hiro2 产品、技术、设计、数据和 Roadmap 文档体系。
- 增加时间情报、历史回测、岗位影响建议和协作评测设计。
- 增加 Makefile、uv/pnpm 环境规范和 Git 提交前检查。
- 增加 CI 工作流、环境模板和架构决策记录。
- 明确 YAML Prompt、Pydantic Schema、OpenAPI 类型的分层规则。
- 增加 Python、TypeScript/TSX 文件长度和拆分规则。
- 增加 Claude Code 工作流，并将文件长度规则调整为 500/800/1000 行软阈值。
- 增加招聘、求职、审核和高校观察的用户场景与体验验收文档。
- 按官方赛题重构用户分层，补充岗位全景与能力阶梯场景。
- 增加 AI 应用工程能力链、学练赛证路径和岗位标准培养输出。
- 增加发榜方契合度与招聘平台竞品调研资料。
- 增加国内外 AI 招聘产品调研，明确岗位智能、招聘自动化与 Hiro2 的边界。
- 将“可信岗位版本”确立为产品中心，并补充 AI 应用边界、页面共同信息结构与亮点评测指标。
- 增加结构化 AI 工作台的前端组件选型、交互模型、信息密度规则和外部设计参考。
- 增加岗位更新前端垂直切片，包括版本 Diff、证据抽屉、审核队列和发布确认。
- 增加岗位更新 JSON fixture、演示数据标识和逐条证据原文详情。
- 优化岗位更新筛选条、置信度横条和证据元信息展示，减少非必要框线。
- 微调变化项审核动作，将接受/拒绝收纳为同组低对比操作。
- 将待审、待确认、已接受和已拒绝状态改为统一的内联状态标记。
- 增加 Fixture 驱动的新岗位候选列表和五要素定义工作台，暂不接入后端。
- 增加新岗位定义的前端编辑、保存/取消、空态/错误态 Fixture 和数据校验测试。
- 重构新岗位页面信息层级，突出独立岗位依据与必备能力。
- 增加 Fixture 驱动人岗诊断页面，支持画像修正、匹配短板和学习路径展示。
- 规范化三个前端页面的 Fixture 状态、Section Header、技能状态映射和置信度组件入口。
- 统一岗位更新与新岗位的辅助字号，业务元数据提升至 11px，连续文本保持 12px 以上。
- 微调岗位更新和新岗位的内容内边距、Diff 条目节奏与定义区对齐。

### Changed

- 将日常协作反馈设计为前端任务、审核和评测闭环。

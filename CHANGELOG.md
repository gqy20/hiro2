# 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的记录方式，并使用语义化提交信息。

## [Unreleased]

### Added
- 能力全景岗位切换（`/skills?job=<version_id>`）：后端 `/skills/graph` 的 job 参数打通——未知岗位版本 404（对齐 training-output 模式），默认仍为 ai-agent-v2；岗位列表复用 `/jobs/published`；前端头部新增岗位选择器（URL 参数驱动 RSC 取数，切换重置筛选与选中态），mock 模式配套 `scripts/skillfx.py` 从真实 published 版本生成分岗位快照 fixture（skill_llm-algo-v2 / skill_bigdata-v3），主样本 jobTitle 与 mock 岗位宇宙对齐为 AI Agent 工程师；e2e 新增 2 例（切换重置选中态 + 未知岗位回退），API 契约测试 1 例，contracts.md 补录该端点；同时修复前端长期传后端不识别的 `state` 死参数。
- 简历工作台 V1（求职闭环补投递材料一环，`/career/resume` 新页）：左侧结构化草稿编辑（经历/项目/教育增删行）+ PDF 渲染预览与下载——渲染复用合成测试集同链路（pandoc + PyMuPDF Story，A4 单栏）；右侧确定性建议随目标岗位切换（零 LLM，每条带证据）：coverage 覆盖差（岗位版本必备/加分 vs 草稿技能归一，带市场权重与 JD 数）、specificity 技能点具体化（SKILLS.yml 反查）、structure 结构检查（概述/量化/bullet 数）；域模块 `backend/candidates/resume_build.py`（ResumeDraft/AdviceItem DTO）+ 双端点（advice/render，contracts 已更新）+ mock 分支；域单测 3 例 + API 测试 3 例（CI 无 pandoc 时渲染测试跳过），边界诚实标注：V1 只归一显式技能字段，LLM 表述建议为 V2。
- `docs/onboarding.md` 协作者导览：面向新加入的协作同学，一份文档串起整体逻辑（可信岗位版本主线）、三条边界规则、目录职责、当前缺口（人工抽检标注、岗位+等级双确认 0/266、双人复核、role_mapping v4、Neo4j 投影）与按角色的深入阅读路径；`docs/README.md` 的"先看什么"同步指向它作为入口。
- `docs/competition.md` 与产物全量核对并修正滞后数字：岗位版本 12→17（12 岗位 5 升 v3，`data/processed/jobversions/published/` 实测）；覆盖率 65.12%→68.44%（73 测试实跑）；e2e 10/10→14/14（career.spec 4 条）；证据 6645→14174 条；求职区"五页未建"更正为已闭环（差距收敛为诊断页求职语境优化）；CI 状态由"未建"更正为已上线；JD 指标补注解析层口径（另有 8656 条存档/企业源解析记录）；`docs/README.md` 状态表同步（API 31 路由、前端 26 页、27 表）。
- CI 上线 GitHub Actions（B-T4.12）：私有仓库 gqy20/hiro2（gh 创建 + 全量推送），workflow 全链绿——uv `--frozen` + pnpm `--frozen-lockfile` 锁文件同步、`make verify`（格式/lint/mypy/67 测试）、Playwright e2e、pre-commit 全文件钩子，约 4 分钟；CI 首跑即抓出三层存量格式债并清零（11 个 Python 文件 ruff format、10 个 web 文件 prettier、184 个文件末尾换行/尾随空格钩子修复、test-results 测试产物目录入 prettier ignore）。
- Outbox 常驻消费 worker（B-T4.5 收口）：消费逻辑从 CLI 归位 `backend/application/outbox.consume_batch`——失败不再终态而是退避回 PENDING（60s 起步指数退避封顶 1h，attempts>=5 转 FAILED），`FOR UPDATE SKIP LOCKED` 多消费者安全；常驻 worker 挂 API lifespan（`HIRO2_OUTBOX_WORKER` 开关默认关、compose 默认开、30s 轮询、单轮异常不退出），岗位发布 -> Neo4j 投影全自动一致；`scripts/outbox.py` 变壳；域单测 3 例（开关/退避封顶/重试-终态语义，假连接不依赖 PG）。
- 预测规则回测反哺闭环（rule_version=2）：v1 回测错误结构分析（up 预测 84% 误判于过热追涨、down 48% 误于反弹、高量 flat 稳定）推导 v2——过热抑制（ratio>=3.0 不追涨）+ down 阈值收紧（0.7->0.5）；三 horizon 一致改进（h30 +5.0 / h60 +14.0 / h90 +12.8 点），仍逊平基线如实保留。`forecast.py` 双规则可切换，`backtest.py --rule` 参数化，产物版本化（backtest-h{H}-r2.json），dbimport 双版本导入（backtest_records/forecasts，当前预测统一取最新规则）。复盘页新增“规则迭代对比”区块（v1->v2 三 horizon 命中率 + 平基线对照）——“事件->预测->回测->规则修正->再回测”闭环至此打通。方法论纪律：阈值来自错误分布的结构特征（命中条 ratio 上限 2.94 vs 错误条最大 16.67），非逐点调参。
- 岗位映射 v3 迭代与固定样本对比工具（`scripts/evalcmp.py`）：商务/管理信号排除（销售/TPM/FDE/测试工程师等 23 词）、“无技术信号则降级”规则、族覆写机制（部署/视觉/安全优先于泛别名）与域专门岗保护、别名顺序修正（具体词先于泛词）。**固定 v1 样本严格对比：74% → 95%（修复 21 条、回归 0）**；新冻结样本（eval-v3，llm 桶混入更多英文管理岗）现状 78%，剩余失分定位：BIZ 信号未覆盖“Engineering Manager/Manager of”等管理岗（8 条）、产品岗别名优先级（3 条）、排除规则的 3 条误伤。方法论教训已固化：评测集锚定 method 分层会导致样本漂移，跨版本对比必须锚定 jd_id（evalcmp.py 即此用途）。
- 岗位映射 v2 迭代（评测驱动改进的第一轮完整闭环）：`rolemap.py` 扩充别名表（泛称与应用类关键词，机器学习/深度学习从 NLP 研究员改归算法主体岗——原映射为系统性偏差源）、新增 LLM 结果后置校验（族关键词一致性 + 置信度 <0.6 强制降级）与 `repair` 子命令（零 LLM 成本重判全量 5915 条：规则改判 359 + 校验修正 187）；修复别名匹配对含空格关键词永不命中的 bug。评测集升版 `eval-v2-20260828`（v1 归档 `evaluation/samples/v1/`，标注记录按数据集版本隔离），重冻结 100 条分层样本并重判——**role_mapping 基线 74% → 84%**（+10 点），domain 96%、event 100% 持平。剩余失分：LLM 对非技术岗强行归类（产品经理/销售/TPM/FDE 9 条）、别名误中运营岗（2 条）、族关键词漏“视频”与“AI全栈”（2 条），改进项已记录待下一轮。
- 评测中心接入真实硬指标：`/evaluation/overview` 的 metrics 新增三项准确率（岗位映射/领域判定/事件抽取，读 `evaluation/samples/metrics.json`，标注回流后重跑 `evalset.py score` 即更新），回测命中率与平基线保留为时间情报指标。
- 评测基线首次产出（`prelabel.py apply` 批量采纳 180 条预标注，透明标记 `reviewer_id=ai-prelabel-batch`）：`evalset.py score` 结果 role_mapping **74%**（100 条，llm 映射方法错配 16 + 漏判 2 为主要失分）、domain_judgment **96%**、event_extraction **100%**；任务列表 180 条全部 RESOLVED。role 层距 90% 目标差 16 点，改进方向明确（llm 映射候选集约束 + 泛称职位兜底映射）；正式指标宣称前需人工抽检覆盖（建议 28 条非 ACCEPT 全复核 + ACCEPT 抽 10%）。
- 评测样本 AI 预标注（`scripts/prelabel.py` -> `evaluation/prelabels.jsonl`）：180 条冻结样本逐条建议判定（ACCEPT 152 / MODIFY 16 / REJECT 12），每条带置信度与理由、MODIFY 带修正岗位 id；任务 VM 挂载 `system_output.prelabel`，`/tasks` 页新增“AI 预标注建议（候选）”区块与“采纳建议（可修改后提交）”按钮——建议不计入指标，人工确认提交后才写入 annotations.jsonl，遵循“AI 只产候选、人来发布”原则。预标注初判：role_mapping 约 74%（llm 方法为主要错源）、domain 约 94%、event 约 100%，role 层距 90% 目标线有差距，需人工复核后确认真实基线。
- 求职区首页双态与诊断求职视图深化：`GET /api/v1/career/home` 端点（读取 `candidate_targets` 活跃目标，DB 不可用时回退演示候选人）；`/career` 首页按目标存在性双态渲染——未选岗位只留“选择目标岗位/上传简历”两个入口，已选显示目标岗位与版本；诊断工作台与首页的“投递基础”让位于“必备能力 x/n”（`requiredMet/requiredTotal`，总分降为小字辅助），成长计划从手写模板改为渲染真实学练赛证四段字段；学练赛证渲染抽为共享组件 `gap-steps.tsx`（学习路径页与诊断页复用）。
- 求职流程 e2e 用例 3 条（`tests/e2e/career.spec.ts`）：目标岗位卡与族筛选、首页 ready/empty 双态、学习路径学练赛证步骤；全量 13/13 通过。
- 三工作区设计文档成套：`docs/design-data.md` 新建（数据工作区六页：总览/来源/流水线/审核任务/评测与质量/时间情报，明确收纳 `/datasets`、`/quality`、时间情报等游离页）；`docs/design-recruiting.md` 扩充岗位发现、能力图谱、候选人诊断三个页面章节；`docs/design-career.md` 校准目标岗位页、诊断三栏布局并新增“我的画像”章节。
- `docs/competition.md` 比赛对标与亮点叙事：官方硬指标现状表（337 条 JD 与 65.12% 覆盖率达标，三项准确率因标注 0/180 未产生数值）、四项评分项差距分析、四层亮点叙事与 8 分钟演示动线、按 ROI 排序的行动清单。
- 求职成长工作区补齐为五页闭环：`/career/jobs` 目标岗位页（岗位卡：名称/版本/首条职责/必备加分能力数/生效时间，岗位族 Segmented 筛选）与 `/career/path` 学习路径页（缺口按优先级排序，学练赛证四段呈现，顶部 WorkflowContext 固定目标岗位与版本上下文）；顶栏 career 工作区导航 3→5 项（首页/目标岗位/我的画像/候选诊断/学习路径），招聘与数据工作区导航不受影响。
- `GET /api/v1/jobs/published` 已发布岗位版本列表端点（`backend/application/joblist.py`）：每岗位取最新发布版本，经 job_id 内嵌 pos_XX 结构化关联岗位目录补充岗位族与首条职责，12 岗位。

### Fixed
- 前端界面文案语言规范化（AGENTS.md 第 8 节，与文档侧同批）：质量看板"Run 对比/Run A·B/vs/horizon X 天"→"运行对比/运行 A·B/对比/预测期 X 天"；我的岗位页"快照 Diff"→"快照差异"；发布结果页裸枚举标签 `PUBLISHED`→"已发布"；影响建议页下拉选项"required（必备）"等中英重复表述→纯中文（从已有 LEVEL_LABEL 映射派生，顺带消除"暂不纳入/不在范围"两套译法）；技术传导页图例"各层 onset"→"各层起始月"；简历解析演示文案内部 ID 裸露"疑似 cap_06 RAG/知识库"→"疑似 RAG/知识库（cap_06）"。
- 影响建议审核断链修复：`POST /api/v1/temporal/suggestions/{id}/review` 端点上线，`/temporal/suggestions` 页的接受/修改/拒绝从纯前端本地状态改为写入 append-only 审核日志（复用 `review-actions.jsonl` 与 PG `review_actions` 双写通道，`sug-` 前缀 target_id 区分建议审核）；VM 构建时合并最新审核状态（含 modified 的 suggested_level 变更），刷新后状态保持。已接受/已修改的建议卡显示“前往岗位更新流程”接力入口——建议仍不直接修改岗位版本，岗位变更须走 Diff 审核发布流程（边界不变）。
- 诊断 DB 路径岗位版本查询补齐 `required_skills` 列（原 SELECT 缺列导致 `requiredTotal` 恒为 0），与文件路径键名对齐。
- 评测标注管道断链修复：新增 `POST /api/v1/tasks/{task_id}/decision` 提交端点与 `backend/application/annotate.py`（append-only 写入 `evaluation/annotations.jsonl`，不动冻结样本 CSV 的 manifest 哈希）；`/tasks` 页提交按钮从纯本地状态改为接入真实 API（mock 模式保持本地状态机）；`evalset.py score` 计算时按 task_id 优先合并标注记录（ACCEPT=对 / MODIFY·REJECT=错 / UNKNOWN 不计入分母），CSV 手工判定列保留为兼容回退——修复前“freeze→任务→提交→指标”链路在提交处完全断开，标注结果无法回流为准确率。
- 匹配报告缺口字段补全学练赛证四段：`GapVM` 新增 `practice`/`evaluate`/`certify`，从学习路径 steps 合入（原仅有 action=learn 一段）。
- 数据流转图四步流水线状态修复：后端 `pipeline_runs` View Model 新增已核实的 component → stage 映射（ingest/extract/evidence/signal/other，依据各采集/处理脚本 docstring），不再让前端按组件名猜测导致永远“暂无运行”；`/data` 运行拉取窗口 20 → 100，保证四阶段能取到最近一次运行。
- `GET /pipeline-runs` 的 `total` 字段修复：此前直接等于当前页条数（limit=5 返回 total=5），现返回时间窗口内真实总数；流水线页显示“显示最近 50 / 共 200 次运行”。
- Pipeline run 状态大小写归一：后端读取时统一大写（历史 events.jsonl 存在 `succeeded`/`SUCCEEDED` 混写）；前端僵死识别——RUNNING 超过 30 分钟无终态事件显示为“疑似中断”（灰色），不再与真实进行中混淆。
- 顶栏“数据截至 08-22”硬编码修复：改为客户端拉取 `/datasets/overview` 取最近 `updated_at` 动态显示，mock 模式或请求失败时不显示。
- 时间展示统一为 Asia/Shanghai：新增 `lib/time.ts`（`formatTime`/`formatDate`/`todayStr`），替换流水线页与流转图中基于 `toISOString()` 的 UTC 显示（此前差 8 小时），“今日处理”按上海时区切日。
- 数据总览 KPI 口径修复：“今日处理”suffix 计入进行中（如“成功 6 · 进行中 14”，此前 19 个 RUNNING 被静默吞掉）；待处理记录占比 0.096% 不再被四舍五入成“0%”，显示 `<0.1%`。
- 质量页消费 `data_quality` 可用性标记：unavailable 的指标（双重审核率/平均响应/错误分布）显示“暂无数据”而非 0 值；标题由“质量与回测”改为与实际内容一致的“标注质量”。
- 术语统一：“数据域”全站改为“数据集”；数据资产页“记录总量”的误导性标注“条有效记录”改为“条记录”（total_records 含无效记录）。
- 来源明细硬编码数字移除：`/datasets/overview` 的 DatasetItem 新增 `sources` 字段，由后端读取 `data/SOURCES.yml`（D0 来源登记）按数据集挂载来源通道（jd→5 条采集通道、temporal→wechat-mp/feeds/arxiv/pypi-pkgstats、capability→含政策/O*NET 历史），前端删除写死的 SOURCE_DETAIL（“字节 376/51job 650/Wayback 13,071”等与 KPI 对不上的旧数字）；派生（evidence）、受控（resumes）、冻结（evaluation）数据集显示派生说明而非虚构通道。

### Changed
- 文档语言规范化（AGENTS.md 第 8 节，全项目 17 份主文档）："双 as_of 闸门"改写为"预测侧双重时间截止闸门"并写明机制（信号数据与技能词典各自只使用截止日当时已可用的版本）；其余同类修正：MatchReport→匹配报告、三 horizon→三个预测期、ACCEPT→"接受"判定、BIZ 信号→商务/管理信号、reviewer→标注者、role_mapping→岗位映射、fail-under=60→下限 60%、Diff→对比/差异、Temporal Intelligence/Job Capability Graph/Candidate Matching→时间情报域/岗位图谱域/人岗诊断域、Application Use Case→应用层用例、View Model→展示模型、ground truth→后验真值。命令、数据字段、DTO 名与产品名保留英文并用反引号标记；`adr/` 为不可变历史决策记录不动，`archive/`/`research/` 不在主文档范围。
- CSS 按工作区/域拆分归位：`dashboard.css` 更名 `recruiting.css`（招聘区）；求职区样式（career-home/jobs/path/profile/proof 共 373 行）抽出为 `career.css`；质量看板与评测嵌入块移入 `evaluation.css`；`datasets.css` 并入 `data.css`（数据集目录已归入数据区总览）；`globals.css` 改为“基础层 -> 共享组件 -> 工作区/域”的有序导入。拆分只移动不改规则，计算样式抽查（career 卡片 saffron-soft 背景/10px 圆角、quality min-height）与 e2e 14/14、smoke 22/22 全绿验证无渲染回归。
- 数据工作区收纳为六项导航（总览/来源/流水线/审核任务/评测与质量/时间情报）：`/datasets` 并入总览页数据集目录区块（`DatasetWorkbench` 新增 embedded 模式），`/data/quality` 与 `/quality` 并入评测与质量页（`DataQualityWorkbench`/`QualityWorkbench` embedded），旧路由全部重定向不 404；`/temporal` 五子页归入数据工作区并补“时间轴”二级 tab；招聘工作区导航收敛为五项（工作台/岗位发现/我的岗位/能力全景/候选诊断），评测中心、数据资产、简历解析撤出业务导航。
- 简历解析并入诊断流程：`/resumes` 确认画像后可“前往诊断”，诊断页画像区新增“从简历导入”入口；我的岗位卡片审核入口带待处理计数（“审核变化（13）→”）。
- `/data` 总览删除“时间情报”窄带（信息与流转图重复），流转图高度余量放大，主要内容获得更多纵向空间；四个数据页页内大标题移除（顶部导航已承担当前位置表达），改为 sr-only 隐藏标题保留无障碍文档大纲。
- 全站最小字号清理：中文辅助文字一律 ≥12px（工作台指标标签、workflow-context 阶段标签、new-jobs 候选人标签等 10px→12px），纯数字/ID/图表刻度 ≥11px；流转图 SVG 文字整体上抬（meta 11→12、status 11→12、time 10→11）。
- 来源详情抽屉排版重做：统计格从 4 列挤排改为 2×2 卡片（值 22px）；来源列表改为通道卡片（id 等宽字体 + 中文类型徽章 + 时间窗/采集模式 meta 行 + notes 正文段落）；抽屉内层级统一为标题 18px / 小节 13px / 正文 12px。
- 表格体系统一：新增 `.t-table` 共享基础样式（9px/14px 单元格距、垂直居中、粘附表头 + 底线、行 hover、`.num` 右对齐表格数字），`/data/sources`、`/data/pipeline`、`/datasets` 三张表共用；字号走 token（正文 `--fs-table: 15px`、表头与表内辅助 `--fs-table-aux: 13px`）；三张表全部改为 `table-layout: fixed` + 按内容字数标定的 colgroup（每列都有宽度，宽屏剩余空间按列宽比例分配，一行留白均匀，实测 4K 下六列等比 ×4.73 放大；窄屏容器横向滚动）；筛选 select 统一为 `.col-filter`（原生 select 自绘样式：26px 定高 + 16px 行高，文字与 chevron 中心严格同轴）。
- 质量页布局填满：错误分布面板 flex 拉伸占满剩余高度，空态文案垂直居中，页脚贴底，消除下半屏留白。
- 流转图 caption“5 个数据源 · 4 步处理 · 2 个用户界面”删除（与图内节点信息重复）。
- `/data` 总览布局填满：流转图容器改 stretch 撑满剩余高度，底部留白 131px→32px；流转图来源节点 meta 去掉常态冗余的“可用”，版本号只保留 vN 段（jd-v3 → v3，前缀与节点名重复），状态非常态时才追加显示。
- 来源明细交互重构：`/data` 流转图节点与 `/data/sources` 表格行的详情面板，从“挤压主内容的右侧栏”改为复用 `/datasets` 的右侧抽屉模式（遮罩 + 滑入动画 + reduced-motion 降级）；新增 Esc 关闭、再点同一来源 toggle、打开时焦点落到关闭按钮、遮罩点击关闭；`/data/sources` 无 SOURCE_DETAIL 明细的行（如评测样本）也可打开查看统计；`/datasets` 抽屉同步补 Esc 关闭。
- 字体全站统一并自托管：通过 `next/font/google` 内嵌 Inter（正文西文）、IBM Plex Mono 400/500/600（run_id / 版本号 / 时间戳等等宽场景）、Archivo Narrow（KPI 大数字与页面标题的窄体西文，替代系统字体 Arial Narrow），构建期内嵌字体文件，不再依赖用户系统是否安装；中文不打包，继续走系统栈（Noto Sans SC / PingFang SC / Microsoft YaHei）。`foundation.css` 新增 `--font-sans` / `--font-mono` / `--font-display` 三级字体 token，清除 `data/dashboard/datasets/layout/evaluation` 五个样式表中所有硬编码 `"IBM Plex Mono"` / `"Arial Narrow"` / 裸 `monospace` 栈，统一走 token。修复前 Linux 环境下 IBM Plex Mono 未安装导致等宽场景退化为文泉驿正黑（非等宽、数字对齐失效）的问题，实测各页等宽渲染 1/W 同宽。
- 数据工作区字号体系统一：新增 5 级字号 token（`--fs-display: 30px` KPI 大数字 / `--fs-title: 24px` 页面 H1 / `--fs-section: 16px` 区块标题 / `--fs-body: 13px` 正文表格 / `--fs-aux: 12px` 辅助说明，12px 为中文下限）；五个数据页 H1 统一 24px（原 34/30/22 三种），KPI 大数字统一 30px（删除首卡 38px 特例、质量页 36px、资产页 28px）；状态徽章、列头筛选、表格辅助列从 9~11px 提升到 12px；中文标签去掉对其无效的 uppercase + letter-spacing + 西文 mono 字体（mono 仅保留给 run_id、版本号等纯 ASCII 字段）；流转图 SVG 内文字 9/10px 提升到 10/11px。
- 数据流转图来源明细改右侧栏：点击来源节点不再挤占大图下方，改为右侧 320px 明细栏展开厂商/时间窗明细，大图保持完整可见；选中节点高亮。数据来源页同步接入：点击表格行在右侧展开同一份明细（复用 `SOURCE_DETAIL`），类型/状态筛选移入对应列头、搜索移到标题行，独立工具栏删除。
- 流水线页重构：删除与真实数据脱节的"四步抽象阶段"条（按 ingest/extract/evidence/signal 匹配组件永远为空，`signal` 永不匹配），删除独立筛选工具栏，将组件/状态筛选移入对应列头（下拉内嵌表头），控制即列头；表格向上扩展利用更多纵向空间。
- 数据首页来源节点可点开：点击数据流转图的源节点展开厂商/时间窗明细面板（如"招聘岗位"展开为 jd-corp 字节 376/腾讯 208/阿里 98 · jd-opencli 51job 650/BOSS 540 · jd-archive Wayback 13,071 条三条通道及各自时间窗），明细来自 `data/SOURCES.yml` 登记；关闭按钮收起。
- 修复数据工作区导航高亮错误：`isActive` 前缀匹配导致"总览"（`/data`）在 `/data/sources` 等子页下也点亮；改为精确匹配，仅当前路由高亮。
- 数据首页 KPI 重排为单条面板：总记录数（英雄数字 38px）+ 每项数字与补充信息同行（如"就绪数据集 6 / 6 个数据域"），消除三行卡片的碎片感。
- 数据工作区去方框感：卡片/面板圆角 4px→12px、SVG 节点 rx=12、边框统一减弱为 `--line-soft`；选择框/输入框圆角→10px 并加 saffron focus 光晕；表格去掉每行横线（仅留表头底线）、行距加大；状态徽章 pill 化（999px 圆角 + 更饱满内边距）；流水线四步改单容器 + 细分隔；顶栏工作区切换按钮 pill 化。
- 数据工作区导航与顶栏统一：数据工作区不再使用页内独立 `DataNav` subnav，四个入口（总览 / 来源 / 流水线 / 质量）并入顶部主导航（`AppShell` 数据模式），与招聘 / 成长工作区同构；`isActive` 改前缀匹配支持子路由高亮；`data-nav` 组件与 subnav 样式删除。
- 数据工作区密度与可操作性优化（对标 Linear/Stripe 驾驶舱范式）：`/data` KPI 从 2 卡扩为 4 卡并去掉 640px 宽度限制（总记录数 / 今日处理 / 就绪数据集 / 待处理记录），移除从未使用的 sparkline 占位；流水线 strip 每步节点补充最近运行时间与计数；`/data/sources` 与 `/data/pipeline` 表格支持点击表头排序（默认记录数降序 / 开始时间降序）；`/data/*` 四页新增 `loading.tsx` 骨架。
- Railway 部署适配：API/Web 使用平台动态端口，CORS 与简历档案路径支持环境变量，生产镜像排除本地密钥和原始文件。
- 新增内部质量模式的数据资产工作区，展示数据域规模、质量、版本和可重建流转链路。
- 数据导入升级为版本化快照登记：新增 `dataset_versions` 表，`dbimport` 记录 manifest 哈希、`run_id`、数量和质量状态，数据资产 API 优先读取 PostgreSQL。

### Added
- PG 全量同步六域（`migrations/0008_domain_ext.sql` + dbimport 扩域）：新增 policies（109 条）/ dadian_careers（4,335 行=2015 Excel + 2022 公示稿 + API 活数据三版按 version_id 共存）/ arxiv_papers（14,830 去重）/ resume_archive（72 条含 stats+profile JSONB）四表；dbimport 全域重跑后 PG 23 表 ~52K 行与文件层完全对齐——events 缺口 2,167 为 is_primary=False 的去重副件（设计保留），arxiv 缺口 100 为跨 query 重复幂等跳过，**真缺口为零**；部署链路就绪（Railway 侧重放 make db-migrate + db-import 即可）。
- 词典批次二（中频词消化）：count 5~19 共 2,171 词（覆盖 19,279 次提及）LLM 归派 2,003 候选——高置信 ≥0.9 有 342 词，扣除红线词（编程语言域外）与已有词后自动合入 310 词入 SKILLS-EARNED v5（Natural Language Processing/multi-agent orchestration/GPU programming/query optimization 等，ML/DL算法 42 词最多、云计算 35、SQL/数据库 28）；中置信 638 词留 alias-candidates.jsonl 人工复核；噪声 1,011 词拒绝；命中率全池 25.6%→30.8%（英文 18.7%→21.8%），350 万 input tokens / 4,636 次调用 / 25 分钟（进度日志 ETA 实时可见）。
- O*NET 历史版本采集与美国侧技术演化（`scripts/onetget.py` + `onet-history` 来源，B 站资源帖溯源至官方 onetcenter.org/db_releases.html）：5 个代表版本（2005~2025）双 URL 模式下载，表名随版本演化适配（Technology Skills→Software Skills，Workplace Example 列名差异，修'Skills'模糊匹配误中'Skills to Work Context'两处数据坑）；技术演化结论——Python 标注职业 2020 93→2025 132、Apache Spark 7→23、PyTorch 4/TensorFlow 5（2025 新标注）、Hugging Face 1，2005-2015 全零（AI 技术在职业标准中 2020 后才成体系出现）；职业维度 Data Scientists 2020 首现（15-2051.00），2005-2015 无任何 AI 命名职业；与美国侧对照的中国侧演化链完整（大典 2015→2022→动态新增 + 四层时间轴）。
- 职业大典三段式演化（用户提供 2022 版社会公示稿 PDF 570 页）：PyMuPDF 提取公示稿全量 1,636 职业条目（官方口径 1,639，99.8%），与 osta API 活数据（1,676）对照——**公示后动态新增 76 个职业**（含 2023~2025 全部批次：生成式 AI 系统应用员、网络主播、用户增长运营师、无人机群飞行规划员、养老服务师、智能制造系统运维员等），反向差异 36 个抽查为名称截断/格式差异非真缺失；三段式入典时间轴落盘 dadian-evolution.json（2015 版已有 → 2022 版新增 → 2022 后动态新增），每个职业可回答"政策上何时诞生"。
- 职业大典 2015→2022 版本对比：dadianget --all 拉取 2022 版全量 1,676 职业；2015 版从政府网转载源下载结构化 Excel（1,036 职业，含 2019 首批新职业入典记录）+ 164MB 官方 PDF 备档；名称归一 diff 落盘 dadian-2015-2022-diff.json——数字技术域 2015→2022 新增 23 个职业（数据安全工程技术人员/生成式 AI 系统应用员/数字化解决方案设计师/智能硬件装调员等，全部带官方编码与工种数），2015 版 AI 相关仅 6 个；如实注明 diff 总数（+758/-118）因两侧覆盖不对等（Excel 为有标准的子集）不可按字面读（官方口径净增 158）。
- 政策数据接入（`scripts/policyget.py` + `policy` 来源）：gov.cn 统一检索 API 直通（国务院+部委两库，纯 HTTP JSON），9 个关键词扫描 109 条政策文件（标题/发文机关/发布时间/全文链接，URL 幂等），核心锚点含 2017 新一代 AI 发展规划、2025"人工智能+"行动意见、2026 各行业 AI+ 实施意见，按年覆盖 2010~2026；职业目录改用 osta.org.cn 职业分类大典系统结构化 API 并脚本化 `dadianget.py`（versions/run 两命令，--version 参数、按 career_code 幂等、--all 支持全 450 小类，产物带版本号 dadian-careers-<ver>.jsonl；版本探测实测 versionId 1/3/4 树在但职业明细为空，仅 2=2022 版可用——旧版 1999/2015 不在 API，需走 PDF 转载源）（官方权威编码）——初版模型知识整理被联网核对证伪（5 个编码错 3：人工智能工程技术人员实为 2-02-38-01 而非 2-02-10-01、生成式 AI 系统应用员实为 4-04-05-13），已废弃并以 API 提取的官方数据替换（61 个相关小类递归 311 个职业，AI/数据/安全核心 20 个入 YAML 含官方编码/工种数/所属类目），为 46 岗位矩阵提供政策锚点。
- 合成简历真实化（身份要素注入）：genresume 新增真实感信息池（40 中文人名 / 32 所按 AI 岗分布分层的大学 / 34 家公司覆盖大厂-AI独角兽-中厂-外企 / 11 项真实竞赛 / 8 类证书 / 10 城市），按画像级别抽取身份要素（seed 可复现：senior 三段公司序列、junior 实习），prompt 要求原样使用真实名称禁止"某某/XX"占位；重生成 24 份 diverse 简历（旧版备份 md-v2/，占位检查 0 命中，样例：南京邮电大学+虾皮→MiniMax+ACM-ICPC 铜奖），md2res 转四版式 96 份，清理旧 imported 档案 191 条后重新导入 72 条（同文件名幂等跳过问题以清旧重导解决）。
- 数据全景工作区（`/data`）：AppShell 扩展 Workspace 三元（招聘 / 成长 / 数据）+ localStorage 兼容；`/data` 入口五段叙事（数据来源 / 处理流水线 / 时间情报 / 服务对象）+ 三个钻取子页（`/data/sources` 来源、`/data/pipeline` 流水线、`/data/quality` 质量）；H1 改叙述式"从原始素材到两个用户界面"，KPI 卡主次优先级区分（主 2 列宽 + sparkline 占位 / 次 1 列宽），错误分布顶部红色 annotation，服务对象改独立 CTA 按钮；复用 paper / ink / saffron 既有色板，未引入新色。
- Pipeline run 列表 API（`GET /api/v1/pipeline-runs?limit=50&since_days=7`）：扫描 `data/runs/<run_id>/events.jsonl` 聚合最近运行（默认 7 天 / 50 条），返回 run_id / component / status / duration / count_summary 等字段；只读不写库，HR / 评委视角。
- `make dev` / `make stop` / `make dev-logs` 一键工具：`make dev` 后台启动 API (8000) + Web (3000) 并写入 `.run/{api,web}.pid`，幂等检查避免重复启动；`make stop` 关闭两服务并兜底清理 pnpm 派生的 next-server 残留；`make dev-logs` 实时跟踪两份日志。前端默认连真实 API（`NEXT_PUBLIC_USE_MOCK=false`）。

### Fixed
- 工作台加载失败（错误编号/digest，页面停在 error 边界）：根因是 `GET /api/v1/dashboard/overview` 耗时 ~17s 超过前端 10s 超时。`ApplicationService` 组装岗位变化时为 13 项 changes 每条重建 14,173 行证据索引、为 32 条证据每条重扫全量 `jd_records`（85.9 万次 JSON 解析）；改为请求内一次索引 + 联查表实例级缓存，17s → 2.3s，`/` 恢复 200（~2.9s）。
- `apps/web/app/data/page.tsx` 与 `apps/web/app/data/pipeline/page.tsx` 调用 `apiFetch` 时重复拼接 `/api/v1`，因 `NEXT_PUBLIC_API_BASE_URL` 已含该前缀，请求变成 `/api/v1/api/v1/pipeline-runs` 触发 404；改为相对路径 `/pipeline-runs` 后 `/data` 与 `/data/pipeline` 在真实数据模式下正常加载。
- 数据驱动演化闭环到前端：新增 `GET /jobs/detected-changes`（快照 Diff 变化草稿，16 岗位 139 项）与 `GET /temporal/timeline`（四层时间轴 18 域）两端点（backend/application/insights.py VM）；`/positions` 页新增"系统检测到的岗位变化"区块（岗位卡片 + top3 变化标签 base%→obs%，按 add/grow 蓝标与 shrink 灰标区分）；`/temporal/timeline` 新子页四层传导表（论文→PyPI→npm→日报→JD→论文到 JD 月数）+ temporal 首页导航卡；mock 模式分别给示例与管线说明占位。
- arXiv 论文信号采集与四层时间轴验证（`scripts/arxivget.py` + `arxiv` 来源登记）：export.arxiv.org 公开 API 按 13 个技能关键词 x 2015~2026 拉取 14,830 篇预印本 metadata（幂等 arxiv_id，3.2s 限速，词x年粒度 runlog），词典归一聚合为月 x 能力域序列；与 relsignal 的包/日报/JD 三层并排首次完成六大新兴域四层传导验证——LLM应用 论文2020-01→包2023-02→日报2024-01→JD2025-10（全程70个月）、AI Agent 81 个月、RAG 79 个月（论文2019-05→JD 跨 6.5 年）、Prompt 工程 26 个月速通（实践先于学术化的反例）；结论：论文到岗位需求的完整传导约 5~7 年，其中论文→包 1~3 年、包→传播→JD 2~4 年。
- 快照 Diff 检测器（`scripts/snapshotdiff.py`）：任意两 JD 池（archive/corp/snapshots 日期）按岗位分组对比技能份额，自动产出岗位级 JobChangeSet 草稿（add/remove/grow/shrink + 证据提及计数，阈值 min_jds=8/delta=2%/presence=0.5%）；首版跨年 diff（Wayback 历史池 4089 JD vs 现行池 4219 JD）检出 16 岗位 139 项变化，AI 产品经理的演化与手工五年对比一致且落到岗位粒度（AI Agent 要求 10.0%→20.6% grow、RAG 2.4%→5.7% grow、大数据处理 20.6%→7.6% shrink）——快照机制从存档升级为岗位演化引擎，changeset 审核后可喂 jobver 升版。
- leadtime 接入历史 JD 窗口并修正先导口径：JD 源从仅 51job 扩为 51job/字节/腾讯（含 Wayback 历史池，观测窗起点 2025-09→2018-07）；跨期数据揭示原"12/13 域领先、中位 214 天"是窗口截断伪影——历史 JD 证明 12/13 域需求早已存在（新增 jd_preceded 分类：多为存量技能、事件侧早期覆盖薄或词典语义漂移），从统计排除；可证先导仅 ML/DL算法 1 域（信号 2017-07→JD 2018-07，+365 天，深度学习研究热→工业化招聘的真实跨期例证）；caveats 口径写入产物 params。
- 词典新词核对与修正：逐条审查首批合入词，撤 10 个错配（Java/JS/Go/PHP/Node.js 等编程语言被归入 cap_07"Python"域会扭曲岗位画像——Java 岗 Python 权重虚高；Typescript 大小写双写跨域；CPU 歧义）并修正 ISO 27001 归属（法规域→安全/风控域），终态 72 词；核对代价命中率 27.4%→25.6%（换 Python 域纯净）；三项下游验证——英文岗位 resolved 重归一模拟 1.0→1.6、五年演化结论在新词典下四大崛起域与大数据收缩方向全部一致（幅度略小，结论不依赖词典版本，稳健）。
- JD 侧词典新词消化（首批）：skillmap 支持 `--input` 词单路径与并发 15，JD 未命中词统计（89225 提及 / 词典命中仅 19.9% / 去重 22577 词）生成高频词单（count>=20 共 422 词覆盖 25489 次提及，样例上下文取自 JD 正文）；LLM 归派 388 候选（skill-alias prompt v1）——高置信（≥0.9）82 词自动合入 SKILLS-EARNED v4（Java/GCP/Azure/Spark/LLMs/MLOps/TensorFlow 等，effective_from 2026-08-28 尊重时间闸门）、中置信 116 词留 alias-candidates.jsonl 人工复核、噪声 187 词拒绝（产品/公司名）；词典生效后全池命中率 19.9%→27.4%（英文 18.7%），快照循环的新解析自动受益，存量 resolved 重归一为可选后续。
- JD 快照接入应用生命周期（`backend/application/snapshot.py`）：`HIRO2_SNAPSHOT_ENABLED=true` 时 API 启动 60s 后自动进入周期后台循环——每轮 jdcorp runall（8 站增量，缓存命中秒级跳过）→ 当期文件归档 `snapshots/YYYY-MM-DD/`（一天一份，与 Wayback 历史无缝衔接）→ jdxtract + rolemap 增量解析映射（`HIRO2_SNAPSHOT_ANALYZE` 可关）；CLI 走独立子进程（超时保护，失败不拖垮 API），compose 默认开启、本地默认关闭；实测一轮 62 秒（腾讯捕获 13 个新岗位、其余站 0 新增秒过）；Dockerfile.api 安装 chromium headless 依赖，快照域单测 2 例（开关、同日归档不覆盖）。
- Wayback 历史 JD 回溯（`scripts/jdarchive.py`，jd-archive 来源）：CDX 枚举字节/腾讯/Greenhouse 招聘 API 的全部 200 快照逐份拉取（id_ 原始响应 + gzip 解压，1.2s 限速，断点续跑），13071 条历史记录 / 4148 个去重岗位（观测时间 2022~2026 五年连续），记录带 snapshot_ts 锚点、jdxtract 按 jd_id 首见去重（最早观测优先）；解析 4135 条 + rolemap 映射 2424 条后首次实现真历史窗口对比——2022-23（334 条）vs 2025-26（1513 条）：多模态 +6.4%/LLM应用 +6.1%/AI Agent +4.9%/RAG +2.6% 崛起，大数据处理 -10.8%/SQL -2.7%/云计算 -2.3% 收缩，与行业真实演化吻合；放弃源及死因：拉勾快照为反爬响应、阿里 POST 无 body、百度/网易 SPA 壳、华为/51job 无存档——结论为 Wayback 仅 GET 型 JSON API 有可存档响应体。
- 第三方技术信号双生态四轮扩容至终态（`data/PKGS.yml` v9：PyPI 209 包/18 域（cap_04 Agent 域 37 包）+ npm 24 包/5 域 + `scripts/pypidl.py` fetch/rels/ch/hist/npm/pepy/run + `pypi-pkgstats` 来源登记）：实测通路——pypistats 全端点仅 180 天、GitHub stargazers 端点 2026-06-30 起仅限管理员（star 时序不可得）、萌芽信号用 pypi.org JSON API 全版本 upload_time；三层时间轴成立（包首发 → 日报传播 → JD 采用，AI 域首发到 JD 中位 670~1796 天 vs 日报领先 243 天），leadtime 解释力取决于信号锚定的生命周期阶段。补包三层依据：JD 高频技能原词反查（Databricks 250 次/Kafka 116/Lakehouse 89）→ hugovk top-15000 下载 dump 域词根扫描（+30 增长型包：browser-use 5300 万/月、ollama、sglang、tokenizers、mem0ai、firecrawl-py、deepeval 等）→ 人工剔除主包拆包与传递依赖；npm downloads API 2015 起全历史落地（段级 404 容忍 + 429 指数退避），npm 份额 onset 领先 JD 中位 304 天与日报同量级、Agent 域 npm 采用与 JD 几乎同步（JS 侧起量晚于 LLM SDK）；BigQuery 额度事件（三次真实测试查询烧尽当月免费额度、切账号实测不可绕过）后调研出主通路：**ClickHouse 官方 Playground `pypi_downloads_per_month`**（demo 免费、2016-01 起 127 个月一条 SQL 拉取、与 BigQuery 口径逐位交叉验证一致），BigQuery 降级为备份；pepy.tech 90 天滚动通路（.env key、429 退避、嵌套 downloads 适配）覆盖 2026-05~08。历史化 JD 基线的四侧对比已出：成熟域下载份额领先 JD 中位 1886 天（可信），AI 域读数受词典回望/语义漂移/小样本阈值三个混杂标注不可引用（修复方向：JD 历史重解析带 as_of + onset 阈值按池规模归一）。扩容四轮方法链归档于 PKGS.yml 头注：v7 中文 AI 生态 +28（dashscope/modelscope/qwen-agent/flagembedding/paddlepaddle 等，xinference 官方下载近零实证镜像低估）；v8 gh search 14 个 AI topic +10（opik 285 万/月、ocrmypdf、whisperx、scrapling、open-webui、funasr 等）；v9 agent 域专项 15 topic 宽检索 +11（pipecat 121 万、graphiti-core 110 万、agentscope 67 万、kedro、langflow 153k★、metagpt 等，cap_04 达 37 包）；star/下载差集分类法沉淀：被低估包（加）vs git-clone 型（GPT-SoVITS/storm 等 pip 月下载 <3000，不加）。

- JD 扩采全链路落地并兑现薄证据岗位升版：解析 corp 4167 条（并发 4→15 后 41 条/分钟，实测校准预估方法论）、rolemap 增量映射 3225 条（exact/alias/llm/unmatched = 107/684/1962/738）；46 岗位覆盖 43 个、≥15 条岗位从 6 → 21 个（大数据 4→334、数据分析师 5→158、数据安全 3→95、数据中心运维 5→31、AI训练师 6→25；智能传感器 4→7 仍薄）；`jobver --version 3` 支持对已发布 v2 的扩采复核（changeset_vs_v2 语义：新市场 top10 对比 v2 必备/加分，add/promote/demote），发布 5 个 v3 版本（bigdata/data-analyst/data-sec/dc-ops/ai-trainer），Neo4j 投影 17/17 可查；质量核对：中英技能原词抽取均好（13.8/10.5 每岗），英文词典归一短板（resolved 1.1 vs 4.8）归入新词消化任务。
- 企业官方招聘站采集器 `jdcorp`（8 源 4248 条 JD）：字节/阿里/腾讯/美团/小红书/vivo 国内 6 厂（Playwright 拦截同源 XHR 或纯 HTTP，全部带职责/要求正文，7 成带真实发布时间）+ Anthropic 与 Greenhouse 通用 board adapter（Together AI/Scale/Databricks/Pinterest/Figma/Discord/Stripe/Duolingo 8 板块纯 HTTP 全量）；关键词级 7 天增量缓存（首屏无新增跳过整词）、`--keywords all` 全岗位池模式（不过度倾向技术岗）、`runall` 8 站并行；`jdxtract` 接入 corp 第四源自动合并解析，`SOURCES.yml` 登记 jd-corp 来源与限速纪律。放弃名单及原因：华为 404、百度 headless 反爬、快手登录墙、OpenAI 网络不通、DeepSeek SSR 内嵌且岗位量个位数、MiniMax careers 无职位数据、荣耀/蚂蚁/小米/B站连接层拒绝。
- 简历档案审阅工作区：左侧去重档案列表，右侧当前文件审阅；支持 PDF 内嵌预览、DOCX 内容预览、TXT/MD 文本预览，以及文档预览与结构化档案 Tab 切换。
- 简历档案批量解析：新增 `resparse` 命令，将已入档未解析的 PDF/DOCX/TXT/MD 逐份接入现有抽取与归一管线，更新结构化职业档案并保留失败记录。
- 简历档案结构化升级：解析结果按职业摘要、工作经历、项目与能力证明、技能匹配、教育与补充信息、原始简历排序；解析 Schema 扩展经历、教育、城市、证书、作品链接和语言字段，内部能力 ID 改为“已识别/待确认”。
- 简历档案持久化与可视化：新增 `backend/candidates/archive.py`（文件落 `data/objects/resumes/`、元数据与画像追加 `resume-archive.jsonl`，离线优先文件为权威）；`POST /candidates/resumes` 解析成功自动入档，新增 `GET /candidates/resumes`（轻字段列表）与 `GET /candidates/resumes/{id}`（详情）；`resumeimport` CLI 一次性导入 resumes-div 测试集 72 份（过滤 -2col 版式变体，imported 不解析、重复文件名幂等跳过）；`/resumes` 页新增档案网格（文件名/日期/大小/来源/技能与归一摘要），点已解析档案回看画像，上传成功即时置顶入档；档案域单测 2 例（入档往返、导入幂等）。
- 简历解析体验升级：新增上传后文件预览、多文件处理队列、单份解析与批量解析入口，逐份保留待解析/解析中/完成/失败状态。
- 工作区切换：顶部新增“招聘 / 成长”分段切换，按角色切换首页、导航和工作区上下文，并记住最近选择。
- 前后端断链补全六项（roadmap 前端 26/26 完成）：①发布流实装 `POST /jobs/{id}/versions/{version}/publish`（审核留痕 + 复用 jobpub 固化，重复发布幂等返回，TestClient 验证）；②新岗位候选接受/拒绝接 `POST /emerging-jobs/{id}/review`（留痕失败时前端不更新状态并提示）；③`/temporal/signals`、`/temporal/suggestions` 改走 `/temporal/dataset`（与 forecasts/retrospect 一致，真实 signals 500 条）；④证据抽屉无来源链接时提供「查看全文」（fullText 已在 VM）；⑤发布成功视图接入 `GET /jobs/{id}/training-output`（JD 模板 + 学练赛证培养任务 + 证明要求）；⑥新增 `/resumes` 解析确认页（上传 FormData → `POST /candidates/resumes` 90s 超时 → 归一结果可修正 + 原文片段，确认为会话内闭环）；`apiFetch` 支持 FormData，主案例 draft version_id 规范化为 `ai-agent-v2-draft-{date}`。
- 数据库事实主库推进：诊断、时间情报和 ApplicationService 的证据/JD/事件读取在配置 PostgreSQL 时优先走数据库；新增画像版本、当前目标、时间信号、回测、预测和岗位影响建议 schema，导入岗位版本自动写入 outbox，`make graph-sync` 幂等投影 Neo4j。
- PostgreSQL 集成完善：新增 `dbmigr` 幂等迁移执行器、`make db-up/db-migrate/db-import` 命令，并将求职成长 migration 纳入 Compose 初始化与升级路径。
- 求职成长界面打磨：移除重复眉题和重复入口，统一能力证明术语；画像页补充目标岗位上下文并修正标题对齐，求职模式导航仅保留诊断、成长和画像入口。
- 求职成长工作区扩展：首页与我的画像独立入口，支持目标岗位切换、画像编辑、成长任务与能力证明关联。
- 求职成长闭环扩展：诊断页支持成长任务持久化和能力证明录入；新增个人目标、成长任务、证明 PostgreSQL migration 与 API，未配置数据库时明确返回不可持久化状态。
- 求职成长工作区第一版：人岗诊断重构为“目标岗位 → 投递基础 → 优先补齐 → 学练证成长计划”主线；计划支持会话内完成标记，仍只消费已发布岗位版本与候选人画像，不暴露审核与内部运行信息。
- 信号流接入真实数据（D6 TrendSignal 落地）：sigbuild 确定性生成提及级 TrendSignal（events 主记录 × 归一映射，6755 条/24 能力域，cap_04 AI Agent 2027 次居首，confidence 沿用事实分级映射，evidence_id 直回链 ev:{event_id}）；daily 增至七步（+sigbuild）；`/api/v1/temporal/dataset` signals 从空数组变为近 90 天 500 条；前端 `/temporal/signals` 从 mock 25 条切真实（近 90 天 ≤500 条），头部新增"最近信号"新鲜度指示。AI Agent 信号第一的既有结论在多源数据下复现。
- 时间情报每日闭环（daily 编排 + RSS 事件化）：extract 新增 feeds 通道（FeedItem 剥 HTML 后复用 report-event prompt 进同一 events 池，幂等键 content_hash，--days 控制增量窗口，<150 字纯标题条目跳过）；daily.py 编排 fetch→日报增量→feeds 增量→resolve→evdedup→evidence 六步（单步失败不阻塞）。整链实测：110 条近 7 天条目产出 522 事件（隔离 5），事件池 8350→9068；跨源重复 23.8% 被 evdedup 标记（多源报道同一新闻的去重价值直接体现）；evidence 重建 7219 条；词典加权覆盖 87.2%→60.3%（英文提及未命中进新词队列 3735 个，为词典习得原料）。存量 2700 条历史条目可 `extract.py feeds` 全量回填。
- 打通 RSS 直连采集：feedtest 逐个测试 rss2cubox feeds.txt [direct] 段 140 个真直连源（116 可用，按优先级分组报告）；精选 24 源生成 `data/FEEDS.yml`（p5/p4 全量 10 + p2 精选 15，剔除与 openai-news 完全同 feed 的 openai-blog）；新增 `rssget` 抓取器（feedparser，guid 幂等追加、并发 8、失败源不阻塞），首轮 24/24 成功落 `data/raw/feeds/` 2718 条 FeedItem（published 2015-12~2026-08），复跑 0 新增验证幂等；SOURCES.yml 登记 `feeds`（live 模式）。
- 采集与简历抽取域逻辑归位（AGENTS 分层惯例）：RSS 抓取/幂等落盘移入 `backend/temporal/feed.py`（Pydantic FeedItem + 不联网单测 3 例），`rssget` 变 CLI 壳；`candmatch._extract` 移入 `backend/candidates/parse.py` 为 `extract_resume` 域入口（消除 scripts 跨脚本 import），candmatch/reseval 改调域模块；feedparser 缺类型桩按 mypy overrides 豁免。50 测试全过。

### Fixed
- 收敛简历档案列表：主列表只展示 PDF/DOCX 可预览版本，隐藏 TXT/MD 和重复文件元信息；PDF 使用红色格式标记、DOCX 使用蓝色，已解析状态为绿色、未解析为灰色。
- 五项质量债清零（`make verify` 全绿恢复）：mypy 5 错误修复（psycopg fetchone 判空兜底、dashboard 类型注解）；删除 CHANGELOG 重复的 RSS 条目；发布端点补幂等回归测试（重复发布 200 / 未知草稿 404）；`Dockerfile.api` CMD 启动前幂等执行 `dbmigr`（托管 PG 无 initdb 挂载）、`Dockerfile.web` API 地址改 build-arg 注入（Railway 适配）；e2e 恢复密闭性——独立端口 3100 + 独立 distDir + 强制 mock（不受 `apps/web/.env` real 模式与 8000 API 新旧影响，绕开 Next dev 单实例锁），jobs/skills spec 对齐双 Tab 图谱新 UI 与 GSAP 动画（dispatchEvent 点击）；修复 `dashboard.css` 截断的未闭合 @media、`resume-parse-workbench` useState 声明顺序、`genresume.py` 超长行，`.next-e2e` 产物入 eslint/prettier/git 忽略。
- 修正招聘侧候选诊断上下文：招聘模式不再显示求职成长、学习计划或求职者证明提示；简历解析上传区扩展为主内容宽度。
- 统一诊断工作区操作对齐：重新计算与编辑画像归入标题行右侧操作组，打开证据移至说明标题行；学习计划编号固定窄列并与内容基线对齐。
- 优化能力图谱与加载反馈：移除前端暴露的 `cap_XX` 内部能力 ID；各路由加载态改为匹配首页、Diff、图谱、诊断和评测实际结构的专属骨架；接入 GSAP 为路由切换和图谱重排提供轻量过渡，并完整支持减少动态效果偏好。
- 修复 `.env.example` 存储段变量名与代码不一致：`HIRO2_DATABASE_URL`/`HIRO2_NEO4J_*` 改为代码实际读取的 `DATABASE_URL`/`NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`（原配置照抄必连不上库），默认值对齐 docker-compose，删除重复定义的 Phase B 段。
- 简历抽取三处修复并回归验证（96 次调用 0 失败）：candmatch 对超限 skills/projects 截断而非整单拒绝（long 简历 >40 条曾触发 ValidationError）；resume-parse prompt 升 v2（技能定义纳入能力域词、密集列举逐项拆出）；reseval 宽松核心词匹配成为主指标（gold 侧短词仍全等防误报）。宽松口径召回 91.8% -> 96.5%（variant 63.6%->97.8%、typo 78.3%->89.1%、buried 99%、双栏 96.5%），严格口径 82.7% -> 86.1%。

### Added
- 技能图谱节点详情接入关联岗位版本与市场信号（原 F-T3.5 占位块）：`/api/v1/skills/graph` 每个节点聚合 `jobVersions`（扫全部 published 版本的必备/加分引用，按权重降序）与 `signal`（jd-parsed 提及数 + 占比），前端 `skill-node-detail` 替换占位块渲染；Neo4j 分支改为仅校准 role、保留 VM 节点的别名/位置/关联字段（原实现裸覆盖会丢字段）；mock fixture 补示例数据。
- 岗位版本管线参数化并批量发布 11 个岗位版本：`jobver.py run --job <position_id> --slug <前缀>` 将主案例精做脚本泛化为任意岗位管线（市场统计与 changeset 规则提取共用，pos_02 回归逐项一致）；按 JD 浓度发布 v2 版本——llm-algo（大模型算法，65 JD）、ai-pm（22）、nlp-mm/cv（各 17）、mlops（10）等，JD<10 的薄证据岗位（ai-trainer/bigdata/data-sec 等 6 个）在审核留痕中标注"方向性，扩采后升版复核"；全部经 review-action 留痕 + jobpub 不可变发布 + Neo4j 投影（12 版本含 ai-agent-v2 皆可查），`/skills/graph?job=<version_id>` 生效。
- 新增简历抽取回归（reseval）：24 份 × 4 版式全管线（解析→LLM 抽取→gold 宽松比对）双口径报告。结论：解析层无瓶颈（双栏 94.2% 召回反而最高，PyMuPDF 无需替换）；严格口径 82.7%、宽松核心词口径 91.8%，差距主要来自 gold 埋点写法（版本号/括号注释）而非漏抽；真实缺口三类——能力域词（工具调用/数据仓库/向量数据库）系统性不抽、密集列举漏抽、技能超 40 条时 ResumeRawExtraction 校验整单失败。
- 新增多样性合成简历批次（genresume diverse）：7 类边缘画像（写法变体/技能稀疏/技能埋项目/软技能噪声/管理向/全半角噪声/超长）× 方向级别共 24 份 Markdown 源，生成时埋点 171 个 gold 技能提及（落盘前校验与正文逐字对齐）；新增 md2res 转换器（pandoc + PyMuPDF Story）把 Markdown 统一转为 pdf 单栏/双栏、docx、txt 四版式，内容与版式解耦。冒烟确认双栏 PDF 经现有解析器出现词内断行（Ｐｙｔｈｏｎ 被栏宽切断），为解析层升级（MinerU）提供依据；synthetic 依规则不进入官方指标。
- 新增企业招聘工作区与求职成长工作区设计文档，明确角色入口、首屏信息层级、主流程、权限边界和验收标准。
- PostgreSQL 事实源切换：质量看板优先读取 `review_tasks/review_actions`，`dbimport` 导入冻结评测任务；新增 `outbox_events` 表、幂等事件写入器与 `scripts/outbox.py`。
- outbox 增加 `consume` 投影消费者：使用 `FOR UPDATE SKIP LOCKED` 领取事件，成功/失败状态可追踪，`JobVersionPublished` 幂等写入 Neo4j。
- 健康检查拆分为 `/health/live` 与 `/health/ready`；质量 fixture 改用 manifest/metrics 结构化数据；新增审核质量字段 migration；技能图谱 API 支持 Neo4j 查询并在不可用时回退文件图谱。
- 完成交付基础设施：Docker Compose（PostgreSQL/Neo4j/API/Web）与依赖健康检查、真实质量看板 API（评测任务/审核动作聚合）、Neo4j 幂等图谱投影及 `quality.py` 五道质量门统一 JSON 报告；38 个 Python 测试覆盖率 65.12%，`make check` 强制 coverage>=60%。
- 简历双层归一（词典 + LLM 归层，置信度门槛与 reason 留痕）：20 份合成简历 99% 综合归一率；genresume 按方向×级别矩阵生成 20 份测试简历（txt/pdf/docx），批量匹配 overall 0.2~0.94 方向区分度清晰。
- 完成主案例 3 人岗诊断（candmatch/candidates/matching）：文档解析适配器 + LLM 简历抽取 + 确定性四档匹配引擎 + 学练赛证路径；岗位版本发布流程（jobpub 审核留痕校验 + 不可变发布）；修复 resolver 空格变体 bug，词典 v6。
- D9 评测集骨架（evalset）：三层冻结样本（映射 100/领域 50/事件 30，分层+哈希+种子）与回流评分脚本。
- 岗位版本组装（jobver）：AI Agent 工程师 JobVersion v2 草稿（必备/加分技能+56 证据 JD+点级 changeset）与两窗口 JobChangeSet；修正份额换算量纲错误，改用群内排名规则，结论为专家基线域级一致、点级细化 8 项。
- 完成主案例 1（newjob）：AI Agent 工程师新岗位发现的五路确定性证据（涌现/技能组合独立性/跨公司扩散/信号先行/定义卡草稿）。
- 增加提前量验证（leadtime）：事件研究法测量日报信号领先 JD 需求的天数，12/13 能力领先、中位 214 天；自带左删失可信度分级（clean/lower_bound）与成熟技能反例对照（Python -242 天）。
- 增加 D3 岗位目录映射（rolemap）：规则精确/别名匹配 + LLM 语义候选（251/266 映射到 Excel 46 岗位，带置信度理由）+ L1-L4 确定性等级推断 + 人工标注包 review-labels.csv；测试抓出并修复 MLOps 死别名。
- 增加 JD 两窗口 diff 引擎（jddiff）：按窗口聚合能力域份额，输出新增/消失/增强/减弱及证据 JD；v1 结果 LLM 应用份额翻倍（5.9%->12.9%）、模型微调需求涌现（0->14 次），基准窗详情补齐后更新终版。
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

- 完成 F-T4.10/4.11/4.12 审核与质量看板：2 个新页面 `/tasks`、`/quality` + dashboard 加 2 张跳转卡：
  * `/tasks` 一页 = 左 1/3 任务列表（F-T4.10）+ 右 2/3 工作区（F-T4.11），含 5 条 mock 任务（3 forecast_review + 2 job_review，2 条标记「需双审」），任务支持领取 → 审核中 → 提交 → 完成 4 状态机；右侧工作区按「系统结果 / 证据 / 人工决策」三段，决策按钮复用 `ReviewActions` 已有 onAccept/onModify/onReject
  * `/quality` F-T4.12 看板：4 stat-card（任务完成率 80% / 双人复核率 67% / 平均响应 3.2d / 已解决 12）+ 6 类错误分布条 + 3 horizon Run 对比（A / B 双 Select）
  * `lib/tasks-fixture.ts` DTO 严格照 `contracts.md:283-310`（8 task_type / 6 状态 / 4 decision），mock 数据复用 `temporal-fixture.ts` forecasts + `data/fixtures/job_update.json` changes
  * 不扩 `review-ui.tsx` 的 4 态 ReviewStatus 枚举——避免影响 `job-update-workbench` 既有行为；任务用 task 自己的 status 字段 + Tag 着色
  * `app/quality/page.tsx` 是 RSC + 调 `loadTemporalFixture()` + 把 `temporal` 数据传给 client `QualityWorkbench`（避免 client bundle 拉 `node:fs`）
  * `globals.css` 加 ~180 行 `.tasks-*` 与 `.quality-*` 样式（含 1180px 响应式断点）
  * 一级导航仍 6 项不变（`/tasks`、`/quality` 仅作次级路由），dashboard 加 `dashboard-temporal-grid` 横排 2 张跳转卡（我的任务 / 质量看板）
  * 10 个 e2e 用例 regression 全过

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

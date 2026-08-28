# 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的记录方式，并使用语义化提交信息。

## [Unreleased]

### Changed
- Railway 部署适配：API/Web 使用平台动态端口，CORS 与简历档案路径支持环境变量，生产镜像排除本地密钥和原始文件。
- 新增内部质量模式的数据资产工作区，展示数据域规模、质量、版本和可重建流转链路。

### Added
- JD 侧词典新词消化（首批）：skillmap 支持 `--input` 词单路径与并发 15，JD 未命中词统计（89225 提及 / 词典命中仅 19.9% / 去重 22577 词）生成高频词单（count>=20 共 422 词覆盖 25489 次提及，样例上下文取自 JD 正文）；LLM 归派 388 候选（skill-alias prompt v1）——高置信（≥0.9）82 词自动合入 SKILLS-EARNED v4（Java/GCP/Azure/Spark/LLMs/MLOps/TensorFlow 等，effective_from 2026-08-28 尊重时间闸门）、中置信 116 词留 alias-candidates.jsonl 人工复核、噪声 187 词拒绝（产品/公司名）；词典生效后全池命中率 19.9%→27.4%（英文 18.7%），快照循环的新解析自动受益，存量 resolved 重归一为可选后续。
- JD 快照接入应用生命周期（`backend/application/snapshot.py`）：`HIRO2_SNAPSHOT_ENABLED=true` 时 API 启动 60s 后自动进入周期后台循环——每轮 jdcorp runall（8 站增量，缓存命中秒级跳过）→ 当期文件归档 `snapshots/YYYY-MM-DD/`（一天一份，与 Wayback 历史无缝衔接）→ jdxtract + rolemap 增量解析映射（`HIRO2_SNAPSHOT_ANALYZE` 可关）；CLI 走独立子进程（超时保护，失败不拖垮 API），compose 默认开启、本地默认关闭；实测一轮 62 秒（腾讯捕获 13 个新岗位、其余站 0 新增秒过）；Dockerfile.api 安装 chromium headless 依赖，快照域单测 2 例（开关、同日归档不覆盖）。
- Wayback 历史 JD 回溯（`scripts/jdarchive.py`，jd-archive 来源）：CDX 枚举字节/腾讯/Greenhouse 招聘 API 的全部 200 快照逐份拉取（id_ 原始响应 + gzip 解压，1.2s 限速，断点续跑），13071 条历史记录 / 4148 个去重岗位（观测时间 2022~2026 五年连续），记录带 snapshot_ts 锚点、jdxtract 按 jd_id 首见去重（最早观测优先）；解析 4135 条 + rolemap 映射 2424 条后首次实现真历史窗口对比——2022-23（334 条）vs 2025-26（1513 条）：多模态 +6.4%/LLM应用 +6.1%/AI Agent +4.9%/RAG +2.6% 崛起，大数据处理 -10.8%/SQL -2.7%/云计算 -2.3% 收缩，与行业真实演化吻合；放弃源及死因：拉勾快照为反爬响应、阿里 POST 无 body、百度/网易 SPA 壳、华为/51job 无存档——结论为 Wayback 仅 GET 型 JSON API 有可存档响应体。
- 第三方技术信号冒烟（`data/PKGS.yml` 32 包 -> 14 能力域 + `scripts/pypidl.py` fetch/rels/run + `pypi-pkgstats` 来源登记）：实测通路三则——pypistats 全端点仅 180 天（PyPI 下载历史无 key 通路不存在）、GitHub stargazers 端点 2026-06-30 起仅限管理员（star 时序不可得）、现行萌芽信号用 pypi.org JSON API 全版本 upload_time；三层时间轴成立（包首发 → 日报传播 → JD 采用，AI 域首发到 JD 中位 670~1796 天 vs 日报领先 243 天），leadtime 解释力取决于信号锚定的生命周期阶段。
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

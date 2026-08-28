# 数据 Roadmap

> 范围：Excel 能力矩阵、职业标准、招聘 JD、日报 RSS、技能本体、岗位阶梯、证据链、时间快照和评测数据。
> 原则：原始数据不覆盖，处理结果可重建，正式结论必须有证据和审核。
> 当前阶段：数据主线完成，D2 去重 / D7 证据实体 / D9 评测集与人工标注待做（2026-08-25 审计）。
> 状态只使用：未开始、进行中、阻塞、待验收、完成。

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

数据资产版本登记已接入 PostgreSQL（迁移 `0007_dataset_versions.sql`）。本地处理产物通过 `dbimport` 写入 `dataset_id`、`dataset_version`、记录数、有效数、质量分、manifest 哈希和 `run_id`；数据资产 API 线上优先读取最新登记快照。

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

状态：部分完成（隐式于 ingest/jdclean/extract 的时间戳修复、隔离队列与坏值标记；未做专项遍历）。JSONL 无编码/列名问题，实际缺口已被后续阶段吸收。

处理编码、空值、列名、日期、HTML/Markdown 噪声、损坏文件、非法 URL 和文件哈希。原始记录不覆盖，清洗结果可从 raw 重建，失败记录进入隔离队列。

### D2 身份与重复清洗

完成（2026-08-25，`scripts/evdedup.py`）：同日 + 标题相似（归一化精确/包含/二元组 Jaccard>=0.55）+ 实体重合，并查集聚类；**2017/8350（24.2%）为速览/正文重复**（2026-02 前仅 3 条，验证为结构性重复非误杀）。全部事件保留原文，仅标记 duplicate_group_id/is_primary/duplicate_reason；resolve/leadtime/newjob/backtest 四个下游已改为只消费主记录。
去重后结论复验：提及 12605->10274，中高频覆盖 85.2%->**87.2%**（重复长尾消除）；提前量中位 214 天不变（12/12 领先、clean 案例不变）；Agent 信号 2328->1816；回测 v1 36.8% vs 基线 44.9%（仍输，结论不变）——**全部核心结论稳健**。

处理 URL、GUID、内容哈希、标题/公司/时间相似度、转载和模板 JD。输出 `canonical_record_id`、`duplicate_group_id`、`is_primary` 和 `duplicate_reason`。重复记录保留原文，只标记主记录和关系。

### D3 岗位目录与岗位阶梯

状态：待验收（映射完成，退出条件需 >=100 条人工标注，0/100）。

映射完成（2026-08-25）：`scripts/rolemap.py` + `prompts/role-map.yml` + `backend/jobs` 模块。266 条 AI 域 JD：精确/别名规则匹配 83 条 + LLM 语义候选 168 条（带置信度与理由）= 251/266（94%）映射到 Excel 46 岗位，15 条真歧义 unmatched（管培生/技术支持等）。等级 L1/L2/L3/UNKNOWN = 100/29/35/102（L4 稀缺符合市场；UNKNOWN 集中于 boss"经验不限"）。人工标注包 `review-labels.csv`（266 行，映射+等级双确认列）已生成，待同学标注 >=100 条满足退出条件。

建立：

```text
岗位族 -> 标准岗位 -> 岗位别名 -> 岗位等级
```

等级统一为 `L1 初级 / L2 中级 / L3 高级 / L4 专家或负责人 / UNKNOWN`。判断综合标题、经验、薪资、职责复杂度、架构责任、指导和管理责任；冲突时进入 `REVIEW`。

退出条件：至少 100 条完整 JD 完成岗位和等级人工标注，映射有置信度和证据。

### D4 技能本体与归一化

完成（2026-08-25 验收）：

- 全量 697 篇事件共 12605 次提及；词典三层体系：`data/SKILLS.yml` v5（人工先验：Excel 30 能力 + 技能点 + 别名，含专家短形）+ `data/SKILLS-EARNED.yml` v3（755 个语料习得别名，全部带 `effective_from` 首见日期，其中 665 个经离线归一任务 + 置信度>=0.7 筛选合入）。
- 覆盖率验收（按次加权）：中高频(>=2 次) 85.2%、高频(>=5 次) 94.0%，达标（目标 >=80%）。
- 时间闸门实测：词典随 as_of 正确截断（2025-06 视角 59.8% / 2026-01 视角 70.7% / 当前 85.2%），回测无规则泄漏。
- 离线归一任务：`prompts/skill-alias.yml` + `scripts/skillmap.py batch`，LLM 出候选、置信度筛选、人工抽审后入典；0.6~0.7 临界带 76 词留待细审。
- `backend/skills/resolver.py` 确定性匹配，`resolve --as-of T` 时首见日期晚于 T 的习得别名不参与匹配；`scripts/resolve.py events` 输出逐条映射、分桶覆盖率与带上下文的未命中词单，`dates` 子命令重算首见日期。
- 未命中是新词队列，反复出现的新词经离线归一 + 人工审核进入词典并递增 version。

每个映射保存 `raw_mention`、`canonical_skill_id`、`skill_point_id`、`matched_by`、`rule_version`；JD 侧映射还需 `confidence`、`evidence_ids` 和 `review_status`（D5 起接入）。

Excel 的 30 个能力维度作为初始能力域，技能点继续按需拆出：

```text
RAG/知识库 -> 文档切分 / Embedding / 向量数据库 / Reranking / 检索评测
API开发    -> REST / OpenAPI / 认证 / 权限 / 接口监控
```

### D5 JD 详情与技能证据

状态：待验收（采集与解析完成，退出条件同样需人工标注项）。

Phase 0 完成（2026-08-25）：
- 存量修复：70 条 detail 全部归位（51job title 按 jobId join 搜索层修复、公司四列错位校正、location 拆分；boss 22 条本就干净），产出 `norm-jd.jsonl`。可用 38 条（51job 18 条带日期 + boss 20 条无日期），32 条 desc 不足（51job 反爬空页）。
- 搜索层：1190 -> 1150（去重 40）；带日期的 51job 集中在 2026-03~07（556 条）；**2025 基准窗仅 16 条且无法通过当前搜索补齐**（平台只留存在招职位）——主案例 2 两窗口调整为 基准 2026-03~04 / 观察 2026-06~07，或以 Excel 专家基线为基准。
- 补抓清单：`data/processed/jd-opencli/fetch-plan.md`（P0 AI Agent 工程师 / AI 应用工程师；沿用旧 opencli 管道 KEYWORDS，需在装有 opencli 的机器执行，详情按 2.5 倍冗余）。
- 补抓通路（2026-08-25 打通）：`scripts/jdserve.py`（远程浏览器栈：Xvfb+Chrome/CDP+noVNC）→ 用户 noVNC 登录并手动搜索一次"焐热"WAF 信誉 → `scripts/jdauto.py run/detail` 在同一浏览器内自动抓搜索层与详情（冷浏览器/纯 cookie 注入均被软封锁，实测唯一可行通路）；`scripts/jdlisten.py` 为手动浏览时的被动监听兜底。已抓 6 关键词 115 个去重职位（100% 带发布日期）。
- boss 通路（2026-08-25 打通）：boss 检测任何调试器附着（CDP/devtools/扩展 debugger）即返回空数据或刷新循环；唯一通路 = OpenCLI 扩展仅创建标签页（不附着）+ mitmproxy 网络层截获（`scripts/mitmjd.py`，页面零感知，`__zp_stoken__` 由页面正常计算）。`scripts/jdboss.py run` 已抓 6 关键词 92 条（含明文薪资与 skills 标签，54/90 带技能；无发布日期，仅作标注素材）。jdserve 已集成 mitm 启停。

JD 解析完成（2026-08-25）：`prompts/jd-skill.yml` v2 + `backend/extraction` + `scripts/jdxtract.py`，三源合并 342 条全量解析（337 成功 / 5 隔离），每条含职责、任职要求（[必备]/[加分] 标记）、技能原词、词典归一、以及模型语义领域判定 `is_ai_role + domain_reason`（266 条 AI 域，71 条非 AI 带理由可审计）——**staged 层不丢数据，curated 层按判定过滤**。AI 域技能提及 3536 次，归一命中 37%；高频能力域：ML/DL 205、AI Agent 190、Python 186、LLM 应用 138、RAG 112。51job 扩采后搜索层 386 条（六城覆盖），详情可用 219+（158 条待冷却后续抓）；boss 搜索 92 条、详情可用 85。

数据收口（2026-08-25）：待抓详情 149 条中 79% 为 51job 对冷门关键词的填充结果（智慧城市/AI制药等匹配不到即塞 loosely-related），停止抓取；搜索层记录保留（staged 全量），垃圾在解析层由 is_ai_role 判定拦截。最终干净语料：51job 147 + boss 96 = **243 条 AI 域结构化 JD**。基准窗（03-04 月）样本 ~24 条为平台物理上限（在招职位随时间下架，不可回补），diff 结论标注样本量。教训沉淀：冷门词搜索需标题相关度预筛再花抓取成本。

JD 分为：

```text
SearchIndex    用于发现、去重和详情补抓
DetailEvidence 用于职责、要求、技能和岗位版本
```

只有详情完整、来源和发布时间可信的 JD 才能进入正式岗位分析。退出条件：100～200 条完整 JD 具备职责、任职要求、技能片段、岗位/等级映射和人工标注。

### D6 日报事件与趋势信号

抽取侧完成（2026-08-25）：全量 697 篇 → 8350 个 ReportEvent（隔离 19 篇，2.7%），prompt v3，`published_at` 已全量回填（未索引文章用文件名日期，天粒度）；TrendSignal/SignalCluster 聚合待做（随 D8）。

```text
Markdown -> ReportEvent -> Evidence -> TrendSignal -> SignalCluster
```

事件类型至少包括研究、规范发布、模型发布、开源、产品化、采用、政策和传闻。事实、报道和观点分级保存。

退出条件：日报可按日期重建，事件可回到正文和引用链接，历史回填与实时数据分开。

第三方技术信号冒烟（2026-08-27，`data/PKGS.yml` 32 包 -> 14 能力域 + `scripts/pypidl.py`）：

- 通路实测三则：pypistats 全端点仅近 180 天，PyPI 下载历史无 key 通路不存在（正式版 pepy.tech key 或 BigQuery Linehaul 二选一）；GitHub stargazers 列表端点 2026-06-30 起仅限仓库管理员，star 时序不可得；现行信号 = pypi.org JSON API 全版本 `upload_time`（萌芽锚点，无刷量、as_of 干净）。
- 三层时间轴成立（`data/processed/pypi/relsignal.json`，13 域对齐）：包首发（萌芽）→ 日报信号（传播）→ JD 落地（采用）。AI 域首发到 JD 中位 670~1796 天；老基建域（SQL/运维/云）7~20 年；日报领先 JD 中位 243 天不变。leadtime 的解释力取决于信号锚定的生命周期阶段，单一"领先天数"不可跨信号比较。
- 口径教训归档：下载绝对量阈值被生态通胀证伪（onset 全被拖到 2026 初）；跨仓份额分母被大仓截断扭曲；萌芽锚点用"首发月中位数"。国内 pip 走镜像源，官方下载对中国使用为系统性低估，正式版结论须注明。
- 正式版（2026-08-28）：`data/PKGS.yml` v6 定稿（PyPI 160 包/19 域 + npm 24 包/5 域，npm 份额独立分母不与 PyPI 混算）。补包三层依据：JD 高频英文技能原词反查（Databricks 250 次/Kafka 116/Lakehouse 89 等）→ hugovk top-15000 月度下载 dump 按域词根扫描（发现 ollama/browser-use/sglang/mem0ai/firecrawl 等凭知识遗漏的增长型包，+30）→ 人工剔除主包拆包与传递依赖（langchain-openai 等是传递结构、typing-extensions 等是依赖不是技能）；无词典域的前端技能不进表（limitation 注明）。BigQuery Linehaul 通路打通（项目 hiro2-pypi-research，dry-run 实测 2018 起全历史 324GB，扫描量只随月数增长与包数无关）；**额度事件**：三次真实测试查询各 324GB 将当月免费额度（1TB）烧尽，PyPI 拉数顺延至 9/1 重置后执行（教训：真实查询前只 dry-run、正式查询一次成型）。npm 侧已全量落地：24 包 2015 起月度下载（`npm` 子命令，段级 404 容忍 + 429 退避），**npm 份额 onset 领先 JD 中位 304 天**（3 域有效对齐：LLM应用 304/Agent 31/API开发为 2015 老域无意义），与日报 245 天同量级——开发者采用与媒体传播是可分层的两层信号；cap_04 Agent 域 npm 采用与 JD 几乎同步（JS 侧 Agent 框架 2025 才起量，晚于 LLM SDK），双生态对照价值显现。萌芽信号 18 域已出（v6 中位领先 3044 天，明细留 `pkg_first_releases` 复查）。

### D7 证据质量与融合

状态：部分完成（2026-08-25）。`scripts/evidence.py build` 落地 Evidence 实体层（`data/processed/evidence/evidence.jsonl`，6645 条）：trend_signal 6333（日报主记录，质量=事实分级映射）/ job_requirement 266（AI 域 JD）/ expert_baseline 46（Excel 画像），每条含 source_span 回链与 content_hash；JobVersion 草稿与 JobChangeSet 引用已升级为 evidence_id。
未完成：支持/反证关系标记（claim 与岗位字段的正反关系）、跨源冲突与单一来源热点的统一审核队列。

```text
完整性 -> 时间 -> 去重 -> 交叉验证 -> 幻觉/异常拦截
```

来源职责固定为：Excel/标准提供能力基线，日报提供技术先导信号，JD 提供企业需求验证，简历提供候选人输入。每条证据还需标记它支持的字段/变化、支持或反证关系、时间和质量状态。

退出条件：岗位、技能、趋势和匹配结论均能通过 `evidence_id` 回链原文；正式岗位字段和关键匹配结论的证据覆盖率为 100%；来源冲突、单一来源热点和低置信结论进入审核队列，不能静默聚合为岗位事实。

### 候选人测试集与 AI 归一层（2026-08-25）

- **双层归一**：词典（确定性，岗位/日报侧不变、回测可复现）+ 简历专属 LLM 归层（`prompts/resume-alias.yml`，置信度>=0.6 采纳，每条带 reason 可人工修正）。20 份合成简历实测：658 次提及，词典命中 246（37%）+ LLM 归派 411（63%）+ 未命中 1，**综合归一率 99%**。
- **合成测试集**：`scripts/genresume.py`，LLM 按 方向(6)×级别(3) 矩阵生成 20 份（txt 16 + PyMuPDF 生成 PDF 2 + python-docx 生成 DOCX 2，练解析器），`data/fixtures/resumes/` + manifest，synthetic 标记永不进评测指标。
- **多样性批次（2026-08-26）**：`genresume diverse` 生成 24 份 Markdown 源（7 类边缘画像：写法变体/技能稀疏/技能埋项目/软技能噪声/管理向/全半角噪声/超长），带 171 个生成时埋点 gold 技能提及（供回归比对，不进官方指标）；`scripts/md2res.py`（pandoc + PyMuPDF Story）从 Markdown 统一转出 pdf 单栏/双栏、docx、txt 四版式，内容与版式解耦。双栏冒烟确认 PyMuPDF 存在词内断行与左右栏错序，是解析层升级 MinerU 的直接依据。
- **批量匹配**：20 份画像 vs ai-agent-v2 的 overall 分布 0.2~0.94，方向区分度清晰（Agent/LLM/RAG 方向 senior 0.82~0.94 零短板；算法/大数据方向 0.2~0.46 短板集中在 AI Agent/LLM 应用——跨方向转岗的真实差距信号）。

### 主案例 3：人岗诊断管线（2026-08-25）

`backend/candidates`（PyMuPDF/python-docx 薄适配器 + resume-parse LLM 抽取 + 画像构建）与 `backend/matching`（确定性匹配引擎 match-v1 + 学练赛证路径模板）。前置完成岗位版本发布：`scripts/jobpub.py` 校验审核留痕（review-actions accepted）后固化 `published/ai-agent-v2.json`（hash f0f3fdb4，发布后不可变，幂等保护）。合成简历端到端（candmatch demo，标注 synthetic 不进指标）：10/10 技能归一、overall 0.48、四档判定（已具备/初级部分/点级部分/缺失）、关键短板 = LLM应用 + SQL、6 步学练赛证路径。
过程中修复 resolver 空格变体 bug（"Prompt 工程"≠"Prompt工程"）并升级词典 v6（LangChain/LangGraph/Milvus/FastAPI 等框架别名）。

### 岗位版本组装（2026-08-25，`scripts/jobver.py`）

产品核心对象落地（contracts.md 语义，确定性组装，status=DRAFT/PENDING 待人工审核）：
- `jobversion-agent-draft.json`：AI Agent 工程师 JobVersion v2 草稿。必备/加分技能（市场份额加权）、56 条证据 JD、信号引用；changeset_vs_v1 用群内排名规则（份额与 Excel 0-5 评分不同量纲，直接换算不成立——已修正）：能力域级零变化（专家基线与市场一致），技能点级 8 项 add（工具调用 20 证据/代码生成 14/MCP 10/推理 7/记忆 4）——v2 的真实增量是点级细化。
- `jobchangeset-window-diff.json`：主案例 2 两窗口 diff 归一为 JobChangeSet（13 项带证据 JD，样本量声明）。

### 主案例 1：AI Agent 工程师新岗位发现（2026-08-25，`scripts/newjob.py`）

五路确定性证据（`data/processed/jd-opencli/emerging-agent.json`）：
1 涌现：56 条 JD、44 种标题变体、月度 1->7 增长（2025-12~2026-08，21 条带日期）。
2 组合独立性：技能画像 Agent 31% + LLM 12% + Python 11% + RAG 11%；与最近邻 MLOps 余弦 0.788、大模型算法 0.645——相邻但可区分，非既有岗位换名。
3 跨公司扩散：27 家企业、行业分布电商/软件/AI/游戏（boss 侧元数据）。
4 信号先行：日报 AI Agent 信号总强度 2328（全部能力域第一），2025-03 启动、JD 2025-09 落地（+184 天下界，见 leadtime）。
5 定义卡五要素草稿：职责/必备/加分/行业自 56 条 JD 聚合（短语去重频次），待 LLM 归并润色后进人工审核。

### 提前量验证（2026-08-25，`scripts/leadtime.py`）

事件研究法：13 个能力域，日报"信号启动月" vs JD"需求落地月"（月粒度，两侧同词典口径）。**12/13 信号领先 JD，中位 214 天**；含可信度分级：
- `clean`（信号启动晚于 JD 观测窗起点 2025-09，全程可验证）：自动化运维 +120 天（黄金案例）；Python -242 天（成熟技能 JD 先行，方法有效性的反例对照）。
- `lower_bound`（信号启动早于观测窗，提前量含左删失成分）：RAG 245 / Prompt工程 243 / LLM应用 214 / AI Agent 184 / 模型微调 184 等 10 项——JD 侧落地时间为窗内实测，信号起点到窗起点段不可回验，故为下界。
limitation 已写入产物：词典为当前全量口径（描述性对比，非时间闸门回测）。

### D8 时间快照与历史回测数据

回测基础设施完成（2026-08-25，rule_version=1）：
- `backend/temporal/features.py`：SkillSnapshot 窗口统计（事实分级加权 fact=1.0/report=0.6/opinion=0.3）；`backend/temporal/forecast.py`：确定性方向预测与后验方向；`scripts/backtest.py run`：月度滚动回测，预测侧数据+词典双 as_of 闸门，后验侧全词典度量。
- 结果（H=30/60/90，11/10/9 个封闭 as_of 点）：动量规则 v1 命中率 36.1%/33.6%/34.6%，均低于全平基线 40.3%/43.2%/45.6%。最大错误源 up->down：新闻爆发后均值回归，动量外推不适用。**诚实结论：v1 规则不可用，基础设施可用**；v2 方向（更长平滑窗口、高置信子集弃权）另行迭代并在答辩披露两版对比。

为每个 `as_of_date` 构建：

```text
JobSnapshot(T)
SkillSnapshot(T)
SignalSnapshot(T)
```

只使用 `available_at <= T` 的数据。预测窗口结束后再构建实际结果，不能用当前 Excel 倒推历史 ground truth。

退出条件：至少一个主题完成多时间点滚动回测，输出预测、实际、差异和错误分类。

### D9 评测集与发布

骨架完成（2026-08-25，`scripts/evalset.py`）：`freeze` 冻结三层分层样本（`evaluation/samples/`，manifest 记录哈希与种子，合成数据不进入）——role 岗位映射 100 条（按 method 分层）、domain 领域判定 50 条、event 抽取抽查 30 条；`score` 在人工判定回流后输出各项准确率（指标脚本确定性可复现）。**退出条件待人工标注回流后达成**。

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

- [x] 每个原始文件都有 manifest、哈希、来源和导入模式。（boss/har 通道后补登记）
- [~] 原始、清洗、标准化、正式和实验数据分层保存。（分层在，norm*/curated* 前缀约定仅部分遵循，jd-parsed/events 等为无前缀 staged 产物）
- [x] 岗位族、标准岗位、别名和等级可解释。（rolemap 94%，待人审）
- [x] 技能映射保留原始提及、规范技能、技能点和证据。（mention/skill_id/point_id/event 或 jd 引用）
- [x] JD 和日报都能按时间重建状态。
- [~] 失败、冲突和低置信记录进入审核队列。（各环节有隔离文件，无统一队列）
- [ ] 正式岗位字段、岗位变化和关键匹配结论均能回链具体证据片段；证据区分支持与反证。（D7 未落地）
- [ ] 评测集与调优数据隔离。（D9 未开始）

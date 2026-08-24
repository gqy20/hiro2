# Hiro2 协作规范

> Hiro2 是面向挑战杯 XH-202621 的最终交付项目。本文档只约束 Hiro2，不继承旧 `hiro/AGENTS.md` 的实验性技术偏好。

## 1. 总体原则

- 先完成可验证的岗位能力闭环，再增加预测、Agent 和视觉扩展。
- 代码、数据、文档和评测结果必须可复现。
- 业务事实必须有版本、来源和审核状态。
- LLM 只能产生结构化候选，不能直接发布岗位版本。
- PostgreSQL 是事实主库，Neo4j 是可重建图谱投影。
- 前端、CLI 和后台任务通过 Application Use Case 和 API 契约协作。
- Python 环境和依赖只使用 `uv`；TypeScript/Node 环境和依赖只使用 `pnpm`。
- 不使用 `pip`、`venv`、`npm`、`yarn` 或全局安装的项目依赖。

## 2. 脚本命名

所有脚本文件的基础名称不得超过 **10 个字符**，包括 Python、Shell、PowerShell、SQL 和可执行脚本。

推荐名称：

```text
ingest.py       # 6
extract.py      # 7
normalize.py    # 9
forecast.py     # 8
backtest.py     # 8
evaluate.py     # 8
seed.py         # 4
health.py       # 6
```

禁止使用过长、包含完整句子的脚本名，例如 `run_historical_forecast_pipeline.py`。长流程使用 CLI 子命令表达：

```text
hiro2 temporal backtest
hiro2 temporal forecast
```

脚本文件名使用小写字母和下划线，避免空格、中文和随意缩写。脚本职责必须单一；超过一个明确职责时拆成模块或 CLI 子命令。

### 文件长度

- Python、TypeScript 和 TSX 业务文件建议控制在 **500 行以内**。
- 超过 **800 行**时，PR 或变更说明必须说明职责边界、为何当前不拆分，以及后续处理计划。
- 超过 **1000 行**原则上必须拆分；数据库 migration、生成代码、静态数据和单一主题的大型测试夹具可例外。
- 测试文件建议控制在 **800 行以内**，超过 **1200 行**需要审查。
- 单个函数建议不超过 **50 行**，超过 **80 行**时检查是否混合了多个职责；React 组件超过 **400 行**时优先拆出面板、表单或数据查询。
- 超过阈值时优先按职责拆分，不得为了压行数制造无意义的 Wrapper、基类或工具函数。
- 行数是设计预警，不是机械阻断规则；最终判断以职责数量、依赖复杂度和可测试性为准。

## 3. 项目层级

目录结构保持浅层和按职责分组：

```text
hiro2/
├── apps/          # api、web
├── backend/       # domain、application、infrastructure、workers
├── data/          # raw、processed、fixtures、runs
├── docs/          # 当前主文档
├── evaluation/    # 标注集和评测入口
├── migrations/    # 数据库迁移
└── scripts/       # 短脚本和一次性工具
```

规则：

- 除非有明确边界，不新增目录层级。
- 每个业务目录建议保留 5～10 个直接子文件；少于 5 个时优先合并到相邻职责目录。
- 超过 10 个文件时，只有在职责确实不同的情况下才拆分子目录。
- 不按函数、接口或单个页面创建目录。
- 不为每个 Agent、每个 API 或每个数据源创建独立目录。
- 临时输出、日志和运行产物不得进入源码目录。
- 外部压缩包解压后的原始目录可以保留来源结构，但必须位于 `data/raw/`，不作为正式代码层级。

## 4. 数据目录

```text
data/raw/          原始文件，只读，不覆盖
data/processed/    清洗和标准化结果，可重建
data/fixtures/     小型固定调试样本
data/runs/         CLI、回测和评测运行产物
```

原始数据进入系统前必须生成 manifest、哈希、来源和导入模式。历史回填使用 `backfill` 标记，不能伪装为实时采集。

## 5. 前后端边界

- 前端不直连 PostgreSQL、Neo4j 或对象存储。
- 后端不返回数据库内部结构，API 返回稳定 View Model。
- CLI 和前端调用同一 Application Use Case。
- `JobImpactSuggestion` 是时间预测域连接岗位图谱域的唯一业务出口。
- 人岗匹配只接受 `CandidateProfile + PublishedJobVersion`。
- 预测、日报和 Excel 不得直接进入匹配计算。

## 6. Prompt 管理

- Prompt 必须使用 YAML 管理，不得把长 Prompt 散落在 Python/TypeScript 源码中。
- 每个 Prompt 文件只负责一个任务，推荐放在 `prompts/`：`extract.yml`、`signal.yml`、`forecast.yml`、`review.yml`。
- 每份 YAML 必须包含 `id`、`version`、`task`、`system`、`input_schema`、`output_schema`、`limits` 和 `enabled`。
- YAML 可以管理字段说明、枚举提示、必填标记和模型限制，但不得成为第二套运行时 Schema。
- Pydantic 是 Agent 输出、API DTO 和领域转换的唯一运行时校验来源；TypeScript 类型由 OpenAPI 生成。
- Prompt 的版本、模型、Schema 和参数必须写入每次 `run` 产物；修改 Prompt 必须递增版本。
- Prompt 模板只能使用声明过的变量；不得把密钥、个人信息或未脱敏简历写入仓库。
- Prompt 输出必须经过 Pydantic 校验；失败进入重试或人工队列，不能静默接受自由文本。

## 7. 日志与运行记录

- 正式日志使用 JSONL；终端可以有中文摘要，但 JSONL 才是机器读取的事实日志。
- 每次 CLI、API、worker 和回测运行必须生成 `run_id`，相关子任务使用 `parent_run_id` 或 `correlation_id`。
- 必填字段：`ts`、`level`、`run_id`、`stage`、`event`、`component`、`status`。
- 可追溯字段：`item_id`、`source_id`、`dataset_version`、`model_version`、`prompt_version`、`duration_ms`、`count`。
- 异常字段：`error_type`、`error_message`、`retry_count`；错误必须保留堆栈文件路径或错误 ID。
- 日志不得写入 API key、完整 Prompt、原始简历、手机号、邮箱、身份证号或大段正文；使用 ID、哈希和截断摘要。
- 运行产物统一放在 `data/runs/<run_id>/`：`config.json`、`events.jsonl`、`metrics.json`、`errors.jsonl` 和必要的输入输出引用。
- 事件名称使用 `snake_case`，日志级别只使用 `DEBUG`、`INFO`、`WARN`、`ERROR`。

## 8. 文档规则

- 主文档只写当前有效的结论、契约、验收和状态。
- 一份文档只回答一个问题，禁止重复项目背景。
- 详细样本放数据目录，历史决定写 ADR，代码细节写代码和测试。
- Roadmap 只管理阶段、依赖、联调门和退出条件，不替代任务看板。
- 文档改动必须同步检查关联代码、接口和 Roadmap。
- 图表、页面和业务说明优先使用中文；只有代码标识符、协议名、框架名、API 路径和数据字段保留英文。
- 禁止在同一图表节点或 UI 标签中重复中英文表达同一含义，例如“Evidence 证据层”。

## 9. 变更前检查

- [ ] 是否已有目录可以承载这次文件？
- [ ] 新脚本名称是否不超过 10 个字符？
- [ ] 新文件是否增加了重复职责？
- [ ] 是否需要更新 `contracts.md` 或 Roadmap？
- [ ] 是否能通过 CLI 或测试复现？
- [ ] 是否把原始数据、合成数据和正式评测数据区分开？
- [ ] 新的 Agent 是否有对应 YAML Prompt、版本和输出 Schema？
- [ ] YAML 的 `output_schema` 是否存在对应 Pydantic 模型？字段和枚举是否一致？
- [ ] 新的任务是否记录了完整 `run_id` 和结构化日志？
- [ ] 日志和运行产物是否已脱敏？

## 10. 本地开发与提交

- 新成员克隆项目后必须执行 `make init`，它会运行 `uv sync --all-groups`、`pnpm install --frozen-lockfile`（Web 存在时）并安装 Git hooks。
- Python 命令统一使用 `uv run`，Web 命令统一使用 `pnpm --dir apps/web`。
- 提交前至少运行 `make check`；提交 Hook 自动执行文件完整性、密钥、大文件、Ruff 检查和格式化。
- 完整本地校验使用 `make verify`；排查 Hook 时使用 `make precommit`。
- 提交信息必须使用 Conventional Commits：`type(scope): 摘要`，其中 scope 可省略；例如 `feat(temporal): 增加日报导入`、`docs: 更新数据路线图`。
- 允许的 type：`feat`、`fix`、`docs`、`refactor`、`test`、`chore`、`build`、`ci`、`perf`、`style`。
- 对用户可见、可部署或可验证的变更必须同步更新根目录 `CHANGELOG.md` 的 `Unreleased` 区域。

## 11. 原生能力优先

Hiro2 的工程品味不是“代码越多越专业”，而是：**优先使用当前框架和数据库已经提供的原生能力，只在业务规则确实不存在时编写自有代码。**

### 决策顺序

实现新功能前按以下顺序判断：

```text
1. 当前框架/数据库是否原生支持？
   是 -> 直接使用原生 API
2. 是否只是缺少少量业务适配？
   是 -> 写薄适配层，不复制框架内部机制
3. 是否是 Hiro2 独有的领域规则？
   是 -> 写领域模块，并配套测试和契约
4. 是否只是为了绕过不熟悉的官方 API？
   是 -> 先查官方文档和源码，不新增轮子
```

### 具体规则

- LangGraph 优先使用原生 State、Node、Edge、Checkpointer、interrupt、stream 和 retry；不得再自建一套状态机、事件流或检查点系统来包裹同样能力。
- FastAPI 优先使用原生依赖注入、Background Task、StreamingResponse、OpenAPI 和异常处理；不得另造路由注册、DTO 校验或 SSE 协议。
- Next.js 优先使用 App Router、Server/Client 边界、Route Handler 和现有数据请求库；不得为每个页面自建 API 缓存和状态管理。
- Pydantic 优先承担结构校验、配置校验和模型输出校验；不得用手写 `if/else` 复制 Schema 校验。
- PostgreSQL 优先使用事务、唯一约束、UPSERT、JSONB、窗口函数和索引；不得在 Python 中搬运数据库已经能完成的聚合。
- Neo4j 优先使用参数化 Cypher、约束、索引和官方 driver；不得再包装一层与 Cypher 一一对应的“通用图数据库框架”。
- `feedparser`、PyMuPDF、python-docx 等底层库只通过薄适配器接入；适配器负责格式转换，不复制解析器。

### 什么时候可以自建

只有以下内容允许自建：

- 岗位能力版本 Diff；
- 证据质量和来源权重；
- 技能归一化规则；
- 历史回测时间切片；
- 人岗匹配评分；
- `JobImpactSuggestion` 审核流；
- Hiro2 的领域 DTO、Repository 和 Application Use Case。

这些是 Hiro2 的业务差异，不是框架功能的重复实现。

### 反垃圾代码检查

新增一个抽象、Wrapper、Manager 或基类前，必须回答：

```text
它是否删除了真实重复？
它是否隔离了外部系统变化？
它是否承载了 Hiro2 独有的业务规则？
它是否能用测试证明价值？
```

如果四个问题都不能回答清楚，优先删除抽象，直接调用原生能力。

### 提交前检查

- [ ] 是否查过当前框架的官方原生 API？
- [ ] 是否重复实现了框架已有的状态、校验、重试、流式或持久化能力？
- [ ] 新增抽象是否包含真实领域规则，而不是转发一层函数？
- [ ] 能否用更少的文件和更短的代码实现同样行为？

## 12. 数据库、API 与数据集

- 数据库 schema 只能通过 `migrations/` 中的 migration 修改；已应用 migration 不得重写。
- 破坏性 schema 变更必须有迁移方案、兼容窗口和回滚说明。
- API 变更先更新 Pydantic DTO 与 `contracts.md`，再修改 Application、前端和测试。
- API 响应使用稳定 View Model，不直接暴露数据库实体；删除或重命名字段必须说明兼容策略。
- 数据集必须有 `dataset_version`，并区分 raw、调优、验证和封存测试数据。
- 指标报告必须记录数据集版本、样本量、标注规则、运行版本和错误样本；未经封存的数据不得宣称最终指标。
- 已发布岗位版本、审核记录和评测结果只能追加新版本，不能覆盖历史事实。

## 13. 配置、任务与安全

- 密钥只存在 `.env` 或 CI Secret；`.env.example` 只保留字段说明和占位值。
- 可版本化阈值、来源权重、时间窗口和 Prompt 放在 YAML 配置中，不写死在业务代码。
- 每个定时任务必须声明频率、超时、并发策略、幂等键、重试上限和失败状态。
- 任务使用唯一键或数据库约束保证幂等；重复 RSS、重复预测和重复审核任务必须可安全跳过。
- 原始日报、JD、简历和大型文件不提交 Git；Git 只保存 manifest、脱敏 fixture 和小型评测样本。
- 简历、联系方式和个人信息只允许在受控存储中处理；导出、日志和截图必须脱敏。

## 14. 质量门

- 提交前运行 `make check`；合并前运行 `make ci`，其命令必须与 GitHub Actions 一致。
- Python 代码目录出现后，Ruff、mypy 和 pytest 不允许再静默跳过。
- Web 目录出现后，`lint`、`format:check`、`typecheck`、`test`、`build` 必须在 `package.json` 中存在。
- 关键变更至少补一类测试：领域规则用单元测试，接口用契约测试，数据库/图谱用集成测试，完整流程用端到端测试。
- 数据处理、预测、评测和岗位发布必须保留失败案例，不能只保存成功结果。

# ADR 0006：API 分层、契约源与审核写路径

## 背景

数据侧产物（JSONL）已支撑主案例，前端工作台以 fixture 驱动并自建了 TS 类型（含
stance/excerpt 等 contracts 未定义字段），后端尚无 API。直接开写 API 会造成三件事：
路由穿透数据层（Phase B 换 PostgreSQL 时重写）、固化前后端两套契约漂移、审核动作无
合规落点。前端 fixture 的 Evidence 需要 excerpt/fullText，当前 evidence.jsonl 未存摘录。

## 决定

1. **Repository 接口先行**：Application 层依赖 Repository 接口；Phase A 实现
   FileRepository（读 `data/processed/` 产物，启动时加载、内存供给），Phase B 替换为
   PostgresRepository，Application 与 API 层零改动。
2. **OpenAPI 是唯一契约源**：View Model 以 Pydantic 定义于 Application 层，FastAPI 导出
   OpenAPI；前端 TS 类型由 OpenAPI 生成，替换手写类型。字段命名、枚举（含中文
   SourceType/stance）以 OpenAPI 为准，与前端现有类型的映射在 View Model 层完成。
3. **Evidence View Model 补齐摘录**：`evdev build` 产物在 View Model 层联查事件
   summary/JD 片段输出 excerpt/fullText；stance 当前数据只产生"支持"，"反证"待 D7
   冲突检测，字段先行保留。
4. **审核写路径为 append-only JSONL**：Phase A 的 review 提交追加写
   `data/processed/review/review-actions.jsonl`（run_id/ts/decision/evidence_ids），
   满足"审核记录只能追加"；JobVersion 发布（不可变）推迟到 Phase B 数据库落地。
5. **View Model 白名单输出**：API 只输出显式声明的字段；boss 侧 hrName 等个人信息
   字段永不透出。

## 后果

- API 进程入口在 `apps/api`（AGENTS 层级 apps = api、web），复用 backend 包与同一 uv 环境。
- 前端需将 `lib/*.ts` 手写类型切换为 OpenAPI 生成，是一次跨端协调成本。
- FileRepository 面向 MB 级产物，不做缓存/分页复杂化（YAGNI）。
- Phase B 落 PostgreSQL 时，审核 JSONL 迁移入库，接口不变。

## 替代方案

- 路由直读 JSONL：实现最快，但违反 architecture.md 分层，Phase B 全部重写。
- 迁就前端现有类型定义 API：固化两套契约漂移，违背 AGENTS"TS 类型由 OpenAPI 生成"。
- Phase A 只做只读、审核等 Phase B：前端全流程（含提交审核）无法联调，I1 门推迟。

# 架构决策记录

ADR 只记录影响长期实现或数据可信性的决策。每篇只包含：背景、决定、后果和替代方案，不记录调研过程或实现细节。

| ADR | 决定 |
| --- | --- |
| [0001](0001-env.md) | Python 使用 uv，TypeScript 使用 pnpm |
| [0002](0002-store.md) | PostgreSQL 是事实主库，Neo4j 是投影 |
| [0003](0003-impact.md) | 预测只能输出岗位影响建议 |
| [0004](0004-prompt.md) | Prompt 使用 YAML，运行记录使用 JSONL |
| [0006](0006-api-layering.md) | API 分层、OpenAPI 契约源与审核 append-only 写路径 |

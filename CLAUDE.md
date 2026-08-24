# Hiro2 Claude Code 工作流

> 项目规范唯一来源是 [`AGENTS.md`](AGENTS.md)。本文件只说明 Claude Code 如何在该规范下工作，不重复技术、数据或提交规则。

## 开始任务前

1. 阅读 `AGENTS.md` 和 `docs/README.md`。
2. 按任务类型阅读对应文档：
   - 产品：`docs/product.md`
   - 前端：`docs/design.md`
   - 架构：`docs/architecture.md`
   - 接口：`docs/contracts.md`
   - 数据：`docs/roadmap-data.md`
   - 时间预测：`docs/temporal-system.md`
3. 在修改已有代码前运行 `make check`，记录已有失败项。

## 开发流程

- Python 只使用 `uv`，TypeScript/Node 只使用 `pnpm`。
- 业务规则优先调用框架原生能力；新抽象必须符合 `AGENTS.md` 的原生能力优先规则。
- API、事件或数据对象变更，先更新 `docs/contracts.md` 和 Pydantic DTO。
- 新 Agent 先创建或更新 `prompts/*.yml`，递增版本，并保证 `output_schema` 对应 Pydantic 模型。
- 数据处理、回测和 Agent 调优通过 CLI 运行，保留 `run_id` 与 JSONL 运行产物。
- 前端先接入稳定 View Model 或 Mock Adapter，不直连数据库和外部模型。

## 完成任务前

1. 运行 `make verify`；涉及完整构建时再运行 `make build`。
2. 更新受影响的 Roadmap 状态、接口文档或 ADR。
3. 用户可见、可部署或可验证的变更更新 `CHANGELOG.md` 的 `Unreleased`。
4. 汇报已执行检查、未完成项和剩余风险。

## 规则优先级

```text
AGENTS.md
  > docs/contracts.md
  > 本文件的 Claude 操作流程
  > 代码中的临时假设
```

代码和测试结果与文档冲突时，先报告差异并更新当前有效文档，不能静默维持两套事实。

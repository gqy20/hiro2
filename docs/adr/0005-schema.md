# ADR 0005：YAML Prompt 与 Pydantic Schema

## 背景

Agent Prompt 需要让团队方便调整，但运行结果必须有稳定、可测试的类型契约。

## 决定

- YAML 管理 Prompt 文本、任务说明、字段描述、枚举提示、模型限制和版本。
- Pydantic 是 Agent 输出、API DTO 和领域转换的唯一运行时校验来源。
- YAML 的 `output_schema` 只引用 Pydantic 模型名，不动态生成第二套 Schema 系统。
- 前端类型由 OpenAPI 生成，不能手写第三套接口字段。

## 后果

Prompt 调整不需要修改业务代码；字段类型和业务约束仍然可以通过测试、IDE 和运行时校验保证。

## 替代方案

不采用“YAML 完整定义类型、代码动态解释”的自制 Schema 框架，避免重复实现 Pydantic。

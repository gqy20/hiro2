# ADR 0004：Prompt 与运行记录

## 背景

历史回测和 Agent 调优必须能够复现输入、模型、Prompt、规则和错误。

## 决定

- Prompt 使用 YAML 管理，并带 `id`、`version`、输入/输出 Schema 和限制。
- 每次 CLI、API、worker 和回测运行写入 `run_id` 和 JSONL 事件日志。
- 运行产物保存在 `data/runs/<run_id>/`。

## 后果

系统可以比较两次实验、复盘预测错误，并避免 Prompt 被静默替换。

## 替代方案

不将长 Prompt 散落在业务代码中，也不只依赖终端日志。

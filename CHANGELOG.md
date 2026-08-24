# 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的记录方式，并使用语义化提交信息。

## [Unreleased]

### Added

- 增加归一化时间闸门：语料习得别名独立为 `data/SKILLS-EARNED.yml` 并带首见日期，`resolve --as-of` 时未来习得词不参与匹配，防止回测规则泄漏；新增分桶覆盖率与带上下文的未命中词单。
- 事件抽取改为逐篇落盘并提升并发至 5，长批次中断不丢已完成结果。

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

### Changed

- 将日常协作反馈设计为前端任务、审核和评测闭环。

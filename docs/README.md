# Hiro2 文档

项目级协作规范以根目录 [`AGENTS.md`](../AGENTS.md) 为唯一来源；[`CLAUDE.md`](../CLAUDE.md) 只提供 Claude Code 的执行流程。

## 先看什么

1. [产品定义](product.md)：用户、范围、功能和验收。
2. [用户场景](user-scenarios.md)：角色、决策路径、异常处理和体验验收。
3. [系统总览](overview.md)：完整数据处理、预测、岗位和匹配链路。
4. [技术架构](architecture.md)：模块边界、数据流和存储。
5. [数据与接口契约](contracts.md)：核心对象、状态、API 和事件。
6. [时间情报系统](temporal-system.md)：RSS、历史回测、未来预测和岗位影响建议。
7. [数据 Roadmap](roadmap-data.md)：数据清洗、岗位阶梯、技能和证据进度。
8. [前端 Roadmap](roadmap-frontend.md)：页面、交互和联调进度。
9. [后端 Roadmap](roadmap-backend.md)：数据、API、管道和部署进度。
10. [评测与交付](evaluation.md)：指标、测试、部署和答辩证据。
11. [前端设计参考](design-references.md)：外部平台调研、AI 交互模式和可迁移设计规则。
12. [架构决策记录](adr/README.md)：不可逆技术和数据决策。
13. [研究资料](research/README.md)：发榜方契合度、竞品和产品取舍。

完整历史版本保存在 [`archive/`](archive/)。历史文档只用于查阅，不作为当前实现依据。

## 当前状态

| 项目 | 状态 |
| --- | --- |
| 当前阶段 | T1 收尾：数据主线完成，证据实体（D7）与评测集（D9）待做 |
| 已完成 | 产品需求与技术边界；D0-D6 数据主线（归一 85%、8350 事件、243 条 AI 域 JD、岗位映射 94%、两窗口 diff、提前量验证、岗位版本草稿） |
| 下一步 | D2 事件去重（17% 速览/正文冗余）、D7 Evidence 实体、后端 API 与 PostgreSQL、评测集与 100 条人工标注 |
| 当前阻塞 | 暂无 |

前后端共用阶段 `T1-T4`，每个跨端任务通过 `I1-I4` 联调门验收。两个 Roadmap 的状态只能使用：未开始、进行中、阻塞、待验收、完成。

## 本地开发

Python 使用 `uv`，TypeScript/Node 使用 `pnpm`。克隆项目后执行：

```bash
make init
```

常用命令：

```bash
make check
make verify
make precommit
make build
make ci
```

提交信息使用 `type(scope): 摘要`，例如 `feat(temporal): 增加日报导入`。用户可见或可验证的变更同步记录到根目录 [`CHANGELOG.md`](../CHANGELOG.md)。

## 已确定的技术规则

- PostgreSQL 是业务事实主库。
- Neo4j 是岗位能力图谱投影，不是事实主库。
- LLM 只产生结构化候选，不直接发布正式数据。
- 岗位版本发布后不可变，修改通过新版本完成。
- 所有岗位、技能和匹配结论必须引用 `evidence_id`。
- 评测指标由确定性脚本生成，不在前端手填。
- 预测通过 `JobImpactSuggestion` 连接岗位系统，不直接发布岗位版本。
- 前端和 CLI 共用 Application Use Case，旧项目不共享数据库。
- Prompt 用 YAML 管理，Pydantic 作为唯一运行时 Schema 校验来源。
- 业务文件建议不超过 500 行；超过 800 行需在变更说明中解释，超过 1000 行原则上按职责拆分。完整规则见 `AGENTS.md`。
- 前端基础组件使用 Ant Design 6，AI 交互组件使用 Ant Design X 2.x，图谱使用 `@xyflow/react`；不重复实现等价基础组件。
- Hiro2 的主交互是结构化任务流程，AI 对话只用于上下文意图和追问，不能承载核心结论或绕过人工审核。

## 文档规则

- 主文档只写结论、契约、验收和当前状态。
- 研究资料、完整样本和废弃方案不进入主文档。
- 新决定写入 ADR；实现细节写代码和测试。
- 超过文档篇幅上限时，优先删除重复说明，不继续堆章节。

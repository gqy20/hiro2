## 基本信息
- 李同学 | 求职意向：AI Agent 开发工程师 | 电话：138****0000 | 邮箱：li.tongxue@example.com | 3 年工作经验

## 技能
- 熟练使用 LangChain 0.2 搭建 Agent 工作流，熟悉 ReAct、Plan-and-Execute 等模式，做过自定义 Tool 封装和记忆管理
- 熟悉 Python 3.10 开发，用过 asyncio 做并发调用，写过多轮对话状态机
- 搞过 torch 做小规模模型微调 (SFT/LoRA)，也玩过 HuggingFace/transformers 做推理加速（vLLM 部署）
- 用 sklearn 做过意图分类和实体抽取的 baseline，方便对比 prompt 效果
- 熟悉 FastAPI 写服务接口，配合 Docker Compose 部署过完整 Agent 服务
- 向量库用过 Qdrant，踩过 schema 不一致的坑，后来加了 embedding 版本管理

## 项目经历

**智能客服 Agent（公司内部项目）** | 2023.06 - 2024.03
- 基于 LangChain 0.2 + Qdrant 搭 RAG 流程，处理技术文档问答，将首次解决率从 45% 提到 68%
- 设计了 5 个自定义 Tool（查工单、查库存、转人工），并用 AgentExecutor 做工具路由
- 用 FastAPI 封装成微服务，用 Docker Compose 编排，支持水平扩展

**简历解析 Agent（核心落地项目）** | 2024.04 - 至今
- 针对非结构化简历，构建"提取→校验→结构化"三步工作流，用 Pydantic 做输出约束
- 搞过 torch 对低质量扫描件做 OCR 后处理，结合 HuggingFace 的 NER 模型抽取技能实体
- 用 sklearn 训练了简历段落分类器，准确率 89%，作为 prompt 的 fallback

## 工作经历
**某科技公司 | AI 开发工程师** | 2022.07 - 至今
- 负责公司内部 Agent 平台开发，维护 10+ 个自动化流程
- 参与模型选型和评估，写了不少 prompt 模板和 few-shot 示例

## 教育背景
**某理工大学 | 计算机科学与技术 本科** | 2018.09 - 2022.06

## 证书
- 阿里云 ACA 云计算认证（2023）

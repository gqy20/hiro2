## 基本信息

- 姓名：李同学
- 电话：138****0000
- 邮箱：li.tongxue@email.com
- 求职意向：AI 应用开发工程师（初中级）
- 工作年限：3 年（2 年后端 + 1 年 AI 应用）

## 技能

- **语言与框架**：Python 3.10（主力）、Java（曾用）、FastAPI、Flask
- **机器学习/深度学习**：sklearn（分类/回归/聚类）、torch（自己搞过 CNN 和简单 Transformer，踩过不少显存优化的坑）
- **大模型相关**：HuggingFace Transformers（用过 Llama、ChatGLM 的 checkpoint）、SFT/LoRA 微调流程（玩过 QLoRA 节省显存）
- **工具与平台**：Docker、Git、MySQL、Redis、Linux（日常操作没问题）

## 技能清单

- 熟悉 Python 3.10 的异步编程、装饰器、多进程，能写干净的工程代码
- 会用 torch 搭建和调试小型模型，对反向传播、梯度裁剪有实际理解
- 掌握 sklearn 的 Pipeline 和交叉验证，做过特征工程和模型评估
- 熟悉 HuggingFace Transformers 的加载、推理和微调（用 LoRA 在单卡上微调过 7B 模型）
- 了解 RAG（检索增强生成）的常用链路：embedding + 向量库 + 重排序
- 会用 LangChain 0.2 搭 Agent 和工具调用，写过业务问答机器人

## 项目经历

**智能客服问答系统（RAG 方向）** — AI 应用开发工程师
2024.03 – 2024.09

- 基于 LangChain 0.2 和 FastAPI 搭建知识库问答服务，支持文档上传、分块、向量检索
- 使用 HuggingFace Transformers 加载 embedding 模型，集成向量库（Chroma）做相似度召回
- 对 7B 模型做 SFT/LoRA 微调，解决专业术语回答不准的问题，准确率提升约 15%
- 用 Redis 缓存高频问题，接口 P95 延迟从 2s 降到 800ms

**订单中台重构（后端转 AI 的过渡项目）** — 后端开发工程师
2022.07 – 2024.02

- 用 Java 和 MySQL 重写订单查询接口，QPS 从 200 提升到 800
- 学习 torch 和 sklearn，用 Python 写脚本分析订单异常数据，产生初步兴趣
- 主动在业余时间完成一个基于 FastAPI 的文本分类 demo，用于内部工单自动分派

## 工作经历

**某某科技有限公司** — 后端开发工程师 → AI 应用开发工程师
2022.07 – 至今

- 初期负责订单系统后端，后期转入 AI 组，负责 RAG 相关模块的开发和部署

## 教育背景

**某某大学** — 计算机科学与技术（本科）
2018.09 – 2022.06

## 证书

- 无（不追求纸面证书，靠项目说话）

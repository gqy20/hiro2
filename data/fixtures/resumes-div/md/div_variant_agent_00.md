## 基本信息
- 姓名：沈书言
- 常驻城市：成都
- 邮箱：name@example.com ｜ 电话：138****0000
- 教育背景：南洋理工大学 · 信息与计算科学（本科）
- 证书：软考高级（系统架构设计师）

## 技能
- **LangChain 0.2** 熟练（2 年+），搞过 Agent 多工具编排、记忆持久化与回调链，踩过不少 LCEL 的坑
- **Python 3.10** 熟练（3 年），日常写异步任务、类型注解与 Pydantic 校验
- **HF/HuggingFace** 熟练，玩过 Transformers pipeline、微调 (SFT/LoRA) 与 vLLM 部署
- **torch** 熟悉（2 年），主要用于 embedding 模型与 reranker 的推理调优
- **sklearn** 熟悉（3 年），做特征工程和分类/聚类基线

## 技能清单
- 工作流：Dify 工作流 + n8n 临时搭自动化
- 数据库：PostgreSQL + pgvector、Redis（缓存/限流）
- 部署：Docker Compose、Nginx 反向代理、Prometheus 监控

## 项目经历
### AI 客服 Agent（订单/售后）｜ 核心开发 ｜ 2023-2024
- 基于 LangChain 0.2 搭 ReAct Agent，接入工具层（查单/退换/优惠券），解决多轮对话中工具参数幻觉问题
- 自研模板匹配 + reranker 二阶段召回，准确率从 72% 提到 89%；用 HF/HuggingFace 的 bge-m3 做 embedding
- 在 Dify 工作流里拖出人工转接分支，兜底率降至 8%

### 代码评审 Agent（内部提效工具）｜ 独立开发 ｜ 2022-2023
- 用 torch 封装本地 code-bert 模型，做 commit diff 缺陷分类；结果写入 MR 评论
- 用 Python 3.10 写 FastAPI 服务，Docker Compose 一键部署，组内 40+ 人使用，每周节省约 6 小时

## 工作经历
- **华为**（2021-2023）｜ 软件开发工程师（AI 方向）：负责内部工单意图识别模块，用 sklearn 做特征与建模，迭代上线 3 个版本；参与推理服务容器化改造
- **阿里巴巴**（2023 至今）｜ 算法工程师（Agent 应用）：主导两个内部 Agent 落地，涉及工具调用与多 Agent 协作；用 React 写了简易调试页，方便非技术同事上传工具 schema

## 教育背景
南洋理工大学 · 信息与计算科学 ｜ 2017-2021
- Google Summer of Code（GSoC）：为开源 NLP 库实现文档摘要插件
- ACM-ICPC 亚洲区域赛：铜奖（队伍负责图论与数据结构板子）

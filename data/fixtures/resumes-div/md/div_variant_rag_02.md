## 基本信息
- **姓名**：李同学
- **电话**：138****0000
- **邮箱**：litongxue@example.com
- **求职意向**：RAG 应用开发 / 知识库工程师（初中级）

## 技能
- 熟悉 **LangChain 0.2** 的 Agent 与检索链，自己搭过基于多路召回的重排序流水线
- 会用 **torch** 做 embedding 微调（主要是 sentence-transformer 的对比学习），也拿 **sklearn** 做过召回后的分类/过滤
- 日常用 **HF/HuggingFace** 的模型库，玩过 bge-m3、gte-large 这些，踩过量化精度和上下文截断的坑
- 熟练 **Python 3.10**，asyncio 写并发抓取和文档预处理，正则+BeautifulSoup 做 html/pdf 清洗
- 向量库方面：**ChromaDB** 做原型，生产环境切过 **Elasticsearch 8.x**，搞过 dense+sparse 混合检索（BM25+向量）
- 文档解析：**PaddleOCR** 处理扫描件和表格，配合 layout 模型拆版面，准确率调到 85%+ 就够用

## 技能清单
- 检索增强：RAG 流程设计、混合检索、重排序、query 改写
- 向量库：ChromaDB / Elasticsearch 8.x / Milvus（了解）
- 文档处理：PDF/图片 OCR、表格抽取、Markdown 化
- 模型：embedding 微调、prompt 工程、轻量 SFT（LoRA 试过）
- 工程：FastAPI 服务、Docker 部署、Grafana 监控

## 项目经历
**企业合同问答知识库（2023.10 - 2024.05）**
- 手写 RAG 流程，基于 LangChain 0.2 搭建，处理 5 万份 PDF 合同，用 PaddleOCR 转文本，按条款切分并保留元数据
- 用 Elasticsearch 8.x 做 dense+sparse 混合检索，加 cross-encoder 重排，最终 Top-5 命中率从 52% 提升到 71%
- 踩过分数归一化的坑，最后用 RRF 融合才稳定；上线后处理日均 800+ 查询

**问答机器人后台（2024.06 - 2024.11）**
- 负责知识库同步管道，Python 3.10 写异步爬虫，增量更新 3 万条 FAQ，ChromaDB 存 embedding
- 用 torch 在内部数据上微调 bge-base，对比原始模型准确率提升 6%；偶尔用 HF/HuggingFace 拉新模型测试
- 写 FastAPI 接口给前端调用，Docker 一键部署，排查过内存泄漏（batch 没清干净）

## 工作经历
**某数据服务公司 | RAG 开发工程师（2022.03 - 至今）**
- 参与 3 个知识库项目，负责文档解析、检索优化和接口开发，支持客户包括金融和制造业
- 内部沉淀了一套文档清洗工具，减少 30% 人工标注工作量

## 教育背景
**某理工大学 | 计算机科学与技术（本科，2018 - 2022）**

## 证书
- 软考中级（软件设计师，2021）
- 无其他硬性证书，主要靠项目经验说话

## 基本信息
- 姓名：赵清扬
- 常驻城市：北京
- 邮箱：zhao.qingyang@example.com
- 电话：138****0000
- 教育背景：重庆邮电大学 · 电子信息工程（本科）

## 技能
- **编程语言**：Python 3.10（主力）、SQL、Java（够用）
- **LLM 与框架**：玩过 LangChain 0.2，搞过 RAG 全链路调优；熟悉 HF/HuggingFace 的 Transformers、peft 微调（SFT/LoRA 有踩坑）
- **向量库与检索**：FAISS（日常用）、Milvus 2.3（生产部署）；了解倒排索引和 TF-IDF，混合检索（BM25+向量）有自己的封装
- **文档解析**：用 PyMuPDF 处理 PDF 布局、表格抽取，配合正则处理脏数据；OCR 场景调过 PaddleOCR

## 技能清单
| 技能 | 熟悉度 | 使用年限 |
|------|--------|----------|
| Python 3.10 | 熟练 | 3 |
| LangChain 0.2 | 熟练 | 2 |
| FAISS | 熟悉 | 2 |
| Milvus 2.3 | 熟悉 | 1 |
| HF/HuggingFace | 熟悉 | 2 |
| PyMuPDF | 熟悉 | 1 |
| TF-IDF | 了解 | 2 |

## 项目经历
**智能问答知识库平台（RAG 落地）** · 核心开发
- 基于 LangChain 0.2 + FAISS 搭建企业内部文档问答系统，支持 50 万级文档分块、embedding 入库；开发了 query 改写和 rerank 模块，检索命中率从 71% 提到 89%
- 用 PyMuPDF 处理 PDF 扫描件和复杂表格，解决页眉页脚、跨页表格断裂问题，解析准确率提升约 30%
- 优化 chunk 大小和 overlap 策略，同时接入 Milvus 2.3 做向量索引，搜索延迟从 1.2s 降到 300ms

**电商客服知识库（京东）** · 用户意图检索优化
- 针对客服问答场景，用 HF/HuggingFace 的 Sentence-BERT 做 sentence embedding 蒸馏，替换原生 text-embedding-ada 模型，降低 40% 推理成本
- 搞过混合检索：用 TF-IDF 和向量召回做加权融合，解决长尾口语化问题的冷启动；在 LangChain 0.2 里自己写了一个 custom retriever 类

## 工作经历
- **京东 · 搜索与推荐平台部**（至今）· NLP 算法工程师
  - 负责商品知识图谱实体链接和问答链路优化，主导 RAG 服务从 POC 到生产
- **微软中国 · 云与 AI 事业部**（2-3 年）· 数据工程师助理
  - 参与 Azure 文档解析管线和数据清洗工作，处理多格式 PDF/DOCX，积累了文档解析和异步任务编排经验

## 证书
- AWS 解决方案架构师助理（SAA）

## 其他
- 大学期间参加“互联网+”大学生创新创业大赛，负责数据采集与预处理模块；获省赛银奖
- 曾参与 Google Summer of Code（GSoC），为开源 OCR 项目贡献预处理代码，顺带摸了 Tesseract 和 OpenCV

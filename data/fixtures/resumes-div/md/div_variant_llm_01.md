## 基本信息
李同学 | 138****0000 | lixx@example.com | 广州
求职意向：大模型应用开发工程师（初中级）

## 技能
- **torch**（3年）：日常炼丹主力，自己搭过DDP训练脚本，也改过别人写的huggingface trainer。
- **sklearn**（2年）：搞传统baseline够用，主要拿来给大模型做召回对照/数据清洗。
- **HF/HuggingFace**（2年）：transformers、datasets、peft这些库天天摸，下载模型、改config、调试tokenizer都是家常便饭。
- **LangChain 0.2**（2年）：Chain/Agent/Retriever都玩过，自己封装过自定义tool，也踩过callback和streaming的坑。
- **Python 3.10**（3年）：类型注解、异步IO、装饰器都熟，写服务端接口和数据处理脚本很顺手。
- **大模型微调 (SFT/LoRA)**（2年）：用LoRA微调过Qwen和ChatGLM系列，也试过全参SFT（小模型），对loss曲线和过拟合挺敏感。
- **推理部署**（1年）：用**vLLM**做过推理服务加速，配过Continuous Batching和量化（AWQ），也用过Triton inference server但不够深。
- **向量检索**（2年）：用**FAISS**搭过几套RAG的底层索引，调过IVF和HNSW参数，对召回率和延迟的trade-off有感觉。

## 项目经历
**某电商智能客服知识库（RAG + Agent）** | 研发工程师 | 2023.09-至今
- 负责从0搭建检索链路：切分文档（chunk策略调了很久）、用embedding模型做向量化、存进FAISS索引。
- 基于LangChain 0.2写Agent流程，对接工单系统API，解决多轮对话中上下文丢失的问题（踩过history截断的坑，后来自己用滑动窗口+摘要搞定）。
- 上线后用户问题解决率从45%提升到62%，P95延迟控制在1.8s内。

**公司内部代码助手（LoRA微调）** | 模型工程师 | 2023.03-2023.08
- 用Qwen-7B做底座，基于内部代码库清洗数据，用LoRA微调（rank=8，alpha=16），改了训练脚本里的数据采样逻辑。
- 评估时发现生成的注释质量不稳定，后来加了few-shot prompt模板才压住。
- 部署用vLLM起服务，支持流式输出，团队10+人日常内测。

**简历解析系统（NLP分类+抽取）** | 算法工程师 | 2022.07-2023.02
- 用sklearn做传统baseline（TF-IDF+LR），后来换成预训练模型finetune，对比F1提升8%。
- 主要负责写数据标注规范、清洗和增强，兼做推理脚本的预处理/后处理逻辑。

## 工作经历
**XX科技有限公司** | 算法工程师 | 2022.07-至今
**XX信息技术公司** | 实习（NLP方向） | 2021.06-2022.06

## 教育背景
XX大学 | 计算机科学与技术 | 本科 | 2018.09-2022.06

## 证书
- CET-6
- 阿里云ACP（云计算架构师）

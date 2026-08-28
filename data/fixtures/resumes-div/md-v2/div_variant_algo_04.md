## 基本信息
- 姓名：李同学
- 电话：138****0000
- 邮箱：li.tongxue@example.com
- 求职意向：算法工程师（CV/多模态方向）

## 技能
- 编程语言：Python 3.10 为主，写过多年代码，C++ 能读能改能踩坑
- 深度学习框架：torch 玩得最熟（DDP、AMP、自定义算子都搞过），TF 只是偶尔碰
- 传统机器学习：sklearn 的 pipeline、GridSearch、特征工程那套顺手就来
- 模型部署：ONNX Runtime + TensorRT 导出踩过不少坑，有移动端（NCNN）落地经验
- 视觉工具：OpenCV 图像处理、albumentations 数据增强、MMDetection 3.x 框架
- 大模型生态：HuggingFace Transformers 日常使用（加载/微调/推理），PEFT 库用 LoRA 居多

## 项目经历

### 工业质检：PCB 缺陷检测系统
- 基于 torch 自研检测头，替换 MMDetection 里的标准 head，mAP 从 0.82 → 0.91
- 用 OpenCV 做图像预处理（畸变矫正 + 光照归一化），在线推理延迟压到 18ms
- 导出 ONNX Runtime 部署到工控机，解决动态 shape 和算子融合的坑

### 大模型文档问答助手（内部工具）
- 用 LangChain 0.2 搭 RAG 流程，接的是自研 embedding + 向量库（milvus）
- 对底座模型做过 SFT/LoRA 微调，主要在意图分类和格式抽取上提效果
- HuggingFace Transformers 加载量化模型（4bit 推理），显存占用降低 60%

### 人脸关键点服务
- 负责数据清洗和标注规范，自己写脚本做坏case挖掘
- 模型用 torch 写 ResNet50 + 坐标回归，蒸馏到 mobilenet 后线上跑在树莓派上

## 工作经历
- 2021.07 - 至今：某科技公司，算法工程师（先做 CV，后转大模型应用）

## 教育背景
- 2017.09 - 2021.06：某大学，计算机科学与技术，本科（GPA 3.6/4.0）

## 证书
- CET-6，阿里云 ACP 机器学习认证（纯属凑数，面试基本不问）

# Hiro2 系统总览

> 这份文档只回答一个问题：Hiro2 的数据如何经过处理，最终形成岗位版本和人岗诊断。
> Mermaid 源码是唯一图源，后续导出的 SVG/PNG 只能放在 `docs/assets/`，不能反向编辑。

## 导出图

- [系统总览 SVG](assets/system-map.svg)
- [数据处理流 SVG](assets/data-flow.svg)
- [岗位决策流 SVG](assets/decision-flow.svg)

## 可信岗位版本是系统中心

赛题要求的岗位发现、岗位更新、图谱和诊断共享一个业务中心，而不是四套功能数据：

```text
多源数据与时间信号 -> 证据/建议 -> 人工审核 -> 已发布岗位版本
                                           -> 图谱 / JD 模板 / 人岗诊断 / 培养任务
```

其中 AI 只负责结构化抽取、多源归因、时间推演和行动解释；`JobImpactSuggestion` 只能进入审核，不能绕过 `JobVersion` 成为正式事实。这个约束使亮点贯穿基础功能，而非成为孤立预测模块。

## 1. 系统总览

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#ffffff","primaryTextColor":"#20201d","lineColor":"#77736b","fontFamily":"Inter, Noto Sans SC, Microsoft YaHei, sans-serif"},"flowchart":{"htmlLabels":false}}}%%
flowchart LR
  subgraph Sources["数据来源"]
    Excel["Excel 能力矩阵"]
    Standard["职业标准"]
    JD["招聘 JD"]
    RSS["日报 RSS / 历史归档"]
    Resume["PDF / DOCX 简历"]
  end

  subgraph Data["数据处理与证据"]
    Raw["原始数据层"]
    Clean["清洗与标准化"]
    Evidence["证据层"]
    Signal["趋势信号"]
  end

  subgraph Intelligence["时间情报与预测"]
    Forecast["预测引擎"]
    Backtest["历史回测"]
    Suggestion["岗位影响建议"]
  end

  subgraph Jobs["岗位能力图谱"]
    Review["人工审核"]
    Version["已发布岗位版本"]
    Graph["岗位-技能-技能点图谱"]
  end

  subgraph Matching["候选人与交付"]
    Profile["候选人画像"]
    Match["匹配报告"]
    Learn["学习路径"]
  end

  Excel --> Clean
  Standard --> Clean
  JD --> Raw
  RSS --> Raw
  Resume --> Profile
  Raw --> Clean
  Clean --> Evidence
  Evidence --> Signal
  Signal --> Forecast
  Forecast --> Backtest
  Forecast --> Suggestion
  Suggestion --> Review
  Clean --> Review
  Review --> Version
  Version --> Graph
  Version --> Match
  Profile --> Match
  Match --> Learn

  classDef source fill:#f5f1e8,stroke:#aaa294,color:#20201d,stroke-width:1px
  classDef data fill:#eef3ff,stroke:#2457e6,color:#20201d,stroke-width:1px
  classDef evidence fill:#edf8f1,stroke:#17824b,color:#20201d,stroke-width:1px
  classDef signal fill:#fff5c8,stroke:#b18b00,color:#20201d,stroke-width:1px
  classDef formal fill:#20201d,stroke:#20201d,color:#fffdf8,stroke-width:1px
  classDef match fill:#eef3ff,stroke:#2457e6,color:#20201d,stroke-width:1px
  class Excel,Standard,JD,RSS,Resume source
  class Raw,Clean data
  class Evidence evidence
  class Signal,Forecast,Backtest,Suggestion signal
  class Review formal
  class Version,Graph formal
  class Profile,Match,Learn match
```

### 边界规则

- Excel 和职业标准提供能力本体与专家基线。
- 日报是技术先导信号，JD 是企业需求验证。
- 预测只生成 `JobImpactSuggestion`，不能直接发布岗位版本。
- 人岗匹配只接受 `CandidateProfile + PublishedJobVersion`。
- PostgreSQL 保存事实，Neo4j 保存图谱投影。

## 2. 数据处理流

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#ffffff","primaryTextColor":"#20201d","lineColor":"#77736b","fontFamily":"Inter, Noto Sans SC, Microsoft YaHei, sans-serif"},"flowchart":{"htmlLabels":false}}}%%
flowchart TB
  Raw["原始数据\nCSV / Markdown / RSS / PDF / DOCX"]
  Manifest["数据清单\n来源、哈希、时间、导入模式"]
  Staged["结构修复\n编码、字段、日期、格式修复"]
  Identity["身份与重复\n唯一标识、内容指纹、重复簇"]
  Role["岗位与等级\n岗位族、标准岗位、别名、等级"]
  Skill["技能归一化\n技能点、必备/加分"]
  Event["日报事件\n小节拆分、引用链接"]
  Evidence["证据\n原文片段、发布时间、质量、审核"]
  Curated["正式分析数据\n通过质量门"]
  Feature["时间特征\n日/周/月聚合和快照"]
  Run["运行产物\n输入、输出、提示词、指标、错误"]

  Raw --> Manifest --> Staged --> Identity
  Identity --> Role
  Identity --> Skill
  Identity --> Event
  Role --> Evidence
  Skill --> Evidence
  Event --> Evidence
  Evidence --> Curated --> Feature
  Staged --> Run
  Evidence --> Run
  Feature --> Run

  classDef raw fill:#f5f1e8,stroke:#aaa294,color:#20201d,stroke-width:1px
  classDef clean fill:#eef3ff,stroke:#2457e6,color:#20201d,stroke-width:1px
  classDef evidence fill:#edf8f1,stroke:#17824b,color:#20201d,stroke-width:1px
  classDef feature fill:#fff5c8,stroke:#b18b00,color:#20201d,stroke-width:1px
  classDef run fill:#20201d,stroke:#20201d,color:#fffdf8,stroke-width:1px
  class Raw,Manifest raw
  class Staged,Identity,Role,Skill,Event clean
  class Evidence,Curated evidence
  class Feature feature
  class Run run
```

### 数据层含义

```text
Raw        原始数据，只读，不覆盖
Staged     结构修复，可从 Raw 重建
Normalized 岗位、等级、技能标准化
Curated    通过质量门，可进入业务分析
Feature    时间聚合和模型输入
Run        一次清洗/预测/评测的可复现产物
```

## 3. 岗位决策流

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#ffffff","primaryTextColor":"#20201d","lineColor":"#77736b","fontFamily":"Inter, Noto Sans SC, Microsoft YaHei, sans-serif"},"flowchart":{"htmlLabels":false}}}%%
flowchart LR
  Baseline["专家能力基线\nExcel / 职业标准"]
  Market["市场需求\n招聘 JD"]
  Trend["趋势信号\n日报 / 技术生态"]
  Forecast["预测结果\n历史回测 / 未来预测"]
  Suggestion["岗位影响建议"]
  Review["审核动作\n接受 / 修改 / 拒绝"]
  Draft["岗位版本草稿"]
  Published["已发布岗位版本"]
  Graph["图谱投影\nNeo4j 图谱"]
  Candidate["候选人画像\n手工技能 / 简历"]
  Report["匹配报告\n差距和置信度"]
  Learning["学习路径\n学习顺序"]

  Baseline --> Draft
  Market --> Draft
  Trend --> Forecast
  Forecast --> Suggestion --> Review
  Market --> Suggestion
  Review --> Draft --> Published
  Published --> Graph
  Published --> Report
  Candidate --> Report --> Learning

  classDef baseline fill:#f5f1e8,stroke:#aaa294,color:#20201d,stroke-width:1px
  classDef market fill:#eef3ff,stroke:#2457e6,color:#20201d,stroke-width:1px
  classDef trend fill:#fff5c8,stroke:#b18b00,color:#20201d,stroke-width:1px
  classDef review fill:#fff5c8,stroke:#b18b00,color:#20201d,stroke-width:2px
  classDef formal fill:#20201d,stroke:#20201d,color:#fffdf8,stroke-width:1px
  classDef result fill:#edf8f1,stroke:#17824b,color:#20201d,stroke-width:1px
  class Baseline baseline
  class Market market
  class Trend,Forecast trend
  class Suggestion,Review review
  class Draft formal
  class Published,Graph formal
  class Candidate,Report,Learning result
```

### 发布规则

```text
预测建议 != 岗位事实
岗位草稿 != 正式版本
正式版本必须经过人工审核
匹配只能读取已发布版本
```

## 4. 运行入口

```text
Next.js 前端
  -> FastAPI API / SSE
  -> Application Use Case
  -> Domain Modules
  -> PostgreSQL / Neo4j / Object Storage / LLM Provider

hiro2 CLI
  -> 同一 Application Use Case
  -> data/runs/<run_id>/
```

前端用于业务操作和展示，CLI 用于数据检查、Agent 调试、历史回测、预测复盘和指标导出。两者不能各自实现一套业务逻辑。

## 5. 主要交付路径

```text
新岗位：信号 -> 候选 -> 证据 -> 人工定义 -> 岗位版本
岗位更新：两个时间窗 -> 新增/删除/修改 -> 证据 -> 新版本
人岗诊断：岗位版本 -> 简历/技能 -> 修正 -> 差距 -> 学习路径
历史回测：as_of_date -> 当时快照 -> 未来预测 -> 后验对比 -> 复盘
```

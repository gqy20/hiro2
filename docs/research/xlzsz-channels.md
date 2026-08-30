# 学练赛证数据渠道调研

> 本文只回答一个问题：学练赛证四段所需的证书、竞赛、知识点数据从哪些渠道抓、怎么抓。
> 调研时间：2026-08-30，全部端点实测验证。

## 背景

学练赛证是当前唯一没有实体数据支撑的主输出：`backend/matching/engine.py` 的
`learning_path()` 与 `backend/application/training.py` 的学练赛证四段均为字符串模板，
"证"段无真实证书、"赛"段无真实赛事。产品边界（product.md）：首期不接入课程或证书
平台，只用目录/标准类结构化数据做映射与推荐。

## 渠道总览

| 段 | 渠道 | 类型 | 通路 | 采集难度 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| 证 | 人社部国家职业标准（osta.org.cn） | 官方标准 | 公开 JSON API + PDF | 低 | P0 |
| 证 | 教育部 1+X 证书（ncb.edu.cn） | 官方目录 | 公开 JSON API（POST） | 低 | P0 |
| 证 | 讯飞 AI 大学堂认证（aidaxue.com） | 厂商认证 | SPA DOM 提取 | 中 | P0（发榜方叙事） |
| 证 | 华为职业认证（e.huawei.com） | 厂商认证 | 公开 JSON API | 低 | P1 |
| 证 | 阿里云认证（edu.aliyun.com） | 厂商认证 | DOM 提取 + 大纲文件下载 | 中 | P1 |
| 赛 | 讯飞 AI 开发者大赛（challenge.xfyun.cn） | 厂商赛事 | 公开 JSON API | 低 | P0（发榜方叙事） |
| 赛 | 阿里天池（tianchi.aliyun.com） | 平台赛事 | 公开 JSON API | 低 | P0 |
| 赛 | DataFountain（datafountain.cn） | 平台赛事 | 公开 JSON API | 低 | P1 |
| 赛 | Kaggle（kaggle.com） | 平台赛事 | 浏览器 DOM / 会话 API | 高（reCAPTCHA） | P2 |
| 赛 | 高教学会大学生竞赛目录 | 官方目录 | 新闻稿/PDF，人工整理 | 高（无 API） | P1（静态小数据） |

## 证——证书渠道详情

### 1. 人社部国家职业标准库（osta.org.cn）★核心

技能人才评价工作网"国家职业标准查询系统"，共 **702 条标准**（含历史版本），
覆盖大典全部职业。与项目已接入的 `dadianget.py`（职业分类大典 API）同一站点、
同一技术栈，无鉴权。

```text
列表   GET https://www.osta.org.cn/api/public/skillStandardList
       ?pageSize=50&pageNum=1&total=0&nameCode=<URL编码关键词>&status=1
       返回: id/name/code(职业编码)/issueTime(颁布时间)/issueNumber(发文号)
             standardInfo(PDF路径)/standardInfoName(文件名)
PDF    GET https://www.osta.org.cn/api/sys/downloadFile/decrypt
       ?fileName=<standardInfo 路径 URL 编码>
       注意: 必须 URL 编码，返回标准 PDF 原文件（1MB 左右）
```

已验证数字技术相关标准（nameCode 搜索）：

| 职业编码 | 标准名称 | 颁布 |
| --- | --- | --- |
| 2-02-10-09 | 人工智能工程技术人员 | 2021-09 |
| 4-04-05-05 | 人工智能训练师 | 2021-10 |
| 2-02-10-11 | 大数据工程技术人员 | 2021-02 |
| 2-02-10-12 | 云计算工程技术人员 | 2021-09 |
| 4-04-04-02 | 网络与信息安全管理员（数据安全管理员） | 2024-02 |
| 4-04-05-04 | 数据库运行管理员 | 2025-03 |
| 4-07-02-05 | 商务数据分析师 | 2024-02 |
| 4-04-02-01 | 信息通信网络机务员（数据中心运维） | 2025-12 |

PDF 内部结构（已抽样解析人工智能工程技术人员标准，59 页）：

```text
职业概况 / 基本要求 / 工作要求（按等级分节：
  职业功能 -> 工作内容 -> 专业能力要求 + 相关知识要求）/ 权重表
```

"工作要求"表就是官方鉴定的 **技能要求 + 知识要求** 粒度数据，直接服务"学"
（知识点树）与"证"（等级鉴定标准）；PyMuPDF 可解析（表格为文本层）。

编码差异备忘：项目 `new-occupations.yml` 里人工智能工程技术人员编码
2-02-38-01 为大典条目编码，标准库实际用 2-02-10-09，两套编码体系并存，
映射表需同时登记。

### 2. 教育部 1+X 职业技能等级证书（ncb.edu.cn）

职业教育国家学分银行门户，**证书 1237 条 + 等级标准 446 条**，无鉴权 POST JSON。

```text
证书   POST https://www.ncb.edu.cn/portal/exam/api/open/certificate/pubQuery
       {"pageNum":1,"pageSize":50,"certificateName":"人工智能"}
       返回: certificateId/certificateName/certificateDesc(简介)
             certificateGrade(初/中/高级)/xzhOrgName(颁证机构)/stateDt
标准   POST https://www.ncb.edu.cn/portal/exam/api/open/standard/open/query
       {"pageNum":1,"pageSize":50,"standardName":"人工智能"}
       返回: standardId/standardCode/standardName/xzhOrgName/stateDt
             standardUrl(JSON 字符串，含 fileKey 文档路径)/certInfos(对应证书分级)
```

AI 相关实测 13 张证书：讯飞"人工智能数据处理/语音应用开发"（初/中/高级，2023）、
百度"深度学习工程应用"、新奥时代"前端设备应用"等。证书简介文本质量高，
直接描述面向岗位与技能。标准文档（docx/pdf）fileKey 的下载通路未验证，
首期用目录+简介即可。

### 3. 讯飞 AI 大学堂认证（aidaxue.com/certification）★发榜方叙事

Nuxt SPA，认证卡片数据由 CMS 接口渲染，无独立公开 API，用 agent-browser DOM 提取
（页面结构稳定，一张页拿全）。

双轨认证体系：

```text
大学堂专项（免费，线上考，电子证）:
  Prompt 工程师认证 —— 指令入口、大模型对话与内容创作、结构化提示词
  微调工程师认证   —— 零代码/低代码定制、LoRA/QLoRA 参数高效微调
  智能体工程师认证 —— AI Agent 开发、Multi-Agent 协同、Workflow 范式
  RAG 工程师认证   —— 私域知识库、向量数据库检索、重排序
工信部教考中心 × 讯飞（纸质证，初/中/高三级）:
  AI 大模型应用工程师职业技术认证 —— 内容创作/RAG 系统/智能体开发
```

与项目能力域对应关系极佳：cap_02 Prompt工程、cap_03 模型微调、cap_04 AI Agent、
cap_06 RAG/知识库几乎一一对应，且发榜方年报直接提及该证书（market-fit.md 已引用）。

### 4. 华为职业认证（apigw-04.huawei.com）

华为人才在线职业认证全景数据，**108 个认证**（HCIA/HCIP/HCIE 三级体系），
公开 JSON 无鉴权（需浏览器 UA）：

```text
GET https://apigw-04.huawei.com/api/services/lras/ecms/v1/getProfessionalCertification
    ?a2Flag=N&X-HW-ID=com.huawei.prm.talent&env=&language=zh_CN
返回 86KB 树形: 大类(如 ICT技术架构) -> 技术方向 -> hciaList/hcipList/hcieList
每个认证: certifiedProductName(HCIA-AI)/certifiedProductFullname/关联考试代码/
          amount(费用)/考试时长/introduction(能力描述)/prerequisites(先修建议)
```

AI 方向 9 个认证：HCIA-AI、HCIA-AI Solution、HCIP-AI-Model/Application/EI/MindSpore
Developer、HCIP-AI Solution Architect、HCIE-AI Developer、HCIE-AI Solution
Architect。introduction 字段含能力描述（如 HCIE-AI Developer 的"RAG 与 Agent 应用
开发与性能优化"），可直接做技能映射证据。

### 5. 阿里云认证（edu.aliyun.com/certification）

列表页 DOM 提取（认证卡 `a[href*="/certification/aca|acp|ace"]`）：
大模型工程师 ACA（600 元）/大模型高级工程师 ACP（1200 元）/云计算 ACA/ACP/ACE/
大数据 ACA/ACP。详情页含完整课程大纲（aca13 大模型 ACA：认识大模型/用好大模型/
Agent/RAG/微调/安全合规 11 课时），考试大纲文件可下载
（`/public_file/download/<hash>`，V2.4）。

## 赛——竞赛渠道详情

### 6. 讯飞 AI 开发者大赛（challenge.xfyun.cn）★发榜方叙事

2026 届正在进行，历史全量 API 可翻页（含往届，时间跨度适合做趋势分析）：

```text
行业分类 GET https://challenge.xfyun.cn/2020/ai-contest/api/industry/all
         返回 30 个分类（语音/Skill开发/数据挖掘/大模型/CV/多模态/NLP...）
赛题列表 GET https://challenge.xfyun.cn/2020/ai-contest/api/contests/contests-list
         ?typeBasicProblem=algorithem|application&curPage=1&pageSize=100
         返回: name_basic_problem(赛题名)/industry(行业)/sponsorName(主办方)/
               bonus(奖金)/registerBegin~finalEnd(报名/初赛/决赛时间)/
               team_count(队数)/desc(赛题描述)/contest_flag(赛题代号)
```

实测算法赛 38 页 + 应用赛 30 页（含往届），2026 届进行中赛题如"智能办公协同助理
Skill 开发挑战赛"（8312 队，讯飞主办）。行业分类与能力域映射天然对齐
（大模型技术→cap_01、计算机视觉→cap_05 等）。

### 7. 阿里天池（tianchi.aliyun.com）

```text
GET https://tianchi.aliyun.com/v3/proxy/competition/api/race/page
    ?visualTab=&raceName=&pageNum=1&isActive=
返回: raceId/raceName(内嵌列表)/bonus/teamCount/signup与race起止时间/
      tagsList(医疗健康/NLP/大语言模型等标签)/highlight(亮点，如"证书+评测论文")
```

无鉴权直连。`isActive` 参数可区分进行中/往届。

### 8. DataFountain（datafountain.cn）

```text
GET https://www.datafountain.cn/api/competitions?pageNum=1&pageSize=100
返回: id/title/startTime/endTime/reward(奖金)/teams/users/
      tags(图像分割等技能标签)/industries/organizers(主办方及角色)
```

无鉴权直连，返回字段最规整（tags 直接是技能标签体系）。

### 9. Kaggle（kaggle.com）

curl 直接访问被 reCAPTCHA 拦截；浏览器内两条通路已验证：
- DOM 提取：`a[href*="/competitions/"]` 卡片（标题/团队数/截止时间/category）
- 会话 API：`POST /api/i/competitions.CompetitionService/ListCompetitions`
  （浏览器 fetch 带 cookie 可用，纯 curl 不行）

国际赛事覆盖，优先级最低；国内三平台已够撑"赛"段。

### 10. 中国高等教育学会大学生竞赛目录

cahe.edu.cn 可访问，但竞赛目录以新闻稿/PDF 附件形式发布（无结构化 API），
全国普通高校大学生竞赛目录共 56/57 项，数量小且年度更新慢，
**人工整理成 YAML 是最优解**（同 new-occupations.yml 模式，无需抓取脚本）。

## 采集方案建议

### 脚本规划（遵循 10 字符命名规范）

```text
certget.py   证书采集 CLI（osta 标准库 + 1+X + 华为三个 JSON 源）
raceget.py   竞赛采集 CLI（讯飞大赛 + 天池 + DataFountain）
certparse.py 标准 PDF 解析（PyMuPDF 提取工作要求表 -> 知识点/鉴定点）
```

### 数据落点

```text
data/raw/certs/          证书与标准原始快照（JSON 响应 + 标准 PDF）
data/raw/races/          竞赛原始快照
data/processed/certs/    norm-cert.jsonl（归一化证书目录）
data/processed/races/    norm-race.jsonl（归一化竞赛目录）
data/CERTS.yml           证书 <-> cap_XX 技能点映射（人工审核后，仿 SKILLS.yml）
data/CONTESTS.yml        竞赛 <-> cap_XX 映射 + 获奖等级->L1/L2/L3 换算规则
```

### 映射规则设计要点

1. 每条证书/竞赛登记 `capability_ids`（可多值）+ `evidence_url` + `effective_from`
   （证书颁布日期/赛事首办年份，天然适配现有时间闸门）。
2. 讯飞认证的卡片文案即知识域声明（如 RAG 认证=向量数据库+检索+重排序），
   映射人工一次定稿；osta 标准的"工作要求"表可用 LLM 辅助映射到技能点，
   走 review 队列。
3. 竞赛等级换算建议（写进 CONTESTS.yml，可版本化）：
   国家级一等奖 L3 / 二三等奖 L2.5 / 省级金奖 L2 / 银铜 L1.5 / 完赛 L1；
   厂商赛（讯飞/天池）按 team_count 百分位校正。
4. raw 目录只保存快照和 manifest（SOURCES.yml 登记新来源），映射结论进
   CERTS/CONTESTS.yml 时人工签核，符合"业务事实必须有版本、来源和审核状态"。

### 与现有系统的对接点

- `learning_path()` 的 certify/evaluate 段从模板字符串改为查 CERTS/CONTESTS.yml，
  按 gap.skill_id 反查推荐真实证书与赛事；
- 匹配引擎 judge() 增加"证书证据"分支：简历出现证书 mention 时经 CERTS.yml
  反查 skill_id 判"已具备"（证据=证书名）；
- standards PDF 的"工作要求"表作为"学"段知识点树来源（certparse 产物）；
- 全部渠道均为公开目录数据，不违反"不接入课程/证书平台"边界。

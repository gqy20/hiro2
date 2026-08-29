# 数据字典

> 范围：核心产物的字段类型、含义、来源与质量规则。由 `scripts/datadict.py run` 扫描生成，
> 语义标注内联于脚本；`TODO 待人工补` 为未标注字段。类型从样本推断，仅供参考。

## 日报事件 events

产物：`data/processed/wechat-mp/events.jsonl` · 生成：`extract.py (prompt v3)`

| 字段 | 类型 | 含义 / 质量规则 |
| --- | --- | --- |
| `event_type` | str | 事件类型枚举：研究/规范发布/模型发布/开源/产品化/采用/政策/传闻 |
| `title` | str | TODO 待人工补 |
| `summary` | str | TODO 待人工补 |
| `entities` | list[str] | 事件涉及实体（公司/产品/机构，LLM 抽取） |
| `fact_grade` | str | 事实分级 fact|report|opinion（质量规则：加权 1.0/0.6/0.3） |
| `urls` | list[str] | 原文引用链接（回链用） |
| `skill_mentions` | list[str] | 技能原词列表（未归一） |
| `event_id` | str | 事件唯一标识（item_id + 序号） |
| `item_id` | str | 来源文章标识（索引内=guid，未索引=文件哈希） |
| `published_at` | str | 发布时间（天粒度；未索引文章回退文件名日期） |
| `prompt_version` | int | TODO 待人工补 |
| `model_version` | str | TODO 待人工补 |
| `duplicate_group_id` | NoneType | TODO 待人工补 |
| `is_primary` | bool | TODO 待人工补 |
| `duplicate_reason` | NoneType | TODO 待人工补 |

## JD 解析 jd-parsed

产物：`data/processed/jd-opencli/jd-parsed.jsonl` · 生成：`jdxtract.py (jd-skill v2)`

| 字段 | 类型 | 含义 / 质量规则 |
| --- | --- | --- |
| `jd_id` | str | 岗位唯一标识（平台内 id 或哈希） |
| `is_ai_role` | bool | TODO 待人工补 |
| `domain_reason` | str | TODO 待人工补 |
| `platform` | str | 采集平台（51job/boss/bytedance/tencent/gh-* 等） |
| `title` | str | 岗位标题（51job 曾按 jobId join 修复） |
| `publish_date` | str | 发布日期（boss 无；corp 毫秒精度截断到天） |
| `city` | str | TODO 待人工补 |
| `work_year` | str | TODO 待人工补 |
| `salary` | str | TODO 待人工补 |
| `responsibilities` | list[str] | TODO 待人工补 |
| `requirements` | list[str] | 任职要求（[必备]/[加分] 标记） |
| `skill_mentions` | list[str] | 技能原词；resolved=归一结果（asof 版按发布日词典重算） |
| `resolved` | list | TODO 待人工补 |
| `unresolved` | list[str] | TODO 待人工补 |
| `rule_version` | int | TODO 待人工补 |
| `prompt_version` | int | TODO 待人工补 |
| `model_version` | str | TODO 待人工补 |

## 证据实体 evidence

产物：`data/processed/evidence/evidence.jsonl` · 生成：`evidence.py build`

| 字段 | 类型 | 含义 / 质量规则 |
| --- | --- | --- |
| `evidence_id` | str | ev:|jd:|xlsx: 前缀 + 源标识（回链键） |
| `source_id` | str | TODO 待人工补 |
| `source_span` | dict | 回链定位（event_id/jd_id/position_id） |
| `published_at` | str | 证据时间（as_of 闸门的 T 锚点） |
| `content_hash` | str | 内容哈希 16 位（幂等重建校验） |
| `claim_type` | str | trend_signal|job_requirement|expert_baseline |
| `payload` | dict | 主张载荷（title/event_type/skill_mentions 等按 claim_type 变化） |
| `quality_score` | float | 质量分（事实分级映射；JD 0.8 恒定） |
| `urls` | list[str] | TODO 待人工补 |

## 证据关系 relations

产物：`data/processed/evidence/relations.jsonl` · 生成：`evrelate.py run`

| 字段 | 类型 | 含义 / 质量规则 |
| --- | --- | --- |
| `relation_id` | str | 关系唯一标识（版本+源+技能） |
| `evidence_id` | str | TODO 待人工补 |
| `target` | dict | job_version_skill（版本技能字段）| expert_baseline_skill |
| `direction` | str | supports|contradicts（规则化，零 LLM） |
| `rule` | str | 关系生成规则名（可审计） |

## 岗位版本 published

产物：`data/processed/jobversions/published/` · 生成：`jobver.py + jobpub.py`

| 字段 | 类型 | 含义 / 质量规则 |
| --- | --- | --- |
| `job_id` | str | TODO 待人工补 |
| `version_id` | str | TODO 待人工补 |
| `status` | str | PUBLISHED（发布后不可变） |
| `title` | str | TODO 待人工补 |
| `basis` | dict | TODO 待人工补 |
| `required_skill_ids` | list[dict] | TODO 待人工补 |
| `preferred_skill_ids` | list[dict] | TODO 待人工补 |
| `valid_from` | str | 生效日期（时间闸门消费） |
| `evidence` | dict | TODO 待人工补 |
| `changeset_vs_v1` | list[dict] | 对基线的变化（add/promote/demote；evrelate 的 contradicts 来源） |
| `review_status` | str | PUBLISHED（发布后不可变） |
| `generated_by` | str | TODO 待人工补 |
| `generated_at` | str | TODO 待人工补 |
| `published_at` | str | TODO 待人工补 |
| `reviewer` | str | TODO 待人工补 |
| `review_note` | str | TODO 待人工补 |
| `review_action_ids` | list[str] | 审核留痕引用（review-actions.jsonl） |
| `version_hash` | str | 发布后不可变哈希（幂等保护） |

## 包信号 relsignal

产物：`data/processed/pypi/relsignal.json` · 生成：`pypidl.py run`

| 字段 | 类型 | 含义 / 质量规则 |
| --- | --- | --- |
| `rows` | list[dict] | TODO 待人工补 |
| `pkg_meta` | dict | TODO 待人工补 |
| `params` | dict | TODO 待人工补 |

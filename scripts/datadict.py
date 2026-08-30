"""datadict: D0 数据字典——扫描核心产物字段，生成 docs/data-dictionary.md。

字段类型从样本推断，含义/来源/质量规则来自管线知识内联标注（SEM 注释表），
未标注字段标 TODO 待人工补。幂等重建。
用法：uv run scripts/datadict.py run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data-dictionary.md"

# 数据集 -> (产物路径, 生成脚本, 语义标注 {字段: 含义|质量规则})
DATASETS = OrderedDict(
    [
        (
            "日报事件 events",
            (
                "data/processed/wechat-mp/events.jsonl",
                "extract.py (prompt v3)",
                {
                    "event_id": "事件唯一标识（item_id + 序号）",
                    "item_id": "来源文章标识（索引内=guid，未索引=文件哈希）",
                    "title/summary": "事件标题与摘要（LLM 抽取）",
                    "entities": "事件涉及实体（公司/产品/机构，LLM 抽取）",
                    "urls": "原文引用链接（回链用）",
                    "published_date": "原始发布日期字段（已由 published_at 统一替代）",
                    "event_type": "事件类型枚举：研究/规范发布/模型发布/开源/产品化/采用/政策/传闻",
                    "fact_grade": "事实分级 fact|report|opinion（质量规则：加权 1.0/0.6/0.3）",
                    "skill_mentions": "技能原词列表（未归一）",
                    "published_at": "发布时间（天粒度；未索引文章回退文件名日期）",
                    "is_primary/duplicate_group_id": "D2 去重标记；下游只消费 is_primary 主记录",
                },
            ),
        ),
        (
            "JD 解析 jd-parsed",
            (
                "data/processed/jd-opencli/jd-parsed.jsonl",
                "jdxtract.py (jd-skill v2)",
                {
                    "jd_id": "岗位唯一标识（平台内 id 或哈希）",
                    "is_ai_role/domain_reason": "AI 域判定及理由（staged 全留，curated 按此过滤）",
                    "skill_mentions": "技能原词；resolved=归一结果（asof 版按发布日词典重算）",
                    "platform": "采集平台（51job/boss/bytedance/tencent/gh-* 等）",
                    "title": "岗位标题（51job 曾按 jobId join 修复）",
                    "city/work_year/salary": "城市/经验/薪资元数据（corp 源较完整）",
                    "requirements": "任职要求（[必备]/[加分] 标记）",
                    "publish_date": "发布日期（boss 无；corp 毫秒精度截断到天）",
                },
            ),
        ),
        (
            "证据实体 evidence",
            (
                "data/processed/evidence/evidence.jsonl",
                "evidence.py build",
                {
                    "evidence_id": "ev:|jd:|xlsx: 前缀 + 源标识（回链键）",
                    "source_span": "回链定位（event_id/jd_id/position_id）",
                    "claim_type": "trend_signal|job_requirement|expert_baseline",
                    "content_hash": "内容哈希 16 位（幂等重建校验）",
                    "quality_score": "质量分（事实分级映射；JD 0.8 恒定）",
                    "payload": "主张载荷（title/event_type/skill_mentions 等按 claim_type 变化）",
                    "published_at": "证据时间（as_of 闸门的 T 锚点）",
                },
            ),
        ),
        (
            "证据关系 relations",
            (
                "data/processed/evidence/relations.jsonl",
                "evrelate.py run",
                {
                    "direction": "supports|contradicts（规则化，零 LLM）",
                    "target": "job_version_skill（版本技能字段）| expert_baseline_skill",
                    "supporting_evidence_ids": "contradicts 的真实 JD 证据引用（<=5 条）",
                    "relation_id": "关系唯一标识（版本+源+技能）",
                    "rule": "关系生成规则名（可审计）",
                },
            ),
        ),
        (
            "岗位版本 published",
            (
                "data/processed/jobversions/published/",
                "jobver.py + jobpub.py",
                {
                    "required_skill_ids/preferred_skill_ids": "必备/加分技能（skill_id+weight）",
                    "evidence.evidence_ids": "版本引用的 JD 证据（evrelate 验证 100% 字段覆盖）",
                    "version_hash": "发布后不可变哈希（幂等保护）",
                    "changeset_vs_v1": "对基线变化（add/promote/demote；contradicts 来源）",
                    "status": "PUBLISHED（发布后不可变）",
                    "valid_from": "生效日期（时间闸门消费）",
                    "review_action_ids": "审核留痕引用（review-actions.jsonl）",
                },
            ),
        ),
        (
            "包信号 relsignal",
            (
                "data/processed/pypi/relsignal.json",
                "pypidl.py run",
                {
                    "dl_share_onset": "下载份额启动月（ClickHouse 月度聚合，域内份额抗通胀）",
                    "rel_onset": "首发月中位（萌芽锚点）",
                    "jd_onset": "JD 需求启动月（asof 版词典）",
                    "report_onset": "日报信号启动月",
                },
            ),
        ),
        (
            "证书目录 cert-catalog",
            (
                "data/processed/certs/cert-catalog.jsonl",
                "certget.py norm",
                {
                    "cert_id": "证书唯一标识（osta-std-<编码>|onex-<id>|hw-<name>）",
                    "type": "national_standard|onex_certificate|vendor_cert",
                    "issuer": "颁发机构（匹配引擎证书证据的回链目标）",
                    "effective_from": "颁发/发布日期（时间闸门锚点）",
                    "level": "证书等级（初/中/高级；华为 hcia/hcip/hcie）",
                    "career_code": "osta 职业编码（标准库编码体系，与大典编码并存）",
                    "source": "osta|onex|huawei（三源公开 JSON 采集）",
                },
            ),
        ),
        (
            "竞赛目录 race-catalog",
            (
                "data/processed/races/race-catalog.jsonl",
                "raceget.py norm",
                {
                    "race_id": "赛事唯一标识（xfyun-<flag>|tianchi-<id>|df-<id>）",
                    "industry": "平台行业分类（讯飞：大模型/CV/NLP/Skill 开发等，与能力域对齐）",
                    "bonus/team_count": "奖金与参赛队数（热度信号）",
                    "register_end": "报名截止（进行中判定）",
                    "tags": "平台技能标签（天池/DF；零宽字符已清洗）",
                    "source": "xfyun|tianchi|datafountain",
                },
            ),
        ),
        (
            "标准工作要求 std-requirements",
            (
                "data/processed/certs/std-requirements/",
                "certparse.py parse-all",
                {
                    "level": "等级分离（工程师类：初/中/高；技能类：五级-初级工等）",
                    "func": "职业功能（如：人工智能共性技术应用）",
                    "work_no/work": "工作内容编号与名称；work 列边界尽力解析，宽表跨页或混入"
                    "相邻列；学段只消费干净的 knowledge，不展示 work",
                    "skills": "专业能力要求条目（编号前缀对齐，官方鉴定粒度）",
                    "knowledge": "相关知识要求条目（知识点树来源，干净无乱码，零 LLM 确定性解析）",
                },
            ),
        ),
    ]
)

TODO = "TODO 待人工补"


def _scan_fields(path: Path) -> dict[str, str]:
    """首行/首文件样本推断字段类型。"""
    first = None
    if path.is_dir():
        files = sorted(path.glob("*.json"))
        if not files:
            return {}
        first = json.loads(files[0].read_text(encoding="utf-8"))
    elif path.exists():
        text = path.open(encoding="utf-8").readline()
        if path.suffix == ".jsonl":
            first = json.loads(text)
        else:  # 多行 JSON（indent 格式）读全文
            first = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(first, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in first.items():
        t = type(v).__name__
        if isinstance(v, list) and v:
            t = f"list[{type(v[0]).__name__}]"
        out[k] = t
    return out


def cmd_run() -> dict:
    run = RunContext("datadict", {"cmd": "run"})
    lines = [
        "# 数据字典",
        "",
        "> 范围：核心产物的字段类型、含义、来源与质量规则。由 `scripts/datadict.py run` 扫描生成，",
        "> 语义标注内联于脚本；`TODO 待人工补` 为未标注字段。类型从样本推断，仅供参考。",
        "",
    ]
    n_fields = n_annotated = 0
    for name, (rel, producer, sem) in DATASETS.items():
        fields = _scan_fields(ROOT / rel)
        if not fields:
            continue
        lines += [
            f"## {name}",
            "",
            f"产物：`{rel}` · 生成：`{producer}`",
            "",
            "| 字段 | 类型 | 含义 / 质量规则 |",
            "| --- | --- | --- |",
        ]
        matched = set()
        for f, t in fields.items():
            note = TODO
            for key, desc in sem.items():
                if key == f or (key in f and len(key) > 3):
                    note, _ = desc, matched.add(key)
                    break
            n_fields += 1
            n_annotated += note != TODO
            lines.append(f"| `{f}` | {t} | {note} |")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    metrics = {
        "datasets": len(DATASETS),
        "fields": n_fields,
        "annotated": n_annotated,
        "todo": n_fields - n_annotated,
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datadict")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    print(json.dumps(cmd_run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

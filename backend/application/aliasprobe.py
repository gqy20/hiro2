"""aliasprobe: 词表新词闭环——从数据流发现词典外语言，经 agent 查证生成词表提议。

闭环（docs/competition.md 词表演进）：
  信源一（滞后确定）：unmatched JD 标题关键词聚类——3492 条 unmatched 是
    词典外语言的富矿，高频片段即新词候选；
  信源二（先导预警）：日报事件 skill_mentions 月度突增——时间传导轴证明
    日报先导 JD 5~7 年，"日报爆发、JD 未成词"的新词可提前预备条目。
       ↓ 两路汇合为候选簇
  提议 agent（governed loop）：查证岗位职责 + 回读样本 JD 职责，
    产出 AliasSuggestion（新别名 -> 目标岗位 + 证据 + 置信）；
  人工审核 -> TITLE_ALIASES 生效 -> rolemap repair 零成本重跑 -> evalcmp 验证。

边界：提议只是候选，agent 不改词表；与 evalloop 共用治理通道。
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

REPAIRED = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map-repaired.jsonl"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"

# 扫描参数：候选词门槛（低于此频次无统计意义）
MIN_JD_FREQ = 5
MIN_EVENT_MONTHS = 3  # 突增词至少出现月数
SURGE_RATIO = 3.0  # 近 3 月频次 / 历史月均 >= 该值视为突增
SURGE_MIN_COUNT = 5  # 突增窗口内绝对条数下限


class AliasCandidate(BaseModel):
    """一个新词候选簇（确定性扫描产物，未经 agent 查证）。"""

    term: str
    source: str  # unmatched_jd | event_surge
    jd_freq: int = 0
    event_recent: int = 0  # 近 3 月日报提及数
    sample_jd_ids: list[str] = Field(default_factory=list)
    sample_titles: list[str] = Field(default_factory=list)


class AliasSuggestion(BaseModel):
    """词表提议（提议 agent 的 output_model）——人工审核入口。"""

    term: str
    action: str  # add_alias | new_position_signal | reject
    target_position: str | None = None  # add_alias 时的目标岗位名
    confidence: float = 0.0
    rationale: str = ""
    evidence_jd_ids: list[str] = Field(default_factory=list)
    risk: str = ""


# ---------------------------------------------------------------- 已覆盖判定


def _covered_terms() -> set[str]:
    """当前词表已覆盖的全部词（别名 key、商务信号、岗位名，去空格小写）。"""
    from rolemap import BIZ_SIGNALS, TITLE_ALIASES

    covered = {a.replace(" ", "").lower() for a in TITLE_ALIASES}
    covered |= {s.replace(" ", "").lower() for s in BIZ_SIGNALS}
    return covered


def _is_covered(term: str, covered: set[str], position_names: list[str]) -> bool:
    """候选词已被覆盖 = 它是某别名的子串、或出现在任何岗位名中。

    匹配是子串逻辑：候选 "post training" 若岗位名/别名含它或它含某个
    更短的已有别名（如 "training"），实际都会被现有规则接住。
    """
    t = term.replace(" ", "").lower()
    if t in covered:
        return True
    if any(t in c or c in t for c in covered):
        return True
    return any(t in n.replace(" ", "").lower() for n in position_names)


# ---------------------------------------------------------------- 信源一：unmatched JD


def probe_unmatched_jd(min_freq: int = MIN_JD_FREQ) -> list[AliasCandidate]:
    """聚类 unmatched JD 标题的高频词典外关键词。

    复用 emergscan._keywords（英文 n-gram + 全大写缩写 + 中文连续段 + 停用词）。
    """
    from emergscan import _keywords

    covered = _covered_terms()
    from backend.application.evalaudit import POOLS

    POOLS.load()
    assert POOLS.positions is not None
    position_names = [p["name"] for p in POOLS.positions.values()]

    term_jds: dict[str, list[tuple[str, str]]] = defaultdict(list)
    n_unmatched = 0
    for line in REPAIRED.open(encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("method") != "unmatched":
            continue
        n_unmatched += 1
        title = rec.get("title") or ""
        for kw in _keywords(title):
            if len(kw) < 2 or _is_covered(kw, covered, position_names):
                continue
            term_jds[kw].append((rec["jd_id"], title))

    cands = [
        AliasCandidate(
            term=term,
            source="unmatched_jd",
            jd_freq=len(jds),
            sample_jd_ids=[j for j, _ in jds[:8]],
            sample_titles=[t[:40] for _, t in jds[:5]],
        )
        for term, jds in term_jds.items()
        if len(jds) >= min_freq
    ]
    cands.sort(key=lambda c: -c.jd_freq)
    print(f"信源一：unmatched {n_unmatched} 条 -> 词典外高频词 {len(cands)} 个（>= {min_freq} 次）")
    return cands


# ---------------------------------------------------------------- 信源二：日报技能突增


def _parse_month(s: str | None) -> str | None:
    return (s or "")[:7] if s else None


def probe_event_surges() -> list[AliasCandidate]:
    """日报 skill_mentions 月度突增检测：先导新词（JD 侧尚未成词）。

    突增判据：近 3 月频次 / 历史月均 >= SURGE_RATIO 且窗口绝对数 >= SURGE_MIN_COUNT；
    仅保留词典外词（JD 侧已覆盖的不需要预警）。
    """
    covered = _covered_terms()
    from backend.application.evalaudit import POOLS

    POOLS.load()
    assert POOLS.positions is not None
    position_names = [p["name"] for p in POOLS.positions.values()]

    monthly: dict[str, Counter] = defaultdict(Counter)
    for line in EVENTS.open(encoding="utf-8"):
        ev = json.loads(line)
        month = _parse_month(ev.get("published_at"))
        if not month:
            continue
        for skill in ev.get("skill_mentions") or []:
            monthly[skill][month] += 1

    # 近 3 月窗口取数据中最新月份
    all_months = sorted({m for c in monthly.values() for m in c})
    if len(all_months) < MIN_EVENT_MONTHS + 1:
        return []
    recent_window = all_months[-3:]
    history = all_months[:-3]

    cands: list[AliasCandidate] = []
    for skill, by_month in monthly.items():
        if _is_covered(skill, covered, position_names):
            continue
        recent = sum(by_month.get(m, 0) for m in recent_window)
        if recent < SURGE_MIN_COUNT:
            continue
        hist_avg = (sum(by_month.get(m, 0) for m in history) / len(history)) if history else 0.0
        if hist_avg > 0 and recent / hist_avg < SURGE_RATIO:
            continue
        if hist_avg == 0 and sum(1 for m in recent_window if by_month.get(m)) < MIN_EVENT_MONTHS:
            continue  # 零星出现不满 3 个月的新词，等成熟
        cands.append(
            AliasCandidate(
                term=skill,
                source="event_surge",
                event_recent=recent,
            )
        )
    cands.sort(key=lambda c: -c.event_recent)
    print(
        f"信源二：日报技能突增（{recent_window[0]}~{recent_window[-1]}）-> 预警词 {len(cands)} 个"
    )
    return cands


def probe_all() -> list[AliasCandidate]:
    """两路信源汇合：unmatched 高频词优先，日报预警去重后附加。"""
    cands = probe_unmatched_jd()
    seen = {c.term for c in cands}
    for c in probe_event_surges():
        if c.term not in seen:
            cands.append(c)
    return cands


# ---------------------------------------------------------------- 提议 agent


async def propose_aliases(
    porter: Any,
    candidates: list[AliasCandidate],
    run_dir: Path,
    *,
    budget: Any = None,
) -> tuple[list[AliasSuggestion] | None, Any]:
    """提议 agent：逐簇查证 -> 一份汇总提议列表（AliasSuggestion 列表）。

    与 evalloop 同款形态：必读材料内联、lookup 工具按需查证、submit 出口。
    """
    from backend.application.evalaudit import POOLS, JdQuery, PositionQuery
    from backend.infra.llm.agent import TokenBudget, ToolSpec, run_agent
    from backend.infra.llm.promptspec import load_prompt

    def lookup_position(position_id: str) -> str:
        POOLS.load()
        assert POOLS.positions is not None
        p = POOLS.positions.get(position_id)
        if p is None:
            return f"未找到岗位 {position_id}"
        return json.dumps(
            {
                "position_id": p["position_id"],
                "name": p["name"],
                "summary": (p.get("summary") or "")[:300],
            },
            ensure_ascii=False,
        )

    def lookup_jd(jd_id: str) -> str:
        POOLS.load()
        assert POOLS.parsed is not None
        jd = POOLS.parsed.get(jd_id)
        if jd is None:
            return f"未找到 JD {jd_id}"
        return json.dumps(
            {
                "title": jd.get("title"),
                "responsibilities": (jd.get("responsibilities") or [])[:4],
                "skill_mentions": (jd.get("skill_mentions") or [])[:8],
            },
            ensure_ascii=False,
        )

    def submit(**kwargs: Any) -> str:  # pragma: no cover - exit_tool 不真正执行
        return "已提交"

    class SubmitArgs(BaseModel):
        suggestions: list[AliasSuggestion]

    tools = [
        ToolSpec(
            name="lookup_position",
            description="按 position_id 查标准岗位职责说明",
            args_model=PositionQuery,
            func=lookup_position,
        ),
        ToolSpec(
            name="lookup_jd",
            description="按 jd_id 查样本 JD 的职责与技能，判断新词语义归属",
            args_model=JdQuery,
            func=lookup_jd,
        ),
        ToolSpec(
            name="submit",
            description="提交全部提议（唯一出口）",
            args_model=SubmitArgs,
            func=submit,
        ),
    ]
    spec = load_prompt("alias-propose")
    cand_text = "\n".join(
        f"- {c.term}（来源={c.source}, JD频次={c.jd_freq}, "
        f"近3月日报={c.event_recent}, 样本JD={','.join(c.sample_jd_ids[:3])}）"
        for c in candidates[:30]  # 上下文控制：最多 30 簇
    )
    task = (
        f"对以下词典外新词逐个判断归属，产出词表提议：\n{cand_text}\n\n"
        f"流程：对每个词用 lookup_jd 抽查 2-3 条样本 JD 的职责 -> 需要时 lookup_position "
        f"核对候选岗职责 -> 给出 action：add_alias（写明 target_position 标准岗位全名）/ "
        f"new_position_signal（46 岗都对不上，应走新岗位流）/ reject（噪声词或语义太泛）。"
    )
    result = await run_agent(
        porter=porter,
        spec=spec,
        tools=tools,
        task=task,
        output_model=SubmitArgs,
        run_dir=run_dir,
        max_steps=10,
        budget=budget or TokenBudget(total_tokens=80000),
        exit_tool="submit",
    )
    if result.output is None:
        return None, result
    suggestions = SubmitArgs.model_validate(result.output).suggestions
    return suggestions, result

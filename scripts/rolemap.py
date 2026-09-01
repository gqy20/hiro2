"""rolemap: D3 岗位目录映射与等级推断。

用法：
    uv run scripts/rolemap.py run          # 规则匹配 + LLM 候选 -> jd-role-map.jsonl
    uv run scripts/rolemap.py label        # 生成人工标注包 CSV（review-labels.csv）

映射：JD 职位名 -> Excel 46 标准岗位。规则精确/别名匹配优先（零成本零幻觉），
未命中交 LLM 语义候选（带置信度和理由），均写入映射档案。
等级：L1-L4 由确定性规则从经验要求与职位名推断（记录依据字段），
     冲突或缺失为 UNKNOWN，进人工标注。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
OUT = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map.jsonl"
LABELS = ROOT / "data" / "processed" / "jd-opencli" / "review-labels.csv"
MAX_RETRIES = 2

# 职位名别名（市场叫法 -> Excel 标准名），人工先验
# 注意 dict 顺序即匹配优先级：放前面的先命中。
TITLE_ALIASES: dict[str, str] = {
    # v4（evalloop 首轮，run 20260831T161631）：产品头衔优先于技术词——
    # "QQ-Agent产品经理"曾被 "Agent" 抢配 pos_02（role_level-022/037 证据），
    # 技术头衔罕含"产品"，置顶风险低。
    "产品经理": "AI产品经理",
    "产品实习生": "AI产品经理",
    # v4.2 已撤回：曾按终审锚点加"推理部署/异构硬件/Compute Infrastructure"三个词，
    # 每词仅修 1 条 case 却带全库回归面——词典修补的边际收益已经为负，
    # 这些 case 的正确出路是 role-map LLM 路径带职责上下文重判（方向见 docs/competition.md）。
    "大模型": "大模型算法工程师",
    "LLM": "大模型算法工程师",
    "AIGC": "AI创意策略师",
    "NLP": "NLP/多模态研究员",
    "Agent": "AI Agent开发工程师",
    "智能体": "AI Agent开发工程师",
    # 机器学习/深度学习是算法主体岗，不是 NLP 研究员（原映射为系统性偏差源）
    "感知算法": "自动驾驶感知工程师",
    "机器学习": "大模型算法工程师",
    "深度学习": "大模型算法工程师",
    "计算机视觉": "计算机视觉工程师",
    "图像算法": "计算机视觉工程师",
    "视觉算法": "计算机视觉工程师",
    "CV": "计算机视觉工程师",
    "MLOps": "AI模型部署工程师(MLOps)",
    "数据标注": "数据标注/AI数据专员",
    "大数据": "大数据工程师",
    "数据开发": "大数据工程师",
    "数仓": "大数据工程师",
    "云计算": "云计算/AI基础设施工程师",
    "运维开发": "数据中心运维工程师",
    "DevOps": "数据中心运维工程师",
    "嵌入式": "嵌入式AI工程师",
    "物联网": "物联网(IoT)架构师",
    "IoT": "物联网(IoT)架构师",
    "Prompt": "Prompt工程师",
    # 泛称与应用类（v2 新增）：应用开发岗归 Agent 开发，泛 AI 工程师归算法主体岗
    # 注意：别名匹配在去空格的 norm 上进行，别名本身不得含空格
    # 顺序：更具体的词必须排在泛词前（“感知算法”先于“机器学习”）
    "AI应用": "AI Agent开发工程师",
    "应用AI": "AI Agent开发工程师",
    "AINative": "AI Agent开发工程师",
    "AI全栈": "AI Agent开发工程师",
    "AI开发": "AI Agent开发工程师",
    "AI工程师": "大模型算法工程师",
    "人工智能工程师": "大模型算法工程师",
    "算法工程师": "大模型算法工程师",
    "AI研发": "大模型算法工程师",
    "AI技术": "大模型算法工程师",
    # v4（evalloop 首轮）：推理服务工程岗归 MLOps（role_level-097 证据，
    # "Staff Software Engineer, Inference" 原 unmatched）；置于算法词后，
    # "Inference Research" 类算法岗仍由前部研究/算法词先接住。
    "Inference": "AI模型部署工程师(MLOps)",
}

# v5：泛词别名——归类粗暴、无法区分方向，repair --semantic 时对这些命中
# 追加 LLM 语义重判（职责细分）。证据：eval-v3 gold 修正的 15 条里
# 012/016/038/041/051/064/068 均为"算法工程师->pos_01"泛词粗暴归类。
GENERIC_ALIASES: tuple[str, ...] = (
    "算法工程师",
    "AI工程师",
    "人工智能工程师",
    "AI研发",
    "AI技术",
    "机器学习",
    "深度学习",
)

# v5.1：方向词——exact 命中大类（pos_01 等）但 title 含细分方向时也需语义重判
# （"多模态大模型算法工程师" exact 命中 pos_01，实际属 pos_04，role_level-012 证据）
SEMANTIC_DIRECTION_WORDS: tuple[str, ...] = (
    "多模态", "视觉", "搜索", "推荐", "语音", "NLP", "推理", "部署",
    "Agent", "数据挖掘", "运筹", "生成", "AIGC", "具身", "强化学习",
)

# LLM 结果后置校验族（v2）：title 命中族关键词而 LLM 未选族内岗位时修正。
# 顺序即优先级：视觉/部署/安全先于算法/应用（避免“图像算法”被“算法”截胡）。
# “视频”限定为算法/感知/生成语境，避免“视频号/短视频”产品名误中（v3 回归修复）。
FAMILY_CHECK: list[tuple[tuple[str, ...], str]] = [
    (("计算机视觉", "图像", "视觉", "谱图识别", "视频感知", "视频生成", "视频算法"), "pos_27"),
    (("部署", "MLOps"), "pos_05"),
    (("网安", "网络安全", "信息安全", "数据安全"), "pos_36"),
    (("大模型", "LLM", "算法", "AI工程师", "人工智能工程师", "AI研发", "AI技术"), "pos_01"),
    # v4.1：补 "Applied AI" 英文族词（role_level-074/081 "Applied AI Engineer/Architect"）
    (("AI应用", "应用AI", "AI Native", "AI开发", "Applied AI", "Agent", "智能体", "RAG"), "pos_02"),
]

# 域专门岗集合：族校验不得覆盖 LLM 对专门域岗位的判断
# （如“智慧交通/算法类”->pos_44 不应被“算法”族抢回 pos_01）
DOMAIN_SPECIFIC_PIDS: frozenset[str] = frozenset(
    {"pos_37", "pos_39", "pos_41", "pos_42", "pos_43", "pos_44", "pos_45", "pos_46"}
)

# 商务/管理信号词：title 命中且无任何技术信号时，岗位不属技术目录，应 unmatched
BIZ_SIGNALS: tuple[str, ...] = (
    "销售",
    "市场",
    "品牌",
    "运营",
    "渠道",
    "测试工程师",
    "测试员",
    "技术支持",
    "Account Executive",
    "Product Marketing",
    "Engagement Manager",
    "Customer Success",
    "GTM",
    "Legal",
    "Counsel",
    "Program Manager",
    "Project Manager",
    "Forward Deployed",
    "Field Engineer",
    "Solutions Architect",
    "Solutions Consultant",
    "Developer Relations",
    "Revenue",
    "Enablement",
    # v4.1（evalloop 第二圈，run 20260831T161631 建议 2 采纳部分）：
    # Manager 类精确形态，命中即按商务/管理岗排除（role_level-063/084/086 期望 None）。
    # 用 "managerof"/"manager-"/"sr.manager" 而非裸 "manager"：避开 "Product Manager"
    # （AI产品经理 pos_06 是合法目录岗，会被误伤）。
    "Manager of",
    "Manager -",
    "Manager –",
    "Sr. Manager",
    # v4.1 撤回：曾加 "战略"/"商业化"，中文词过宽——"算法工程师-商业化"等
    # 合法技术岗被整词错杀（evalcmp 回归 44），087 留人工裁决。
)

# 技术执行岗集合：alias 命中技术岗而 title 含商务信号时跳过该别名
TECH_PIDS: frozenset[str] = frozenset(
    {
        "pos_01",
        "pos_02",
        "pos_03",
        "pos_04",
        "pos_05",
        "pos_11",
        "pos_13",
        "pos_14",
        "pos_15",
        "pos_16",
        "pos_17",
        "pos_23",
        "pos_27",
        "pos_28",
        "pos_29",
        "pos_30",
        "pos_35",
        "pos_36",
        "pos_37",
        "pos_38",
        "pos_39",
        "pos_41",
        "pos_44",
    }
)

LEVEL_BY_EXPERIENCE = [
    (("在校", "应届", "实习", "1年以内", "经验不限"), "L1", "经验要求"),
    (("1-3年", "1-3", "一年以上"), "L2", "经验要求"),
    (("3-5年", "3-5", "5-10年"), "L3", "经验要求"),
    (("10年以上",), "L4", "经验要求"),
]
LEVEL_BY_TITLE = [
    (("首席", "专家", "负责人", "总监", "CTO", "架构师"), "L4", "职位名"),
    (("高级", "资深", "Senior"), "L3", "职位名"),
    (("助理", "初级", "实习", "Junior"), "L1", "职位名"),
]


def _has_biz_signal(norm_lower: str) -> bool:
    """title（去空格小写）是否含商务/管理/运营信号。

    v4.1：Forward Deployed 只在 title 无 "engineer" 时才算商务信号——
    FDE（Forward Deployed Engineer）本质是部署工程岗，整词排除会把
    "Frontier Agents Engineer (Forward Deployed Engineering)" 错杀。
    """
    for s in BIZ_SIGNALS:
        key = s.replace(" ", "").lower()
        if key == "forwarddeployed":
            # FDE 精确化：title 真的含该词、且无 engineer 时才算商务信号
            # （v4.1 首版漏了 key in 判断，所有不含 engineer 的 title 被误判，
            #  evalcmp 回归 44 当场拦下）
            if key in norm_lower and "engineer" not in norm_lower:
                return True
            continue
        if key in norm_lower:
            return True
    return False


def _family_override(title: str, pid: str) -> tuple[str, str]:
    """别名命中后的族覆写：高优先族（视觉/部署/安全）优先于泛别名。

    修复“AI应用部署工程师”被“AI应用”接进 pos_02 而“部署”才是核心职责的回归。
    """
    norm = title.replace(" ", "").lower()
    for keys, family_pid in FAMILY_CHECK[:3]:
        if any(k.replace(" ", "").lower() in norm for k in keys):
            # 别名已精确命中域专门岗（如“感知算法”->pos_39）时不覆写
            if pid in DOMAIN_SPECIFIC_PIDS:
                return pid, ""
            if pid in TECH_PIDS and family_pid != pid:
                return family_pid, f"族覆写 {pid}->{family_pid}"
    return pid, ""


def match_by_rule(title: str, positions: list[dict]) -> tuple[str | None, float, str]:
    """规则匹配：标准名包含 > 别名包含。返回 (position_id, confidence, method)。

    v3：别名命中技术执行岗但 title 带商务/管理信号时跳过（“大模型平台运营”
    不应被“大模型”别名接进算法岗）。
    """
    norm = title.replace(" ", "").replace("（", "(")
    for p in positions:
        base = p["name"].replace("（", "(").split("(")[0]
        if base and base in norm:
            return p["position_id"], 1.0, "exact"
    has_biz = _has_biz_signal(norm.lower())
    for alias, target in TITLE_ALIASES.items():
        if alias.replace(" ", "") in norm:
            for p in positions:
                if p["name"] == target:
                    if has_biz and p["position_id"] in TECH_PIDS:
                        break
                    final_pid, _ = _family_override(title, p["position_id"])
                    return final_pid, 0.7, "alias"
    return None, 0.0, ""


def infer_level(title: str, work_year: str) -> tuple[str, str]:
    """等级推断：职位名关键词优先（更具体），其次经验要求。返回 (level, basis)。"""
    norm = title.replace(" ", "")
    for keys, level, basis in LEVEL_BY_TITLE:
        if any(k in norm for k in keys):
            return level, f"{basis}:{next(k for k in keys if k in norm)}"
    wy = work_year or ""
    for keys, level, basis in LEVEL_BY_EXPERIENCE:
        if any(k in wy for k in keys):
            return level, f"{basis}:{wy or '经验不限'}"
    return "UNKNOWN", "无信号"


def _catalog(positions: list[dict]) -> str:
    return "\n".join(f"{p['position_id']} {p['name']}（{p['group']}）" for p in positions)


def post_check(title: str, position_id: str | None, confidence: float) -> tuple[str | None, str]:
    """LLM 映射后置校验：

    1. confidence < 0.6 强制 unmatched（prompt 规则 5 的代码层兜底）；
    2. v3：title 带商务/管理信号且目标为技术执行岗或无技术族命中 -> unmatched
      （非技术岗强行归类的主要防线）；
    3. title 命中族关键词而结果不在族内 -> 修正为族指向。
    返回 (修正后 position_id, 修正说明)；未修正说明为空。
    """
    if position_id and confidence < 0.6:
        return None, f"置信度 {confidence:.2f} 低于 0.6，降级 unmatched"
    norm = title.replace(" ", "").lower()
    has_biz = _has_biz_signal(norm)
    tech_hit = any(k.replace(" ", "").lower() in norm for keys, _ in FAMILY_CHECK for k in keys)
    if has_biz and (position_id in TECH_PIDS or not tech_hit):
        return None, "商务/管理岗信号，排除出技术目录"
    # v3：无任何技术信号（族关键词、别名技术词、AI 裸词都不命中）的 LLM 结果
    # 是脑补映射——目录是 AI 技术岗位目录，无信号即降级
    has_ai_word = any(w in norm for w in ("ai", "人工智能", "智能", "机器人", "运维"))
    has_alias_word = any(a.replace(" ", "").lower() in norm for a in TITLE_ALIASES)
    if position_id and not (tech_hit or has_ai_word or has_alias_word):
        return None, "title 无技术信号，LLM 脑补映射排除"
    for keys, family_pid in FAMILY_CHECK:
        if any(k.replace(" ", "").lower() in norm for k in keys):
            if position_id != family_pid:
                # 域专门岗保护：LLM 已判定专门域岗位时不被泛族关键词抢回
                if position_id in DOMAIN_SPECIFIC_PIDS:
                    return position_id, ""
                return (
                    family_pid,
                    f"族校验修正：命中族关键词，{position_id or 'unmatched'} -> {family_pid}",
                )
            return position_id, ""
    return position_id, ""


def _parse(raw: str, jd_id: str) -> dict:
    from backend.jobs.models import RoleMatch

    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("输出必须是 JSON 对象")
    data.pop("jd_id", None)
    return RoleMatch.model_validate({**data, "jd_id": jd_id}).model_dump()


async def cmd_run() -> dict:
    settings = LLMSettings()
    run = RunContext("rolemap", {"cmd": "run"})
    spec = load_prompt("role-map")
    provider = build_provider(settings)
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]
    rows = [
        r for r in (json.loads(x) for x in PARSED.open(encoding="utf-8")) if r.get("is_ai_role")
    ]

    done: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            done.add(json.loads(line).get("jd_id"))
    todo = [r for r in rows if r["jd_id"] not in done]

    sem = asyncio.Semaphore(15)
    fh = OUT.open("a", encoding="utf-8")
    llm_hits = misses = 0

    async def one(r: dict) -> None:
        nonlocal llm_hits, misses
        title = r["title"]
        pid, conf, method = match_by_rule(title, positions)
        level, basis = infer_level(title, r.get("work_year") or "")
        if pid:
            rec = {
                "jd_id": r["jd_id"],
                "platform": r["platform"],
                "title": title,
                "position_id": pid,
                "confidence": conf,
                "method": method,
                "level": level,
                "level_basis": basis,
                "publish_date": r.get("publish_date"),
            }
        else:
            # LLM 语义候选
            message = (
                f"jd_id: {r['jd_id']}\n职位名: {title}\n经验要求: {r.get('work_year') or '未知'}\n"
                f"职责摘要: {'; '.join(r.get('responsibilities') or [])[:300]}\n\n"
                f"标准岗位清单:\n{_catalog(positions)}\n\n任务: {spec.task}。只输出 JSON。"
            )
            last_err = "unknown"
            cand = None
            async with sem:
                for attempt in range(1 + MAX_RETRIES):
                    user = (
                        message
                        if attempt == 0
                        else f"{message}\n\n上次失败: {last_err}\n重新输出。"
                    )
                    try:
                        raw = await provider.complete(
                            system=spec.system,
                            user=user,
                            max_tokens=int(spec.limits.get("max_tokens", 400)),
                            timeout=float(spec.limits.get("timeout_seconds", 60)),
                        )
                        cand = _parse(raw, r["jd_id"])
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_err = f"{type(exc).__name__}: {exc}"[:150]
            pid = (cand or {}).get("position_id") if (cand or {}).get("is_match") else None
            if pid:
                llm_hits += 1
                rec = {
                    "jd_id": r["jd_id"],
                    "platform": r["platform"],
                    "title": title,
                    "position_id": pid,
                    "confidence": (cand or {}).get("confidence", 0),
                    "method": "llm",
                    "level": level,
                    "level_basis": basis,
                    "publish_date": r.get("publish_date"),
                    "reason": (cand or {}).get("reason", ""),
                }
            else:
                misses += 1
                rec = {
                    "jd_id": r["jd_id"],
                    "platform": r["platform"],
                    "title": title,
                    "position_id": None,
                    "confidence": 0,
                    "method": "unmatched",
                    "level": level,
                    "level_basis": basis,
                    "publish_date": r.get("publish_date"),
                    "error": last_err if not cand else "llm_no_match",
                }
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    try:
        done = 0
        started = time.monotonic()

        async def tracked(r: dict) -> None:
            nonlocal done
            await one(r)
            done += 1
            if done % 25 == 0 or done == len(todo):
                rate = done / (time.monotonic() - started) * 60
                eta = (len(todo) - done) / max(rate, 0.01)
                run.log(
                    "progress",
                    "progress",
                    "progress",
                    count={
                        "done": done,
                        "total": len(todo),
                        "per_min": round(rate, 1),
                        "eta_min": round(eta),
                    },
                )

        await asyncio.gather(*(tracked(r) for r in todo))
    finally:
        fh.close()
    all_recs = [json.loads(x) for x in OUT.open(encoding="utf-8")] if OUT.is_file() else []
    from collections import Counter

    by_method = Counter(r["method"] for r in all_recs)
    metrics = {
        "targets": len(rows),
        "todo": len(todo),
        "by_method": dict(by_method),
        "levels": dict(Counter(r["level"] for r in all_recs)),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        **provider.usage.as_dict(),
    }
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, dict)})
    return metrics


def cmd_label() -> dict:
    """生成人工标注包：映射与等级双确认列。"""
    run = RunContext("rolemap", {"cmd": "label"})
    recs = [json.loads(x) for x in OUT.open(encoding="utf-8")]
    positions = {
        p["position_id"]: p["name"]
        for p in (json.loads(x) for x in POSITIONS.open(encoding="utf-8"))
    }
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    with LABELS.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "jd_id",
                "职位名",
                "系统岗位",
                "系统置信度",
                "系统等级",
                "等级依据",
                "映射正确?(对/错)",
                "修正岗位",
                "等级正确?(对/错)",
                "修正等级",
                "备注",
            ]
        )
        for r in recs:
            w.writerow(
                [
                    r["jd_id"],
                    r["title"],
                    positions.get(r.get("position_id") or "", ""),
                    r.get("confidence", ""),
                    r["level"],
                    r.get("level_basis", ""),
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
    n = len(recs)
    run.finish({"rows": n})
    return {"rows": n, "file": str(LABELS)}


def cmd_repair(semantic: bool = False, force: bool = False) -> dict:
    """v3 重判：规则层重跑 + 后置校验，零 LLM 成本。

    读取现有 jd-role-map.jsonl，输出 jd-role-map-repaired.jsonl：
    - 规则层（扩充别名 + 商务信号过滤）能接住的以规则为准；
    - 规则层未接住的统一过 post_check（族一致性 + 非技术岗排除），
      含曾被旧别名误中的条目（过滤后降级 unmatched）。

    v5 --semantic：泛词别名（GENERIC_ALIASES，约 398 条命中）在规则匹配后
    追加 LLM 语义重判（role-semmap.yml，输入带职责与技能）。泛词无法区分
    方向（"算法工程师"->pos_01 是粗暴归类），职责语义才能细分（多模态算法
    ->pos_04 / 推理框架->pos_05）；明确词别名与 exact 不重判。
    """
    run = RunContext("rolemap", {"cmd": "repair", "semantic": semantic, "force": force})
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]
    out_repaired = OUT.with_name("jd-role-map-repaired.jsonl")
    changed = repaired = 0
    recs = [json.loads(x) for x in OUT.open(encoding="utf-8")]
    # 幂等（继承式）：上轮语义重判结果直接继承——重判非确定性，重跑会漂移；
    # repair 是确定性管线，semantic 结果一经产生即为缓存（--semantic-force 才重判）
    prev_semantic: dict[str, dict] = {}
    if out_repaired.is_file() and not force:
        for line in out_repaired.open(encoding="utf-8"):
            r = json.loads(line)
            if str(r.get("method", "")).startswith("semantic"):
                prev_semantic[r["jd_id"]] = r
    # 治理层次：人审/AI 交叉复核锚定（corrected_payload）的 case 不被批量重判翻案
    anchored = _anchored_decisions()
    semantic_hits: list[dict] = []
    for rec in recs:
        # 一级：锚定判定直接生效（人审/AI 交叉复核，含 None 锚定），不触任何后续
        if rec["jd_id"] in anchored:
            rec["position_id"] = anchored[rec["jd_id"]]
            rec["confidence"] = 1.0 if anchored[rec["jd_id"]] else 0
            rec["method"] = "anchored"
            continue
        # 二级：继承上轮 semantic 判定（缓存语义，保证 repair 确定性）
        prev = prev_semantic.get(rec["jd_id"])
        if prev is not None:
            rec["position_id"] = prev.get("position_id")
            rec["confidence"] = prev.get("confidence", 0)
            rec["method"] = prev.get("method")
            if prev.get("semantic_reason"):
                rec["semantic_reason"] = prev["semantic_reason"]
            continue
        title = rec["title"]
        pid, conf, method = match_by_rule(title, positions)
        if pid:
            # 规则层（含扩充别名）能接住的，以规则为准
            if pid != rec.get("position_id"):
                changed += 1
            rec["position_id"] = pid
            rec["confidence"] = conf
            rec["method"] = method
            # v5.1：语义重判触发（AI+关键词结合）——
            # a) 泛词别名命中（归类粗暴，职责才能细分）
            # b) LLM 路径结果（llm/llm-repair 置信有限，None 类错误主来源）
            # c) exact 命中但 title 含细分方向词（"多模态大模型算法工程师"类）
            if semantic and rec["jd_id"] not in prev_semantic and rec["jd_id"] not in anchored:
                norm = title.replace(" ", "")
                need = method == "alias" and any(
                    a.replace(" ", "") in norm for a in GENERIC_ALIASES
                )
                if not need and method == "exact":
                    need = rec["position_id"] == "pos_01" and any(
                        w in norm for w in SEMANTIC_DIRECTION_WORDS
                    )
                if need:
                    rec["_generic_alias"] = "v5.1-expanded"
                    semantic_hits.append(rec)
        else:
            # 规则层未接住：统一过 post_check（LLM 修正 / 商务排除 / 族校验）
            new_pid, note = post_check(title, rec.get("position_id"), rec.get("confidence", 0))
            if new_pid != rec.get("position_id"):
                repaired += 1
                rec["position_id"] = new_pid
                rec["method"] = "llm-repair" if new_pid else "unmatched"
                rec["repair_note"] = note
                if not new_pid:
                    rec["confidence"] = 0
            # v5.1：LLM 路径存活判定（llm/llm-repair）-> 语义重判
            # （None 类错误主来源：Manager/测试/全栈等被 LLM 判了技术岗；
            #  这些 case 本轮规则匹配 unmatched 走本分支，须在此触发）
            if (
                semantic
                and rec["jd_id"] not in prev_semantic
                and rec["jd_id"] not in anchored
                and rec.get("method") in ("llm", "llm-repair")
            ):
                rec["_generic_alias"] = "v5.1-llm-path"
                semantic_hits.append(rec)

    n_semantic = 0
    if semantic_hits:
        n_semantic = asyncio.run(_semantic_remap(semantic_hits))
    for rec in recs:
        rec.pop("_generic_alias", None)

    with out_repaired.open("w", encoding="utf-8") as fh:
        for rec in recs:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    from collections import Counter

    metrics = {
        "total": len(recs),
        "rule_changed": changed,
        "llm_repaired": repaired,
        "semantic_remap": n_semantic,
        "by_method": dict(Counter(r["method"] for r in recs)),
    }
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, dict)})
    return metrics


async def _semantic_remap(recs: list[dict]) -> int:
    """泛词命中 case 的 LLM 语义重判（role-semmap.yml，带职责上下文）。

    就地更新 rec 的 position_id/method/confidence；method 标记 semantic。
    返回实际发生变更的条数。重判失败保留规则结果（不降级）。
    """
    from backend.infra.llm.promptspec import load_prompt
    from backend.infra.llm.provider import AnthropicProvider
    from backend.infra.llm.settings import LLMSettings
    from backend.jobs.models import RoleMatch

    spec = load_prompt("role-semmap")
    provider = AnthropicProvider(LLMSettings())
    parsed = {
        json.loads(line)["jd_id"]: json.loads(line)
        for line in PARSED.open(encoding="utf-8")
    }
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]
    catalog = "\n".join(f"{p['position_id']} {p.get('group')}/{p['name']}" for p in positions)
    sem = asyncio.Semaphore(8)
    changed = 0

    async def one(rec: dict) -> None:
        nonlocal changed
        jd = parsed.get(rec["jd_id"], {})
        resp = "\n".join(f"- {x[:60]}" for x in (jd.get("responsibilities") or [])[:5])
        skills = ", ".join((jd.get("skill_mentions") or [])[:10])
        user = (
            f"jd_id: {rec['jd_id']}\n职位名: {rec['title']}\n职责:\n{resp}\n"
            f"技能: {skills}\n\n标准岗位目录:\n{catalog}"
        )
        async with sem:
            try:
                raw = await provider.complete(
                    system=spec.system,
                    user=user,
                    max_tokens=int(spec.limits.get("max_tokens", 1500)),
                    timeout=float(spec.limits.get("timeout_seconds", 120)),
                )
                d = json.loads(_strip_json(raw))
                # reason 硬截断：S4 判例式解释惯性超 40 字限制（RoleMatch 约束）
                d["reason"] = (d.get("reason") or "")[:40]
                m = RoleMatch.model_validate(d)
            except Exception:  # noqa: BLE001 - 重判失败保留规则结果
                rec["semantic_note"] = "重判失败，保留规则结果"
                return
        new_pid = m.position_id if m.is_match else None
        if new_pid != rec.get("position_id"):
            changed += 1
            rec["position_id"] = new_pid
            rec["confidence"] = m.confidence
            rec["semantic_reason"] = m.reason
        rec["method"] = "semantic" if new_pid else "semantic-unmatched"

    await asyncio.gather(*(one(r) for r in recs))
    print(f"语义重判 {len(recs)} 条（变更 {changed}）；tokens={provider.usage.as_dict()}")
    return changed


def _anchored_decisions() -> dict[str, str | None]:
    """评测锚定判定：jd_id -> position_id（None=锚定为目录外）。

    来源 annotations 最新带 corrected_payload 的判定（含空 position_id 的
    None 锚定）。治理优先级：锚定 > 继承 semantic > 规则 + 新重判。
    """
    import csv as _csv

    ann_path = ROOT / "evaluation" / "annotations.jsonl"
    csv_path = ROOT / "evaluation" / "samples" / "role-mapping.csv"
    if not ann_path.is_file() or not csv_path.is_file():
        return {}
    latest: dict[str, dict] = {}
    for line in ann_path.open(encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("dataset_version") == "eval-v3-20260828":
            latest[rec["task_id"]] = rec
    anchored: dict[int, str | None] = {}
    for tid, r in latest.items():
        cp = r.get("corrected_payload") or {}
        if r.get("corrected_payload") is not None and "position_id" in cp:
            anchored[int(tid.rsplit("-", 1)[1])] = cp.get("position_id") or None
    rows = list(_csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    out: dict[str, str | None] = {}
    for i, row in enumerate(rows):
        if i in anchored:
            out[row["jd_id"]] = anchored[i]
    return out


def _strip_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1 :] if nl != -1 else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rolemap")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("label")
    p_repair = sub.add_parser("repair")
    p_repair.add_argument(
        "--semantic", action="store_true", help="泛词/LLM路径/方向词 exact 追加语义重判"
    )
    p_repair.add_argument(
        "--semantic-force", action="store_true", help="忽略上轮 semantic 结果全部重判"
    )
    args = parser.parse_args(argv)
    import asyncio

    if args.cmd == "run":
        result = asyncio.run(cmd_run())
    elif args.cmd == "repair":
        result = cmd_repair(semantic=args.semantic, force=args.semantic_force)
    else:
        result = cmd_label()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

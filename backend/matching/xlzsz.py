"""学练赛证实体查询：证书（CERTS.yml）与竞赛（CONTESTS.yml）映射。

职责（Hiro2 领域规则，非框架重复）：
  - 证书/竞赛 -> capability_ids 反查：给定能力域，推荐真实证书与赛事；
  - 证书/竞赛 mention -> 能力域正查：简历出现证书名/竞赛名时提供判定证据；
  - 获奖等级 -> 岗位等级换算（award_to_level，可版本化阈值）。

数据源（人工审定的映射层，raw 数据由 certget/raceget 可复现）：
  data/CERTS.yml / data/CONTESTS.yml
查询层零 LLM：纯 YAML 规则匹配。
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CERTS_YML = ROOT / "data" / "CERTS.yml"
CONTESTS_YML = ROOT / "data" / "CONTESTS.yml"
SKILLS_YML = ROOT / "data" / "SKILLS.yml"
STD_REQ_DIR = ROOT / "data" / "processed" / "certs" / "std-requirements"
RACE_CATALOG = ROOT / "data" / "processed" / "races" / "race-catalog.jsonl"
PRED_CONTEXT = ROOT / "data" / "processed" / "temporal" / "prediction-context.json"


@lru_cache(maxsize=1)
def _load_certs() -> dict:
    if not CERTS_YML.is_file():
        return {"version": 0, "certs": []}
    data = yaml.safe_load(CERTS_YML.read_text(encoding="utf-8")) or {}
    data.setdefault("certs", [])
    return data


@lru_cache(maxsize=1)
def _load_contests() -> dict:
    if not CONTESTS_YML.is_file():
        return {"version": 0, "contests": []}
    data = yaml.safe_load(CONTESTS_YML.read_text(encoding="utf-8")) or {}
    data.setdefault("contests", [])
    return data


@lru_cache(maxsize=1)
def _load_skills() -> dict:
    if not SKILLS_YML.is_file():
        return {"version": 0, "entries": []}
    data = yaml.safe_load(SKILLS_YML.read_text(encoding="utf-8")) or {}
    data.setdefault("entries", [])
    return data


def _skill_keywords(skill_id: str) -> list[str]:
    """能力域的关键词集（名称 + aliases + 技能点名），用于知识点相关性打分。"""
    kws: list[str] = []
    for e in _load_skills()["entries"]:
        if e.get("capability_id") != skill_id:
            continue
        if e.get("name"):
            kws.append(str(e["name"]))
        kws.extend(str(a) for a in e.get("aliases", []) or [])
        for p in e.get("points", []) or []:
            if isinstance(p, dict) and p.get("name"):
                kws.append(str(p["name"]))
    # 过滤短词/泛词（如"记忆""推理"会误命中"长短期记忆网络"等无关上下文）；去重保序
    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        if len(k) >= 3 and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def certs_for_skill(skill_id: str, limit: int = 3) -> list[dict]:
    """能力域 -> 推荐证书（按 effective_from 倒序，供"证"段引用真实证书名）。"""
    out = [
        {
            "cert_id": c["cert_id"],
            "name": c["name"],
            "issuer": c.get("issuer", ""),
            "level_type": c.get("level_type", ""),
            "url": c.get("evidence_url", ""),
        }
        for c in _load_certs()["certs"]
        if skill_id in c.get("capability_ids", [])
    ]
    out.sort(key=lambda x: x.get("effective_from", ""), reverse=True)
    return out[:limit]


def knowledge_for_skill(skill_id: str, limit: int = 3) -> list[dict]:
    """能力域 -> 国家职业标准知识点（供"学"段引用官方知识点）。

    链路：capability_id -> CERTS.yml 的 osta 标准条目（cert_id=osta-std-<career_code>）
    -> data/processed/certs/std-requirements/<career_code>.jsonl -> knowledge 条目。
    用能力域名 + aliases 对知识点做关键词相关性打分，只返回命中的（国标多为 2021 年前，
    不覆盖 RAG/Agent 等新概念时诚实返空，由调用方回退模板）。确定性，零 LLM。
    """
    kws = _skill_keywords(skill_id)
    scored: list[tuple[int, dict]] = []
    seen_works: set[str] = set()
    for cert in _load_certs()["certs"]:
        if skill_id not in cert.get("capability_ids", []):
            continue
        cid = str(cert.get("cert_id", ""))
        if not cid.startswith("osta-std-"):
            continue  # 只消费国家职业标准（唯一带官方知识点的来源）
        career_code = cid[len("osta-std-") :]
        std_path = STD_REQ_DIR / f"{career_code}.jsonl"
        if not std_path.is_file():
            continue
        for line in std_path.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("level") not in ("初级", "五级/初级工"):
                continue
            work = rec.get("work", "")
            know = rec.get("knowledge") or []
            if not work or not know or work in seen_works:
                continue
            body = re.sub(r"^\d+(?:\.\d+)*\s*", "", know[0])
            # 相关性打分：知识点正文命中权重 2，工作内容命中权重 1；无命中不返回（避免硬套）
            body_hits = sum(1 for k in kws if k in body)
            work_hits = sum(1 for k in kws if k in work)
            score = 2 * body_hits + work_hits
            if score == 0:
                continue
            seen_works.add(work)
            scored.append(
                (
                    score,
                    {
                        "std_name": cert.get("name", career_code),
                        "career_code": career_code,
                        "work": work,
                        "knowledge": body[:80],
                    },
                )
            )
    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:limit]]


def skill_points_for_skill(skill_id: str, limit: int = 5) -> list[str]:
    """能力域 -> 自身技能点列表（SKILLS.yml points）。

    供"学"段第二层回退：国家职业标准不覆盖新概念（LLM/RAG/Agent 等 2021 年后）时，
    用能力域自身的技能点给出具体学习方向，避免泛泛模板。确定性，零 LLM。
    """
    for e in _load_skills()["entries"]:
        if e.get("capability_id") != skill_id:
            continue
        points = [
            str(p["name"])
            for p in e.get("points", []) or []
            if isinstance(p, dict) and p.get("name")
        ]
        return points[:limit]
    return []


def contests_for_skill(skill_id: str, limit: int = 3) -> list[dict]:
    """能力域 -> 推荐竞赛（供"赛"段引用真实赛事名）。"""
    out = [
        {
            "race_id": c["race_id"],
            "name": c["name"],
            "organizer": c.get("organizer", ""),
            "scale": c.get("scale", ""),
            "url": c.get("evidence_url", ""),
        }
        for c in _load_contests()["contests"]
        if skill_id in c.get("capability_ids", [])
    ]
    return out[:limit]


# ---------------------------------------------------------------- 竞赛时间维度
# race-catalog 全量赛事带 register_end / final_end；此前推荐只按能力域匹配精选名录，
# 不感知时间，可能推荐早已截止的赛事。以下函数打通时间维度：按能力域筛出"正在报名/即将截止"
# 的赛事，供"赛"段给出可操作推荐。


@lru_cache(maxsize=1)
def _load_race_catalog() -> tuple[dict, ...]:
    if not RACE_CATALOG.is_file():
        return ()
    return tuple(json.loads(line) for line in RACE_CATALOG.open(encoding="utf-8") if line.strip())


def _parse_date(s) -> date | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _race_caps(race: dict) -> set[str]:
    """从 industry（讯飞）/tags（天池、DF）推导能力域（CONTESTS.yml 规则）。未命中返空。"""
    rules = _load_contests()
    ind_rules = rules.get("industry_rules") or {}
    tag_rules = rules.get("tag_rules") or {}
    caps: set[str] = set()
    ind = race.get("industry") or ""
    if ind in ind_rules:
        caps.update(ind_rules[ind])
    for t in race.get("tags") or []:
        if t in tag_rules:
            caps.update(tag_rules[t])
    return caps


def race_status(race: dict, as_of: date) -> str:
    """赛事时间状态：正在报名 / 即将截止（截止日 <=14 天）/ 进行中 / 已结束 / 时间未知。"""
    reg_end = _parse_date(race.get("register_end"))
    final_end = _parse_date(race.get("final_end"))
    if reg_end is None:
        return "时间未知"
    if reg_end < as_of:
        if final_end is not None and final_end >= as_of:
            return "进行中"
        return "已结束"
    if (reg_end - as_of).days <= 14:
        return "即将截止"
    return "正在报名"


def open_contests_for_skill(skill_id: str, as_of: date, limit: int = 3) -> list[dict]:
    """能力域 -> 正在报名/即将截止的赛事（按截止日升序，最紧急在前）。

    从 race-catalog 全量赛事按 industry/tag 规则推导能力域，筛出可报名的，
    返回带截止日与剩余天数的结构化条目，供"赛"段可操作推荐。确定性，零 LLM。
    """
    out: list[dict] = []
    for race in _load_race_catalog():
        if skill_id not in _race_caps(race):
            continue
        status = race_status(race, as_of)
        if status not in ("正在报名", "即将截止"):
            continue
        reg_end = _parse_date(race.get("register_end"))
        days_left = (reg_end - as_of).days if reg_end else None
        # 截止日超 1 年视为占位/长期挂载（如 2099-12-31），不当作真实可报名窗口。
        if days_left is not None and days_left > 365:
            continue
        out.append(
            {
                "race_id": race.get("race_id", ""),
                "name": race.get("name") or "",
                "organizer": race.get("organizer") or "",
                "url": race.get("source_url") or "",
                "status": status,
                "register_end": (race.get("register_end") or "")[:10],
                "days_left": days_left,
            }
        )
    out.sort(key=lambda x: x["days_left"] if x["days_left"] is not None else 9999)
    return out[:limit]


# ---------------------------------------------------------------- 预测信号（时间情报域 -> 学练段）
# 快照由 scripts/predsnap.py 合并 ForecastEngine 预测 + leadtime 建议生成，
# 使匹配引擎（文件驱动）能消费预测信号而不直连 DB。边界：仅作信息性前瞻提示，
# 不改岗位版本、不绕过审核（docs/temporal-system.md）。


@lru_cache(maxsize=1)
def _load_prediction() -> dict:
    if not PRED_CONTEXT.is_file():
        return {}
    return json.loads(PRED_CONTEXT.read_text(encoding="utf-8"))


def prediction_for_skill(skill_id: str) -> dict | None:
    """能力域 -> 预测上下文（方向/置信/新涌现/建议）；无快照或无该域返 None。

    返回包含 note 的字典：把预测信号转为人话（如"预测上升，建议优先投入"），
    供学练段前瞻提示。低置信/平稳/回落不生成提示（避免噪声）。
    """
    ctx = _load_prediction().get("skills", {}).get(skill_id)
    if not ctx:
        return None
    direction = ctx.get("direction", "flat")
    conf = ctx.get("confidence", 0)
    emerging = ctx.get("emerging", False)
    note = ""
    if emerging:
        note = "新涌现方向（近期信号从无到有），值得关注"
    elif direction == "up" and conf >= 0.5:
        note = f"市场信号预测上升（置信 {conf}），建议优先投入"
    elif direction == "down" and conf >= 0.5:
        note = f"市场信号回落（置信 {conf}），投入前可再观察"
    if not note:
        return {**ctx, "note": ""}
    return {**ctx, "note": note}


def match_cert_mention(text: str) -> list[dict]:
    """文本 -> 命中的证书（简历证书经历判"已具备"的证据来源）。

    匹配规则：证书名（去空格）作为子串出现即命中；返回完整映射条目。
    """
    if not text:
        return []
    normalized = text.replace(" ", "")
    hits = []
    for c in _load_certs()["certs"]:
        name = c["name"].replace(" ", "")
        if name and name in normalized:
            hits.append(c)
    return hits


def match_contest_mention(text: str) -> list[dict]:
    """文本 -> 命中的竞赛（竞赛经历的能力证据来源）。"""
    if not text:
        return []
    normalized = text.replace(" ", "")
    hits = []
    for c in _load_contests()["contests"]:
        # 合辑类条目名含"（历年合辑）"等后缀，取括号前主干匹配
        stem = c["name"].split("（")[0].replace(" ", "")
        if stem and len(stem) >= 4 and stem in normalized:
            hits.append(c)
    return hits


def _normalize_award(award: str) -> str:
    """归一获奖措辞到换算表口径："省一等奖"->"省级一等奖"、"国一"->"国家级一等奖"。

    LLM 从简历抽取的获奖措辞多变（省一/省级一等/全国一等/国二），先归一再查表，
    避免同义措辞落回默认 L1。无作用域前缀的企业奖（如"冠军"）原样返回。
    """
    a = award.strip()
    m = re.match(r"^(全国|国家|国|省)(级)?([一二三])(等奖|等)?(奖)?$", a)
    if not m:
        return a
    scope, _, rank, _, _ = m.groups()
    canon_scope = "省级" if scope == "省" else "国家级"
    return f"{canon_scope}{rank}等奖"


def award_to_level(scale: str, award: str) -> str:
    """获奖等级 -> 岗位等级（L1/L2/L2.5/L3），未配置的组合默认 L1。"""
    table = _load_contests().get("award_to_level", {})
    normalized = _normalize_award(award)
    return str(table.get(scale, {}).get(normalized, "L1"))


def cert_level(level_type: str, grade: str) -> str:
    """证书等级 -> 岗位等级（L1/L2/L3），未配置组合默认 L1。"""
    table = _load_certs().get("level_scale", {})
    return str(table.get(level_type, {}).get(grade, "L1"))

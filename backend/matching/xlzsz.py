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
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CERTS_YML = ROOT / "data" / "CERTS.yml"
CONTESTS_YML = ROOT / "data" / "CONTESTS.yml"
SKILLS_YML = ROOT / "data" / "SKILLS.yml"
STD_REQ_DIR = ROOT / "data" / "processed" / "certs" / "std-requirements"


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


def award_to_level(scale: str, award: str) -> str:
    """获奖等级 -> 岗位等级（L1/L2/L2.5/L3），未配置的组合默认 L1。"""
    table = _load_contests().get("award_to_level", {})
    return str(table.get(scale, {}).get(award, "L1"))


def cert_level(level_type: str, grade: str) -> str:
    """证书等级 -> 岗位等级（L1/L2/L3），未配置组合默认 L1。"""
    table = _load_certs().get("level_scale", {})
    return str(table.get(level_type, {}).get(grade, "L1"))

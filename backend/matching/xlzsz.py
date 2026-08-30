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

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CERTS_YML = ROOT / "data" / "CERTS.yml"
CONTESTS_YML = ROOT / "data" / "CONTESTS.yml"


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

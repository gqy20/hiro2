"""技能归一化 resolver（D4）：原词 -> canonical 能力/技能点，确定性规则匹配。

两类词典：
- data/SKILLS.yml        人工先验别名，任何 as_of 均可用（无时间闸门）
- data/SKILLS-EARNED.yml 语料习得别名，带 effective_from（首见日期），
                         as_of 非空时 effective_from > as_of 的别名不参与匹配，
                         防止回测被"未来词典"污染（规则泄漏）

未命中的提及不是错误，是新词队列的输入。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SKILLS_FILE = DATA_DIR / "SKILLS.yml"
EARNED_FILE = DATA_DIR / "SKILLS-EARNED.yml"


@dataclass(frozen=True)
class SkillEntry:
    capability_id: str
    name: str
    aliases: tuple[str, ...]
    points: tuple[tuple[str, tuple[str, ...]], ...]  # (point_name, point_aliases)


@dataclass(frozen=True)
class EarnedAlias:
    """语料习得别名：首见日期之前不可用（时间闸门）。"""

    mention: str
    capability_id: str
    point_name: str | None
    effective_from: date
    sample_event_id: str | None = None


@dataclass(frozen=True)
class MatchResult:
    mention: str
    skill_id: str | None
    point_id: str | None
    point_name: str | None
    matched_by: str  # name | alias | point_name | point_alias | earned | unmatched


def normalize(text: str) -> str:
    """小写、全角转半角、压缩空白；用于词典与提及的统一比对。"""
    t = unicodedata.normalize("NFKC", text).strip().lower()
    return " ".join(t.split())


def _lookup_key(text: str) -> str:
    """去空格变体：中文习惯写法"Prompt 工程"与别名"Prompt工程"须可互达。"""
    return normalize(text).replace(" ", "")


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


class SkillResolver:
    def __init__(
        self,
        entries: list[SkillEntry],
        version: int,
        earned: list[EarnedAlias] | None = None,
        as_of: date | None = None,
    ) -> None:
        self.version = version
        self.entries = entries
        self.as_of = as_of
        self._lookup: dict[str, MatchResult] = {}
        for entry in entries:
            cap = entry.capability_id
            self._lookup[_lookup_key(entry.name)] = MatchResult(entry.name, cap, None, None, "name")
            for alias in entry.aliases:
                self._lookup.setdefault(
                    _lookup_key(alias), MatchResult(alias, cap, None, None, "alias")
                )
            for point_name, point_aliases in entry.points:
                pid: str | None = f"{cap}.{point_name}"
                self._lookup.setdefault(
                    _lookup_key(point_name),
                    MatchResult(point_name, cap, pid, point_name, "point_name"),
                )
                for alias in point_aliases:
                    self._lookup.setdefault(
                        _lookup_key(alias), MatchResult(alias, cap, pid, point_name, "point_alias")
                    )
        for ea in earned or []:
            if as_of is not None and ea.effective_from > as_of:
                continue  # 时间闸门：首见日期晚于 as_of 的习得别名不可用
            pid = f"{ea.capability_id}.{ea.point_name}" if ea.point_name else None
            self._lookup.setdefault(
                _lookup_key(ea.mention),
                MatchResult(ea.mention, ea.capability_id, pid, ea.point_name, "earned"),
            )

    def resolve(self, mention: str) -> MatchResult:
        hit = self._lookup.get(_lookup_key(mention))
        if hit is None:
            return MatchResult(mention, None, None, None, "unmatched")
        return MatchResult(mention, hit.skill_id, hit.point_id, hit.point_name, hit.matched_by)


def load_earned(earned_file: Path = EARNED_FILE) -> list[EarnedAlias]:
    if not earned_file.is_file():
        return []
    data = yaml.safe_load(earned_file.read_text(encoding="utf-8"))
    if not data:
        return []
    out = []
    for raw in data.get("aliases", []):
        eff = parse_day(raw.get("effective_from"))
        if eff is None:
            continue
        out.append(
            EarnedAlias(
                mention=str(raw["mention"]),
                capability_id=str(raw["capability_id"]),
                point_name=raw.get("point_name"),
                effective_from=eff,
                sample_event_id=raw.get("sample_event_id"),
            )
        )
    return out


def load_resolver(
    skills_file: Path = SKILLS_FILE,
    earned_file: Path = EARNED_FILE,
    as_of: date | None = None,
) -> SkillResolver:
    data = yaml.safe_load(skills_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "version" not in data or "entries" not in data:
        raise ValueError(f"词典结构非法: {skills_file}")
    entries = []
    for raw in data["entries"]:
        points = tuple(
            (str(p["name"]), tuple(str(a) for a in p.get("aliases", [])))
            for p in raw.get("points", [])
        )
        entries.append(
            SkillEntry(
                capability_id=str(raw["capability_id"]),
                name=str(raw["name"]),
                aliases=tuple(str(a) for a in raw.get("aliases", [])),
                points=points,
            )
        )
    return SkillResolver(entries, int(data["version"]), load_earned(earned_file), as_of)

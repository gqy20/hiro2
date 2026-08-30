"""resparse: 批量解析已入档但未解析的简历。"""

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.candidates.archive import OBJECTS, update_archive  # noqa: E402
from backend.candidates.parse import (  # noqa: E402
    ResumeRawExtraction,
    build_profile,
    extract_resume,
    llm_resolve_unmatched,
    parse_document,
)
from backend.skills.resolver import load_resolver, normalize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "processed" / "candidates" / "resume-archive.jsonl"


def _rows() -> list[dict]:
    if not ARCHIVE.is_file():
        return []
    latest: dict[str, dict] = {}
    for line in ARCHIVE.open(encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            latest[row["resume_id"]] = row
    return list(latest.values())


def _case_key(row: dict) -> str:
    return Path(str(row.get("filename", ""))).stem


def _deterministic_extraction(text: str, resolver) -> ResumeRawExtraction:
    compact = normalize(text).replace(" ", "")
    skills: list[dict] = []
    for entry in resolver.entries:
        candidates = [entry.name, *entry.aliases]
        candidates.extend(point for point, _ in entry.points)
        candidates.extend(alias for _, aliases in entry.points for alias in aliases)
        mention = next(
            (
                candidate
                for candidate in sorted(set(candidates), key=len, reverse=True)
                if len(normalize(candidate).replace(" ", "")) >= 2
                and normalize(candidate).replace(" ", "") in compact
            ),
            None,
        )
        if mention:
            skills.append({"mention": mention, "proficiency": "初级"})

    years_match = re.search(r"(\d+(?:\.\d+)?)\s*年(?:工作|开发|项目|相关)?经验", text)
    education = next((degree for degree in ("博士", "硕士", "本科", "大专") if degree in text), "")
    return ResumeRawExtraction(
        skills=skills[:40],
        experience_years=float(years_match.group(1)) if years_match else None,
        education=education,
    )


def _propagate_case_profiles(rows: list[dict]) -> int:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(_case_key(row), []).append(row)
    propagated = 0
    for members in groups.values():
        source = next((row for row in members if row.get("stats") and row.get("profile")), None)
        if source is None:
            continue
        for target in members:
            if target.get("stats"):
                continue
            update_archive(
                target["resume_id"],
                {
                    "stats": source["stats"],
                    "profile": source["profile"],
                    "raw_text": source.get("raw_text", ""),
                    "parse_mode": "shared_case_profile",
                    "profile_source_resume_id": source["resume_id"],
                    "parse_error": "",
                },
            )
            propagated += 1
    return propagated


async def _parse_one(row: dict, resolver, fallback_only: bool = False) -> dict:
    stored = next(OBJECTS.glob(f"{row['resume_id']}.*"), None)
    if stored is None:
        raise FileNotFoundError(f"原始文件不存在: {row['resume_id']}")
    text = parse_document(stored)
    raw = (
        _deterministic_extraction(text, resolver)
        if fallback_only
        else ResumeRawExtraction.model_validate(await extract_resume(text, row["resume_id"]))
    )
    profile = build_profile(row["resume_id"], raw, resolver)
    unresolved = [skill.mention for skill in profile.skills if not skill.skill_id]
    if unresolved:
        candidates = await llm_resolve_unmatched(unresolved, text[:400])
        for skill in profile.skills:
            candidate = candidates.get(skill.mention)
            if skill.skill_id or candidate is None:
                continue
            if candidate.is_skill and candidate.capability_id and candidate.confidence >= 0.6:
                skill.skill_id = candidate.capability_id
                skill.resolved_by = "llm"
                skill.reason = candidate.reason
            else:
                skill.resolved_by = "unmatched"
    data = profile.model_dump(mode="json")
    stats = {
        "totalSkills": len(profile.skills),
        "resolved": sum(1 for skill in profile.skills if skill.skill_id),
        "byDict": sum(1 for skill in profile.skills if skill.resolved_by == "dict"),
        "byLlm": sum(1 for skill in profile.skills if skill.resolved_by == "llm"),
        "unresolved": sum(1 for skill in profile.skills if skill.resolved_by == "unmatched"),
    }
    update_archive(
        row["resume_id"],
        {
            "stats": stats,
            "profile": data,
            "raw_text": text[:2000],
            "parse_mode": "deterministic_fallback" if fallback_only else "llm",
            "parse_error": "",
        },
    )
    return {"resume_id": row["resume_id"], "status": "parsed", **stats}


async def _run_one(
    row: dict,
    resolver,
    semaphore: asyncio.Semaphore,
    fallback_only: bool = False,
) -> tuple[str, dict]:
    async with semaphore:
        try:
            result = await asyncio.wait_for(
                _parse_one(row, resolver, fallback_only=fallback_only), timeout=180
            )
            return "parsed", result
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:300] or "单份解析超时或模型无响应"
            update_archive(row["resume_id"], {"parse_error": error})
            return "failed", {
                "resume_id": row["resume_id"],
                "status": "failed",
                "error": error,
            }


async def run(concurrency: int = 10, fallback_only: bool = False) -> int:
    propagated_before = _propagate_case_profiles(_rows())
    latest = _rows()
    groups: dict[str, list[dict]] = {}
    for row in latest:
        groups.setdefault(_case_key(row), []).append(row)
    rows = []
    suffix_order = {".txt": 0, ".docx": 1, ".pdf": 2}
    for members in groups.values():
        if any(row.get("stats") for row in members):
            continue
        rows.append(
            min(
                members,
                key=lambda row: suffix_order.get(
                    Path(str(row.get("filename", ""))).suffix.lower(), 9
                ),
            )
        )
    resolver = load_resolver()
    semaphore = asyncio.Semaphore(max(1, min(concurrency, 10)))
    run = RunContext("resparse", {"rows": len(rows)})

    done = 0
    started = time.monotonic()

    async def tracked(row: dict) -> dict:
        nonlocal done
        r = await _run_one(row, resolver, semaphore, fallback_only=fallback_only)
        done += 1
        if done % 25 == 0 or done == len(rows):
            rate = done / (time.monotonic() - started) * 60
            eta = (len(rows) - done) / max(rate, 0.01)
            run.log(
                "progress",
                "progress",
                "progress",
                count={
                    "done": done,
                    "total": len(rows),
                    "per_min": round(rate, 1),
                    "eta_min": round(eta),
                },
            )
        return r

    results = await asyncio.gather(*(tracked(row) for row in rows))
    parsed = failed = 0
    for status, result in results:
        if status == "parsed":
            parsed += 1
        else:
            failed += 1
        print(json.dumps(result, ensure_ascii=False))
    propagated_after = _propagate_case_profiles(_rows())
    print(
        json.dumps(
            {
                "cases": len(rows),
                "parsed": parsed,
                "failed": failed,
                "propagated": propagated_before + propagated_after,
                "mode": "deterministic_fallback" if fallback_only else "llm",
            },
            ensure_ascii=False,
        )
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="resparse")
    parser.add_argument("--concurrency", type=int, default=10, help="并行解析数，默认 10")
    parser.add_argument(
        "--fallback-only",
        action="store_true",
        help="跳过模型，按技能词典生成基础画像并在同案例格式间共享",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.concurrency, fallback_only=args.fallback_only)))

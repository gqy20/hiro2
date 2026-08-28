"""resparse: 批量解析已入档但未解析的简历。"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runlog import RunContext  # noqa: E402

from backend.candidates.archive import OBJECTS, update_archive  # noqa: E402
from backend.candidates.parse import (  # noqa: E402
    ResumeRawExtraction,
    build_profile,
    extract_resume,
    llm_resolve_unmatched,
    parse_document,
)
from backend.skills.resolver import load_resolver  # noqa: E402

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


async def _parse_one(row: dict, resolver) -> dict:
    stored = next(OBJECTS.glob(f"{row['resume_id']}.*"), None)
    if stored is None:
        raise FileNotFoundError(f"原始文件不存在: {row['resume_id']}")
    text = parse_document(stored)
    raw = ResumeRawExtraction.model_validate(await extract_resume(text, row["resume_id"]))
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
    update_archive(row["resume_id"], {"stats": stats, "profile": data, "raw_text": text[:2000]})
    return {"resume_id": row["resume_id"], "status": "parsed", **stats}


async def _run_one(row: dict, resolver, semaphore: asyncio.Semaphore) -> tuple[str, dict]:
    async with semaphore:
        try:
            result = await asyncio.wait_for(_parse_one(row, resolver), timeout=180)
            return "parsed", result
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:300] or "单份解析超时或模型无响应"
            update_archive(row["resume_id"], {"parse_error": error})
            return "failed", {
                "resume_id": row["resume_id"],
                "status": "failed",
                "error": error,
            }


async def run(concurrency: int = 10) -> int:
    rows = [row for row in _rows() if not row.get("stats")]
    resolver = load_resolver()
    semaphore = asyncio.Semaphore(max(1, min(concurrency, 10)))
    run = RunContext("resparse", {"rows": len(rows)})

    done = 0
    started = time.monotonic()

    async def tracked(row: dict) -> dict:
        nonlocal done
        r = await _run_one(row, resolver, semaphore)
        done += 1
        if done % 25 == 0 or done == len(rows):
            rate = done / (time.monotonic() - started) * 60
            eta = (len(rows) - done) / max(rate, 0.01)
            run.log("progress", "progress", "progress",
                    count={"done": done, "total": len(rows),
                           "per_min": round(rate, 1), "eta_min": round(eta)})
        return r

    results = await asyncio.gather(*(tracked(row) for row in rows))
    parsed = failed = 0
    for status, result in results:
        if status == "parsed":
            parsed += 1
        else:
            failed += 1
        print(json.dumps(result, ensure_ascii=False))
    print(json.dumps({"total": len(rows), "parsed": parsed, "failed": failed}, ensure_ascii=False))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="resparse")
    parser.add_argument("--concurrency", type=int, default=10, help="并行解析数，默认 10")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.concurrency)))

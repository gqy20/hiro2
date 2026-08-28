"""jdxtract: JD 详情正文的结构化解析（职责/要求/技能提及）+ 词典归一。

用法：
    uv run scripts/jdxtract.py run [--limit N]

数据源（自动合并，按 jd_id/encryptJobId 去重，断点续跑）：
    51job 新采集  data/raw/jd/opencli/jd_har_detail_raw.jsonl
    51job 旧修复  data/processed/jd-opencli/norm-jd.jsonl（quality=usable）
    boss          data/raw/jd/boss/boss_detail.jsonl（并入 boss_raw 元数据）
输出 data/processed/jd-opencli/jd-parsed.jsonl，每条含归一结果。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.extraction.models import JDParsed  # noqa: E402
from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402
from backend.skills.resolver import load_resolver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_51 = ROOT / "data" / "raw" / "jd" / "opencli" / "jd_har_detail_raw.jsonl"
NORM_51 = ROOT / "data" / "processed" / "jd-opencli" / "norm-jd.jsonl"
BOSS_DET = ROOT / "data" / "raw" / "jd" / "boss" / "boss_detail.jsonl"
BOSS_RAW = ROOT / "data" / "raw" / "jd" / "boss" / "boss_raw.jsonl"
OUT = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
MIN_DESC = 200
MAX_RETRIES = 2
# 领域过滤不在采集层做：全量解析，由模型输出 is_ai_role 判定，
# 下游 curated 层按判定字段过滤（staged 层不丢数据，判定可审计）。


def load_targets() -> list[dict]:
    """合并三个来源的可解析 JD，返回统一形状。"""
    targets: dict[str, dict] = {}

    def add(jd_id: str, **fields: object) -> None:
        if jd_id and jd_id not in targets:
            targets[jd_id] = {"jd_id": jd_id, **fields}

    if RAW_51.is_file():
        for line in RAW_51.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("status") != "ok":
                continue
            det = rec.get("detail") or {}
            if len(det.get("description") or "") < MIN_DESC:
                continue
            add(
                f"51job:{rec['detail_key']}",
                platform="51job",
                title=det.get("title") or "",
                description=det["description"],
                publish_date=(det.get("issueDate") or "")[:10] or None,
                city=(det.get("location") or "").split(" ")[0] or None,
                work_year=det.get("workYear") or "",
                salary=(det.get("salary") or ""),
            )
    if NORM_51.is_file():
        for line in NORM_51.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("quality") != "usable":
                continue
            add(
                rec["jd_id"],
                platform=rec.get("source_platform", "51job"),
                title=rec.get("title") or "",
                description=rec.get("description") or "",
                publish_date=rec.get("publish_date"),
                city=rec.get("city") or None,
                work_year=rec.get("work_year") or "",
                salary="",
            )
    if BOSS_DET.is_file():
        boss_meta = {}
        if BOSS_RAW.is_file():
            for line in BOSS_RAW.open(encoding="utf-8"):
                r = json.loads(line)
                boss_meta[r["encryptJobId"]] = r
        for line in BOSS_DET.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("description_len", 0) < MIN_DESC:
                continue
            meta = boss_meta.get(rec["encryptJobId"], {})
            add(
                f"boss:{rec['encryptJobId']}",
                platform="boss",
                title=meta.get("jobName") or "",
                description=rec["description"],
                publish_date=None,
                city=meta.get("cityName") or None,
                work_year=meta.get("jobExperience") or "",
                salary=meta.get("salaryDesc") or "",
            )
    for source_dir in ("archive", "corp"):  # archive 先读：同岗位最早观测优先
        for corp_file in sorted((ROOT / "data" / "raw" / "jd" / source_dir).glob("*.jsonl")):
            for line in corp_file.open(encoding="utf-8"):
                rec = json.loads(line)
                add(
                    rec["jd_id"],
                    platform=rec.get("platform", corp_file.stem),
                    title=rec.get("title") or "",
                    description=rec.get("description") or "",
                    publish_date=rec.get("publish_date"),
                    city=rec.get("city") or None,
                    work_year=rec.get("work_year") or "",
                    salary=rec.get("salary") or "",
                )
    kept = [t for t in targets.values() if t["title"]]
    return sorted(kept, key=lambda x: (x["platform"], x["jd_id"]))


def _parse(raw: str) -> JDParsed:
    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    data = json.loads(t)
    if not isinstance(data, dict) or (
        "responsibilities" not in data and "skill_mentions" not in data
    ):
        raise ValueError("输出缺少 responsibilities/skill_mentions")
    data.pop("jd_id", None)
    return JDParsed.model_validate(data)


async def cmd_run(limit: int | None) -> dict:
    settings = LLMSettings()
    run = RunContext("jdxtract", {"cmd": "run", "limit": limit})
    spec = load_prompt("jd-skill")
    provider = build_provider(settings)
    resolver = load_resolver()

    targets = load_targets()
    done: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            done.add(json.loads(line).get("jd_id"))
    todo = [t for t in targets if t["jd_id"] not in done][:limit]
    run.log(
        "jdxtract", "targets_loaded", "progress", count={"total": len(targets), "todo": len(todo)}
    )

    sem = asyncio.Semaphore(15)
    fh = OUT.open("a", encoding="utf-8")
    results, quarantined = [], []

    async def one(t: dict) -> None:
        message = (
            f"职位 ID: {t['jd_id']}\n职位名: {t['title']}\n\nJD 正文:\n{t['description'][:6000]}"
        )
        last_err = "unknown"
        async with sem:
            for attempt in range(1 + MAX_RETRIES):
                user = (
                    message
                    if attempt == 0
                    else f"{message}\n\n上次失败: {last_err}\n重新输出 JSON。"
                )
                try:
                    raw = await provider.complete(
                        system=spec.system,
                        user=user,
                        max_tokens=int(spec.limits.get("max_tokens", 1500)),
                        timeout=float(spec.limits.get("timeout_seconds", 120)),
                    )
                    parsed = _parse(raw)
                except Exception as exc:  # noqa: BLE001 - 校验/API 异常计入重试
                    last_err = f"{type(exc).__name__}: {exc}"[:200]
                    continue
                mentions = parsed.skill_mentions
                resolved = [
                    {"mention": m, "skill_id": r.skill_id, "point_id": r.point_id}
                    for m in mentions
                    if (r := resolver.resolve(m)).skill_id
                ]
                results.append(t["jd_id"])
                fh.write(
                    json.dumps(
                        {
                            "jd_id": t["jd_id"],
                            "is_ai_role": parsed.is_ai_role,
                            "domain_reason": parsed.domain_reason,
                            "platform": t["platform"],
                            "title": t["title"],
                            "publish_date": t["publish_date"],
                            "city": t["city"],
                            "work_year": t["work_year"],
                            "salary": t["salary"],
                            "responsibilities": parsed.responsibilities,
                            "requirements": parsed.requirements,
                            "skill_mentions": mentions,
                            "resolved": resolved,
                            "unresolved": [m for m in mentions if not resolver.resolve(m).skill_id],
                            "rule_version": resolver.version,
                            "prompt_version": spec.version,
                            "model_version": provider.model_version,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                fh.flush()
                return
        quarantined.append({"jd_id": t["jd_id"], "error": last_err})

    try:
        done = 0
        started = time.monotonic()

        async def tracked(t: dict) -> None:
            nonlocal done
            await one(t)
            done += 1
            if done % 25 == 0 or done == len(todo):
                rate = done / (time.monotonic() - started) * 60
                eta = (len(todo) - done) / max(rate, 0.01)
                run.log("progress", "progress", "progress",
                        count={"done": done, "total": len(todo),
                               "per_min": round(rate, 1), "eta_min": round(eta)})

        await asyncio.gather(*(tracked(t) for t in todo))
    finally:
        fh.close()
    metrics = {
        "targets": len(targets),
        "todo": len(todo),
        "parsed": len(results),
        "quarantined": len(quarantined),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        **provider.usage.as_dict(),
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdxtract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    metrics = asyncio.run(cmd_run(args.limit))
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

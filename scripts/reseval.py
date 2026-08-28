"""reseval: 合成简历抽取回归（synthetic，不进官方指标）。

用法：
    uv run scripts/reseval.py run [--layouts txt,docx,pdf,2col] [--limit N]

流程：resumes-div manifest 的 gold 埋点 -> 各版式产物 parse_document ->
LLM 抽取（resume-parse，复用 candmatch._extract）-> 归一化宽松匹配 ->
按版式/画像分组的召回报告。产物 data/runs/<id>/ + resume-regression.json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIV_DIR = ROOT / "data" / "fixtures" / "resumes-div"
OUT_DIR = DIV_DIR / "out"
REPORT = ROOT / "data" / "processed" / "candidates" / "resume-regression.json"

LAYOUT_SUFFIX = {"txt": ".txt", "docx": ".docx", "pdf": ".pdf", "2col": "-2col.pdf"}


def norm(word: str) -> str:
    """匹配归一：NFKC（全角->半角）+ 去全部空白 + 小写。"""
    return unicodedata.normalize("NFKC", word).replace(" ", "").replace("\n", "").lower()


def hit_loose(word: str, extracted: list[str]) -> bool:
    """宽松核心词匹配：归一全等；长词允许双向包含（Spark（PySpark 为主）vs Spark）。

    gold 侧短词（<=3 归一字符）只认全等；抽取侧允许 >=2（标准缩写 RAG 命中
    gold 长注释词 RAG（检索增强生成）），LLM 不会输出单字符技能，误包含风险低。
    """
    nw = norm(word)
    for e in extracted:
        ne = norm(e)
        if nw == ne:
            return True
        if len(nw) > 3 and len(ne) >= 2 and (nw in ne or ne in nw):
            return True
    return False


async def eval_one(manifest_item: dict, layout: str) -> dict:
    """单份 x 单版式：读文件 -> LLM 抽取 -> gold 双口径匹配（宽松为主指标）。"""
    stem = Path(manifest_item["file"]).stem
    from backend.candidates.parse import extract_resume, parse_document

    path = OUT_DIR / f"{stem}{LAYOUT_SUFFIX[layout]}"
    text = parse_document(path)
    raw = await extract_resume(text, stem)
    words = [s.get("mention", "") for s in raw.get("skills", []) if s.get("mention")]
    got = {norm(w) for w in words}
    gold = [g["mention"] for g in manifest_item["gold"]["mentions"]]
    return {
        "file": f"{stem}.{layout}",
        "profile": manifest_item["profile"],
        "gold": len(gold),
        "hit": sum(hit_loose(g, words) for g in gold),
        "hit_strict": sum(norm(g) in got for g in gold),
        "miss": [g for g in gold if not hit_loose(g, words)],
        "extracted_words": words,
    }


def _group(rows: list[dict]) -> dict:
    gold = sum(r["gold"] for r in rows)
    hit = sum(r["hit"] for r in rows)
    hit_strict = sum(r.get("hit_strict", 0) for r in rows)
    return {
        "n": len(rows),
        "gold": gold,
        "recall": round(hit / gold, 3) if gold else None,
        "recall_strict": round(hit_strict / gold, 3) if gold else None,
    }


async def cmd_run(layouts: list[str], limit: int | None, profiles: str | None) -> dict:
    run = RunContext("reseval", {"cmd": "run", "layouts": layouts})
    manifest = json.loads((DIV_DIR / "manifest.json").read_text(encoding="utf-8"))
    items = manifest["items"]
    if profiles:
        want = set(profiles.split(","))
        items = [it for it in items if it["profile"] in want]
    items = items[:limit]
    jobs = [(it, ly) for it in items for ly in layouts]
    sem = asyncio.Semaphore(4)

    async def guarded(it: dict, ly: str) -> dict:
        async with sem:
            try:
                return await eval_one(it, ly)
            except Exception as exc:  # noqa: BLE001
                return {
                    "file": f"{Path(it['file']).stem}.{ly}",
                    "profile": it["profile"],
                    "gold": len(it["gold"]["mentions"]),
                    "hit": 0,
                    "miss": ["<extract_failed>"],
                    "error": str(exc)[:120],
                }

    done = 0
    started = time.monotonic()

    async def tracked(j: tuple) -> object:
        nonlocal done
        r = await guarded(*j)
        done += 1
        if done % 25 == 0 or done == len(jobs):
            rate = done / (time.monotonic() - started) * 60
            eta = (len(jobs) - done) / max(rate, 0.01)
            run.log(
                "progress",
                "progress",
                "progress",
                count={
                    "done": done,
                    "total": len(jobs),
                    "per_min": round(rate, 1),
                    "eta_min": round(eta),
                },
            )
        return r

    rows = list(await asyncio.gather(*(tracked(j) for j in jobs)))
    ok_rows = [r for r in rows if "error" not in r]
    report = {
        "dataset": manifest.get("batch", "diverse-v1"),
        "synthetic": True,
        "note": "回归测试指标，不进入官方评测（evaluation.md 规则）",
        "calls": len(rows),
        "failed": len(rows) - len(ok_rows),
        "overall": _group(ok_rows),
        "by_layout": {
            ly: _group([r for r in ok_rows if r["file"].endswith(f".{ly}")]) for ly in layouts
        },
        "by_profile": {
            p: _group([r for r in ok_rows if r["profile"] == p])
            for p in sorted({r["profile"] for r in ok_rows})
        },
        "miss_detail": [r for r in ok_rows if r["miss"]],
        "rows": ok_rows,
        "errors": [r for r in rows if "error" in r][:5],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    run.finish({"calls": report["calls"], "recall": report["overall"]["recall"]})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reseval")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--layouts", default="txt,docx,pdf,2col")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--profiles", default=None)
    args = parser.parse_args(argv)
    report = asyncio.run(cmd_run(args.layouts.split(","), args.limit, args.profiles))
    print(
        json.dumps(
            {k: report[k] for k in ("overall", "by_layout", "by_profile")},
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

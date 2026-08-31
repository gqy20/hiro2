"""ashby: Ashby 公开招聘板采集（一次 API 全量，无翻页无登录）。

用法：
    uv run scripts/ashby.py run                      # 全部 AI 公司
    uv run scripts/ashby.py run --boards openai      # 单公司

已验证可达的 Ashby 板（2026-08-30 实测）：
    openai       753 岗  Safety/Agent/FDE/Context/Infra 全覆盖
    elevenlabs   248 岗  Voice AI
    xai         (Greenhouse，不在此列)
    cohere       146 岗
    langchain    107 岗  Agent 生态
    perplexity    97 岗
    llamaindex    15 岗  RAG 生态
    runway         4 岗

原理：api.ashbyhq.com/posting-api/job-board/{company} 公开 JSON，
descriptionPlain 直接是纯文本（无需 HTML 剥离）。
产物：data/raw/jd/corp/ashby.jsonl，jd_id 幂等去重。

接入意义：补齐 AI 实验室覆盖盲区——此前池子只有 Anthropic 一家实验室，
AI Safety/Alignment/Context Engineering/Agent Infra 等方向零覆盖。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "jd" / "corp" / "ashby.jsonl"
MIN_DESC = 120  # 过短的多为挂名岗

BOARDS = ["openai", "cohere", "perplexity", "elevenlabs", "langchain", "llamaindex", "runway"]


def _normalize(job: dict, board: str) -> dict | None:
    """Ashby job -> 统一 JD 记录。"""
    jid = job.get("id")
    body = (job.get("descriptionPlain") or "").strip()
    if not jid or len(body) < MIN_DESC:
        return None
    pub = (job.get("publishedAt") or "")[:10]
    return {
        "jd_id": f"ashby-{board}:{jid[:12]}",
        "platform": f"ashby-{board}",
        "title": job.get("title") or "",
        "description": body[:4000],
        "publish_date": pub or None,
        "city": job.get("location") or None,
        "work_year": "",
        "salary": "",
        "keyword": "ALL",
        "job_url": job.get("jobUrl") or "",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def cmd_run(boards: list[str]) -> dict:
    run = RunContext("ashby", {"cmd": "run", "boards": boards})
    seen: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001
                continue

    OUT.parent.mkdir(parents=True, exist_ok=True)
    per_board: dict[str, int] = {}
    for board in boards:
        fresh = 0
        try:
            req = urllib.request.Request(
                f"https://api.ashbyhq.com/posting-api/job-board/{board}",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                jobs = json.loads(r.read()).get("jobs") or []
        except Exception as exc:  # noqa: BLE001 - 单 board 失败不阻塞
            run.log("ashby", board, "WARN", detail=str(exc)[:120])
            jobs = []
        for job in jobs:
            rec = _normalize(job, board)
            if rec and rec["jd_id"] not in seen:
                seen.add(rec["jd_id"])
                with OUT.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fresh += 1
        run.log("ashby", board, "succeeded", count={"new": fresh, "total": len(jobs)})
        per_board[board] = fresh
        time.sleep(random.uniform(1.5, 3.0))

    metrics = {"new": sum(per_board.values()), "per_board": per_board, "total_file": len(seen)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ashby")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--boards", nargs="*", default=BOARDS, help="Ashby 板名列表")
    args = parser.parse_args(argv)
    result = cmd_run(args.boards)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

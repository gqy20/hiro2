"""jdboss: 通过 opencli 标签页导航 + mitmproxy 网络层捕获收集 boss 搜索结果。

链路（对页面零感知，实测通过）：
    opencli browser <session> tab new <搜索URL>   # 仅创建标签页，不附着调试器
      -> 页面 JS 正常计算 __zp_stoken__ 并请求 joblist.json
      -> mitmproxy(scripts/mitmjd.py) 在网络层截获响应体
本脚本按关键词逐个导航，按行偏移把捕获记录归属到关键词，去重写入
data/raw/jd/boss/boss_raw.jsonl。

前提：jdserve 栈在线、Chrome 走 127.0.0.1:8888 代理且已登录 boss、mitmdump 在跑。
用法：
    uv run scripts/jdboss.py run [--pages 1] [--keywords "AI Agent 工程师" ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "data" / "raw" / "jd" / "boss" / "mitm-capture.jsonl"
OUT = ROOT / "data" / "raw" / "jd" / "boss" / "boss_raw.jsonl"
SESSION = "boss1"
NAV_WAIT_SECONDS = 10

KEEP_FIELDS = (
    "encryptJobId",
    "jobName",
    "brandName",
    "brandIndustry",
    "brandScaleName",
    "brandStageName",
    "cityName",
    "areaDistrict",
    "businessDistrict",
    "salaryDesc",
    "jobExperience",
    "jobDegree",
    "skills",
    "jobLabels",
    "welfareList",
    "industry",
    "jobType",
    "proxyJob",
)


def _tab_new(url: str) -> None:
    r = subprocess.run(
        ["opencli", "browser", SESSION, "tab", "new", url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if '"page"' not in r.stdout:
        raise RuntimeError(f"tab new 失败: {r.stdout[:120]} {r.stderr[:120]}")


def _read_jobs(offset: int) -> list[dict]:
    """读取捕获文件 offset 行之后的新记录，返回 jobList 展平结果。"""
    if not CAPTURE.is_file():
        return []
    jobs = []
    with CAPTURE.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i < offset:
                continue
            rec = json.loads(line)
            zp = (rec.get("body") or {}).get("zpData") or {}
            jobs.extend(zp.get("jobList") or [])
    return jobs


def _line_count() -> int:
    if not CAPTURE.is_file():
        return 0
    return sum(1 for _ in CAPTURE.open(encoding="utf-8"))


def cmd_run(keywords: list[str], pages: int) -> dict:
    run = RunContext("jdboss", {"cmd": "run", "keywords": keywords, "pages": pages})
    known: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            known.add(json.loads(line).get("encryptJobId") or "")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fh = OUT.open("a", encoding="utf-8")
    per_keyword: dict[str, int] = {}
    try:
        for kw in keywords:
            kw_new = 0
            for page in range(1, pages + 1):
                offset = _line_count()
                url = (
                    "https://www.zhipin.com/web/geek/job"
                    f"?query={urllib.parse.quote(kw)}&city=100010000&page={page}"
                )
                _tab_new(url)
                time.sleep(NAV_WAIT_SECONDS)
                jobs = _read_jobs(offset)
                fresh = 0
                for j in jobs:
                    jid = j.get("encryptJobId") or ""
                    if not jid or jid in known:
                        continue
                    known.add(jid)
                    fh.write(
                        json.dumps(
                            {
                                "source_platform": "boss",
                                "keyword": kw,
                                "page": page,
                                **{k: j.get(k) for k in KEEP_FIELDS},
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    fresh += 1
                fh.flush()
                kw_new += fresh
                run.log(
                    "jdboss",
                    f"{kw}#p{page}",
                    "progress",
                    item_id=kw,
                    count={"items": len(jobs), "fresh": fresh},
                )
            per_keyword[kw] = kw_new
    finally:
        fh.close()
    metrics = {"new": sum(per_keyword.values()), "per_keyword": per_keyword, "total": len(known)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdboss")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--keywords", nargs="+", required=True)
    p_run.add_argument("--pages", type=int, default=1)
    args = parser.parse_args(argv)
    metrics = cmd_run(args.keywords, args.pages)
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

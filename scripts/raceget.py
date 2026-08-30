"""raceget: 学练赛证"赛"段数据采集（讯飞AI开发者大赛 + 天池 + DataFountain）。

用法：
    uv run scripts/raceget.py run               # 三源全采 + 归一
    uv run scripts/raceget.py xfyun             # 讯飞AI开发者大赛（含往届，分页）
    uv run scripts/raceget.py tianchi           # 阿里天池赛事列表
    uv run scripts/raceget.py datafountain      # DataFountain 竞赛列表

数据源（2026-08-30 实测，全部公开 JSON 无鉴权，详见 docs/research/xlzsz-channels.md）：
  xfyun        https://challenge.xfyun.cn/2020/ai-contest/api/contests/contests-list
  tianchi      https://tianchi.aliyun.com/v3/proxy/competition/api/race/page
  datafountain https://www.datafountain.cn/api/competitions

产物：
  data/raw/races/xfyun.jsonl          讯飞大赛原始快照（算法赛+应用赛全届次）
  data/raw/races/tianchi.jsonl        天池原始快照
  data/raw/races/datafountain.jsonl   DF 原始快照
  data/processed/races/race-catalog.jsonl  三源归一竞赛目录

幂等：全量重写（响应即事实）。讯飞每页 100 条，限速 sleep 0.5s。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "races"
PROC = ROOT / "data" / "processed" / "races"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126", "Accept": "application/json"}
SLEEP = 0.5

XFYUN_API = "https://challenge.xfyun.cn/2020/ai-contest/api/contests/contests-list"
XFYUN_INDUSTRY = "https://challenge.xfyun.cn/2020/ai-contest/api/industry/all"
TIANCHI_API = "https://tianchi.aliyun.com/v3/proxy/competition/api/race/page"
DF_API = "https://www.datafountain.cn/api/competitions"


def _get(url: str, referer: str | None = None) -> dict:
    headers = {**UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 讯飞大赛


def cmd_xfyun(run: RunContext) -> dict:
    """算法赛 + 应用赛双类型全量翻页（含往届，typeBasicProblem=algorithem|application）。"""
    records: list[dict] = []
    for race_type in ("algorithem", "application"):
        page, total_pages = 1, 1
        while page <= total_pages:
            url = f"{XFYUN_API}?typeBasicProblem={race_type}&curPage={page}&pageSize=100"
            data = _get(url, referer="https://challenge.xfyun.cn/competition").get("data") or {}
            batch = data.get("content") or []
            total_pages = data.get("totalPages") or 1
            for x in batch:
                x["_type"] = race_type
            records.extend(batch)
            run.log(
                "xfyun",
                f"{race_type}-p{page}/{total_pages}",
                "progress",
                count={"records": len(records)},
            )
            if not batch:
                break
            page += 1
            time.sleep(SLEEP)
    _write_jsonl(RAW / "xfyun.jsonl", records)

    industries = (
        _get(XFYUN_INDUSTRY, referer="https://challenge.xfyun.cn/competition").get("data") or []
    )
    _write_jsonl(RAW / "xfyun-industries.jsonl", industries)

    by_industry: dict[str, int] = {}
    for x in records:
        ind = x.get("industry") or "未分类"
        by_industry[ind] = by_industry.get(ind, 0) + 1
    top = dict(sorted(by_industry.items(), key=lambda kv: -kv[1])[:8])
    return {"source": "xfyun", "total": len(records), "by_industry_top": top}


# ---------------------------------------------------------------- 天池


def cmd_tianchi(run: RunContext) -> dict:
    """天池赛事分页（pageSize 生效，isActive 空串=全量）。"""
    records: list[dict] = []
    page = 1
    while True:
        url = f"{TIANCHI_API}?visualTab=&raceName=&pageNum={page}&isActive="
        data = _get(url, referer="https://tianchi.aliyun.com/competition").get("data") or {}
        batch = data.get("list") or []
        records.extend(batch)
        run.log("tianchi", f"p{page}", "progress", count={"records": len(records)})
        if not batch or page >= 30:
            break
        page += 1
        time.sleep(SLEEP)
    _write_jsonl(RAW / "tianchi.jsonl", records)
    return {"source": "tianchi", "total": len(records)}


# ---------------------------------------------------------------- DataFountain


def cmd_datafountain(run: RunContext) -> dict:
    """DF 竞赛分页（pageSize 参数生效，实测每页 10 条）。"""
    records: list[dict] = []
    page = 1
    while True:
        url = f"{DF_API}?pageNum={page}&pageSize=10"
        data = _get(url, referer="https://www.datafountain.cn/competitions").get("cmpt") or {}
        batch = data.get("competitions") or []
        records.extend(batch)
        run.log("datafountain", f"p{page}", "progress", count={"records": len(records)})
        if not batch or page >= 30:
            break
        page += 1
        time.sleep(SLEEP)
    _write_jsonl(RAW / "datafountain.jsonl", records)
    return {"source": "datafountain", "total": len(records)}


# ---------------------------------------------------------------- 归一层


def _norm_xfyun(x: dict) -> dict:
    return {
        "race_id": f"xfyun-{x.get('contest_flag') or x.get('name_basic_problem')}",
        "name": x.get("name_basic_problem"),
        "type": "algorithm" if x.get("_type") == "algorithem" else "application",
        "industry": x.get("industry"),
        "organizer": x.get("sponsorName_basic_problem"),
        "bonus": x.get("bonus_basic_problem"),
        "team_count": x.get("team_count"),
        "register_begin": x.get("registerBegin_basic_problem"),
        "register_end": x.get("registerEnd_basic_problem"),
        "final_end": x.get("finalEnd_basic_problem"),
        "description": (x.get("desc_basic_problem") or "")[:400],
        "source": "xfyun",
        "source_url": f"https://challenge.xfyun.cn/topic/info?type={x.get('contest_flag')}",
    }


def _norm_tianchi(x: dict) -> dict:
    return {
        "race_id": f"tianchi-{x.get('raceId')}",
        "name": x.get("name"),
        "type": "algorithm",
        "industry": "",
        "organizer": x.get("orgName") or x.get("organizer"),
        "bonus": x.get("bonus"),
        "team_count": x.get("teamCount"),
        "register_begin": (x.get("signupStartTime") or "")[:10],
        "register_end": (x.get("signupEndTime") or "")[:10],
        "final_end": (x.get("raceEndTime") or "")[:10],
        "highlight": x.get("highlight"),
        "description": (x.get("introduction") or "")[:400],
        "tags": [
            (t.get("tagNameCn") or "").replace("\u200c", "")
            for t in (x.get("tagsList") or [])
            if isinstance(t, dict)
        ],
        "source": "tianchi",
        "source_url": f"https://tianchi.aliyun.com/competition/entrance/{x.get('raceId')}",
    }


def _norm_df(x: dict) -> dict:
    organizers = x.get("organizers") or []
    return {
        "race_id": f"df-{x.get('id')}",
        "name": x.get("title"),
        "type": "algorithm",
        "industry": "",
        "organizer": "; ".join(o.get("name", "") for o in organizers if isinstance(o, dict)),
        "bonus": x.get("reward"),
        "team_count": x.get("teams"),
        "register_begin": (x.get("startTime") or "")[:10],
        "register_end": (x.get("endTime") or "")[:10],
        "final_end": (x.get("endTime") or "")[:10],
        "description": (x.get("subTitle") or "")[:200],
        "tags": [t.get("nameCn") for t in (x.get("tags") or []) if isinstance(t, dict)],
        "source": "datafountain",
        "source_url": f"https://www.datafountain.cn/competitions/{x.get('id')}",
    }


def cmd_normalize(run: RunContext) -> dict:
    records: list[dict] = []
    xf = RAW / "xfyun.jsonl"
    if xf.is_file():
        for line in xf.open(encoding="utf-8"):
            records.append(_norm_xfyun(json.loads(line)))
    tc = RAW / "tianchi.jsonl"
    if tc.is_file():
        for line in tc.open(encoding="utf-8"):
            records.append(_norm_tianchi(json.loads(line)))
    df = RAW / "datafountain.jsonl"
    if df.is_file():
        for line in df.open(encoding="utf-8"):
            records.append(_norm_df(json.loads(line)))
    _write_jsonl(PROC / "race-catalog.jsonl", records)
    by_source: dict[str, int] = {}
    for r in records:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    run.log("normalize", "merged", "SUCCEEDED", count={"total": len(records), **by_source})
    return {"total": len(records), "by_source": by_source}


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raceget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("xfyun")
    sub.add_parser("tianchi")
    sub.add_parser("datafountain")
    sub.add_parser("norm")
    args = parser.parse_args(argv)

    run = RunContext("raceget", {"cmd": args.cmd})
    if args.cmd == "xfyun":
        result = cmd_xfyun(run)
    elif args.cmd == "tianchi":
        result = cmd_tianchi(run)
    elif args.cmd == "datafountain":
        result = cmd_datafountain(run)
    elif args.cmd == "norm":
        result = cmd_normalize(run)
    else:  # run
        result = {
            "xfyun": cmd_xfyun(run),
            "tianchi": cmd_tianchi(run),
            "datafountain": cmd_datafountain(run),
            "norm": cmd_normalize(run),
        }

    run.finish(result)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

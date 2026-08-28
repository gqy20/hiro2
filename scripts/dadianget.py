"""dadianget: 人社部职业分类大典结构化提取（osta.org.cn 官方 API）。

用法：
    uv run scripts/dadianget.py run [--version 2] [--all]
    uv run scripts/dadianget.py versions      # 探测可用的 versionId

API：https://www.osta.org.cn 职业分类大典系统（公开 JSON）
  /api/client/get/tree?versionId=N                    三层树（大/中/小类）
  /api/client/subordinate/data?careerCode=X&versionId=N  逐层下属职业（含官方编码/工种数）

版本现实（2026-08 实测）：versionId=2（2022 版大典）是唯一有职业明细的版本，
1/3 树存在但 subordinate 为空——1999/2015 旧版不在本 API；旧版需走 PDF 转载源。

产物：data/processed/policy/dadian-careers-<ver>.jsonl（职业级，官方编码）
默认只拉数字技术相关小类（--all 拉全部 450 小类，~30 分钟）。
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
OUT_DIR = ROOT / "data" / "processed" / "policy"
API = "https://www.osta.org.cn/api/client"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126",
      "Accept": "application/json"}
SLEEP = 0.6

# 数字技术相关小类的筛选（--all 时跳过）
RELATED_KEYS = ("信息", "数据", "软件", "智能", "计算机", "通信", "互联网",
                "电子", "人工智能")
RELATED_PREFIXES = ("2-02", "4-04", "4-05")


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{API}{path}", headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def cmd_versions() -> dict:
    """探测各 versionId 的可用性（树节点数 + 样本小类职业数）。"""
    out = {}
    for vid in (1, 2, 3, 4):
        try:
            tree = _get(f"/get/tree?versionId={vid}").get("body") or []
            nodes: list[dict] = []

            def walk(ns):
                for n in ns:
                    nodes.append(n)
                    walk(n.get("children") or [])

            walk(tree)
            sample = _get(f"/subordinate/data?careerCode=4-04-05&versionId={vid}").get("body") or []
            out[vid] = {"tree_nodes": len(nodes), "sample_careers": len(sample)}
            time.sleep(SLEEP)
        except Exception as exc:  # noqa: BLE001
            out[vid] = {"error": str(exc)[:80]}
    return out


def cmd_run(version: int, fetch_all: bool) -> dict:
    run = RunContext("dadianget", {"cmd": "run", "version": version, "all": fetch_all})
    tree = _get(f"/get/tree?versionId={version}").get("body") or []
    nodes: list[dict] = []

    def walk(ns):
        for n in ns:
            nodes.append(n)
            walk(n.get("children") or [])

    walk(tree)
    small = [n for n in nodes if n["careerCode"].count("-") == 2]
    if fetch_all:
        related = small
    else:
        related = [n for n in small
                   if any(k in n["careerName"] for k in RELATED_KEYS)
                   or n["careerCode"].startswith(RELATED_PREFIXES)]
    run.log("dadianget", "tree", "progress",
            count={"small": len(small), "related": len(related)})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"dadian-careers-{version}.jsonl"
    seen: set[str] = set()
    if out.is_file():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["career_code"])
            except Exception:  # noqa: BLE001
                continue
    careers: list[dict] = []
    with out.open("a", encoding="utf-8") as fh:
        def emit(code: str, name: str, parent: str, work_num: int) -> None:
            if code and name and code not in seen:
                seen.add(code)
                rec = {"career_code": code, "name": name, "parent": parent,
                       "work_num": work_num, "version_id": version}
                careers.append(rec)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        for i, s in enumerate(related):
            try:
                subs = _get(f"/subordinate/data?careerCode={s['careerCode']}"
                            f"&versionId={version}").get("body") or []
            except Exception:  # noqa: BLE001 - 单小类失败不阻塞
                time.sleep(1)
                continue
            for sub in subs:
                subcode = sub.get("careerCode", "")
                if not subcode:
                    continue
                if sub.get("name"):
                    emit(subcode, sub["name"], s["careerName"], sub.get("workNum", 0))
                else:  # 细类层，再下一层取职业
                    try:
                        leaves = _get(f"/subordinate/data?careerCode={subcode}"
                                      f"&versionId={version}").get("body") or []
                    except Exception:  # noqa: BLE001
                        time.sleep(1)
                        continue
                    for lf in leaves:
                        emit(lf.get("careerCode", ""), lf.get("name", ""),
                             subcode, lf.get("workNum", 0))
                    time.sleep(SLEEP)
            time.sleep(SLEEP)
            if (i + 1) % 10 == 0:
                run.log("dadianget", f"{i+1}/{len(related)}", "progress",
                        count={"careers": len(careers)})

    metrics = {"version": version, "small_categories": len(related),
               "careers": len(careers), "out": str(out.relative_to(ROOT))}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dadianget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("versions")
    p_run = sub.add_parser("run")
    p_run.add_argument("--version", type=int, default=2)
    p_run.add_argument("--all", action="store_true", help="全 450 小类（默认只数字相关）")
    args = parser.parse_args(argv)
    result = cmd_versions() if args.cmd == "versions" else cmd_run(args.version, args.all)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

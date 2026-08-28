"""onetget: O*NET 职业数据库历史版本采集（官方 onetcenter.org，免费公开）。

用法：
    uv run scripts/onetget.py run                  # 下载代表版本序列并提取核心表
    uv run scripts/onetget.py evolution            # 技能需求演化分析

版本 URL 模式：https://www.onetcenter.org/dl_files/database/db_<M>_<m>_text.zip
代表版本（跨越 27 年）：1.0(1998) 5.1(2001) 10.0(2005) 15.0(2010) 20.0(2015)
                       25.1(2020) 30.3(2025)——完整版次列表见 onetcenter.org/database.html
产物：data/raw/onet/db_<M>_<m>/（核心 txt 表）+ data/processed/onet/skills-evolution.json
用途：美国侧技能需求年度快照（职业×技能重要性矩阵），与四层时间轴/大典演化做国际对照。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "onet"
PROC = ROOT / "data" / "processed" / "onet"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126"}

VERSIONS = [
    ("1_0", "1998"), ("5_1", "2001"), ("10_0", "2005"), ("15_0", "2010"),
    ("20_0", "2015"), ("25_1", "2020"), ("30_3", "2025"),
]
# 保留的核心表（版本间文件名略有差异，按子串匹配）
CORE_TABLES = ("Occupation Data", "Skills", "Technology Skills",
               "knowledge", "Abilities", "Interest")


def _download(version: str) -> Path | None:
    dest = RAW / f"db_{version}"
    if (dest / "done").is_file():
        return dest
    # 新版（>=25）在 database/ 子路径带 _text 后缀；老版本在 /dl_files/ 根路径裸 zip
    candidates = (
        f"https://www.onetcenter.org/dl_files/database/db_{version}_text.zip",
        f"https://www.onetcenter.org/dl_files/db_{version}.zip",
    )
    data = None
    for url in candidates:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            break
        except Exception:  # noqa: BLE001 - 尝试下一个 URL 模式
            continue
    if data is None:
        return None
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            base = name.rsplit("/", 1)[-1]
            if any(t.lower() in base.lower() for t in CORE_TABLES):
                z.extract(name, dest)
    (dest / "done").write_text("ok")
    return dest


def _read_tsv(dest: Path, substr: str) -> list[dict]:
    # 精确文件名优先（避免 'Skills' 模糊命中 'Skills to Work Context'）
    matches = sorted(dest.rglob(f"{substr}.txt"))
    if not matches:
        matches = [p for p in dest.rglob("*.txt") if substr.lower() in p.name.lower()]
    if not matches:
        return []
    with matches[0].open(encoding="utf-8", errors="replace", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def cmd_run() -> dict:
    run = RunContext("onetget", {"cmd": "run", "versions": [v for v, _ in VERSIONS]})
    results = {}
    for version, year in VERSIONS:
        dest = _download(version)
        if dest is None:
            run.log("onetget", version, "WARN", detail="下载失败（老版 URL 模式差异）")
            results[year] = None
            continue
        occs = _read_tsv(dest, "Occupation Data")
        skills = _read_tsv(dest, "Skills")
        results[year] = {"occupations": len(occs), "skill_rows": len(skills)}
        run.log("onetget", version, "succeeded",
                count={"occs": len(occs), "skills": len(skills)})
        time.sleep(2)
    metrics = {"versions": {y: r for y, r in results.items()}}
    run.finish({"versions_ok": sum(1 for r in results.values() if r)})
    return metrics


def cmd_evolution() -> dict:
    """关键技能的职业覆盖演化（美国侧 1998-2025）。"""
    watch = ("Machine Learning", "Artificial Intelligence", "Deep Learning",
             "Natural Language Processing", "Data Analysis")
    out = {}
    for version, year in VERSIONS:
        dest = RAW / f"db_{version}"
        if not (dest / "done").is_file():
            continue
        skills = _read_tsv(dest, "Skills")
        tech = _read_tsv(dest, "Technology Skills")
        stats = {}
        for w in watch:
            occs = {r.get("O*NET-SOC Code", "") for r in skills
                    if w.lower() in (r.get("Element Name") or "").lower()}
            tech_occs = {r.get("O*NET-SOC Code", "") for r in tech
                         if w.lower() in (r.get("Example") or "").lower()}
            stats[w] = {"skill_element_occs": len(occs), "tech_occs": len(tech_occs)}
        out[year] = stats
    PROC.mkdir(parents=True, exist_ok=True)
    (PROC / "skills-evolution.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="onetget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("evolution")
    args = parser.parse_args(argv)
    result = cmd_run() if args.cmd == "run" else cmd_evolution()
    print(json.dumps(result, ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

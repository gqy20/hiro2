"""certparse: osta 国家职业标准 PDF -> 工作要求表（职业功能/工作内容/能力+知识要求）。

用法：
    uv run scripts/certparse.py parse <职业编码>    # 解析单份标准 PDF
    uv run scripts/certparse.py parse-all           # 解析 osta-pdf/ 全部 PDF

输入：data/raw/certs/osta-pdf/<编码>.pdf（certget.py pdf 下载）
产物：data/processed/certs/std-requirements/<编码>.jsonl
      每行: level(等级)/func(职业功能)/work_no/work(工作内容)/skills[]/knowledge[]

解析策略（确定性，零 LLM）：
  标准 PDF 的"工作要求"章为四列表格：职业功能|工作内容|专业能力要求|相关知识要求。
  表格含跨行单元格与竖排文字，按行聚类会混列，因此采用列优先策略：
  1. 每页找表头行（含>=3个表头词）校准列 X 边界；"职业功能"常竖排取不到，
     功能/内容分界退化为 工作内容x0-5；表头带（y±25）与页眉行词剔除；
  2. 每页识别等级小节标题（"3.1.x 初级/中级/高级..."），词按 Y 归属最近等级，
     各等级列流独立拼接，避免不同等级的重复表格互相污染；
  3. 各列文本流按编号深度切分：功能列一级(1.)、内容列二级(1.1)、能力/知识列三级(1.1.1)；
  4. 能力列与知识列编号天然成对（同一表格行），按 编号前缀 归并到工作内容记录。
  章节状态：正文"工作要求"标题开启，"权重表/比重"章关闭。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pymupdf  # noqa: E402
from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "raw" / "certs" / "osta-pdf"
OUT_DIR = ROOT / "data" / "processed" / "certs" / "std-requirements"

HEADERS = ("职业功能", "工作内容", "专业能力要求", "相关知识要求", "技能要求")
LEVELS = ("初级", "中级", "高级", "技师", "高级技师")


def _cluster_rows(words: list[tuple], y_tol: float = 3.0) -> list[list[tuple]]:
    """按 Y 顺序聚类成行（同容差内按 X 排序）。"""
    ws = sorted(words, key=lambda w: (w[1], w[0]))
    rows: list[list[tuple]] = [[ws[0]]] if ws else []
    for w in ws[1:]:
        if abs(w[1] - rows[-1][-1][1]) <= y_tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w[0]) for r in rows]


def _find_header(words: list[tuple]) -> tuple[list[float], float] | None:
    """表头行 -> (列 X 边界 [b0,b1,b2], 表头行 y)。

    b0=功能/内容分界：功能列竖排词 x0 在表头左侧较远处（实测 80~91），
    内容列折行词 x0 紧贴内容表头（113~124），取表头左邻词中点。
    """
    for row in _cluster_rows(words):
        hits: dict[str, float] = {}
        for w in row:
            t = w[4].strip()
            if t in ("工作内容", "相关知识要求"):
                hits[t] = float(w[0])
            elif t in ("专业能力要求", "技能要求"):
                hits.setdefault("能力列", float(w[0]))
        if {"工作内容", "能力列", "相关知识要求"} <= set(hits):
            x_work, x_skill, x_know = hits["工作内容"], hits["能力列"], hits["相关知识要求"]
            # 功能/内容分界：左区词 X 聚类取最大间隙中点（功能簇与内容簇间有稳定空隙）
            left_words = [w[0] for w in words if w[0] < x_work and w[4].strip() not in HEADERS]
            b0 = x_work - 20
            if len(left_words) >= 4:
                xs = sorted(left_words)
                gaps = [(xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)]
                g, gi = max(gaps)
                if g > 6:
                    b0 = (xs[gi] + xs[gi + 1]) / 2
            b1 = (x_work + x_skill) / 2
            b2 = (x_skill + x_know) / 2
            return [b0, b1, b2], row[0][1]
    return None


def _col_of(x: float, bounds: list[float]) -> int:
    if x < bounds[0]:
        return 0
    if x < bounds[1]:
        return 1
    if x < bounds[2]:
        return 2
    return 3


def _split_numbered(text: str, depth: int) -> list[tuple[str, str]]:
    """按指定深度的编号切分文本流（depth=1 -> "1."，2 -> "1.1"，3 -> "1.1.1"）。

    返回 [(编号, 正文), ...]；无编号前缀文本挂空编号（表头/说明残片，调用方丢弃）。
    """
    pat = re.compile(rf"(?<![\d.])(\d+(?:\.\d+){{0,{depth - 1}}}\.?)(?![\d.])")
    out: list[tuple[str, str]] = []
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end].strip()
        if body:
            out.append((m.group(1).rstrip("."), body))
    return out


def parse_standard(pdf_path: Path) -> list[dict]:
    """解析标准 PDF 第 3 章工作要求表。"""
    doc = pymupdf.open(pdf_path)
    bounds: list[float] | None = None
    in_ch3 = False
    cur_level = ""
    # streams[(level, col)] -> list[文本块]
    streams: dict[tuple[str, int], list[str]] = {}

    for page in iter(doc):
        text = page.get_text()
        words = page.get_text("words")
        if not words:
            continue
        if re.search(r"^[3\s.．]*工作要求\s*$", text, re.M):
            in_ch3 = True
        elif in_ch3 and re.search(r"^\s*(权重表|4\s*比\S*表|比重\S*)", text, re.M):
            in_ch3 = False
        if not in_ch3:
            continue

        header = _find_header(words)
        if header:
            bounds, header_y = header
        if bounds is None:
            continue

        # 剔除：页眉（含"职业编码"行及以上）与表头带（y±22）
        header_ys = [
            row[0][1]
            for row in _cluster_rows(words)
            if len({w[4].strip() for w in row if w[4].strip() in HEADERS}) >= 3
        ]
        keep: list[tuple] = []
        for w in words:
            if w[4].strip() in HEADERS:
                continue
            if header_ys and any(abs(w[1] - hy) <= 22 for hy in header_ys):
                continue
            keep.append(w)
        # 页眉行：词文本含"职业编码"或 y 小于其行
        codes = [w[1] for w in keep if "职业编码" in w[4]]
        if codes:
            code_y = min(codes)
            keep = [w for w in keep if w[1] > code_y + 3]

        # 等级小节标题（3.1.1 初级 / 3. 1　五级/ 初级工）
        level_marks: list[tuple[float, str]] = []
        level_pat = re.compile(
            r"^(3[.\s\uFF0E]*\d+(?:[.\s\uFF0E]+\d+)?)\s*"
            r"([五四十二十一]级[/／\s\u3000]*(?:初级工|中级工|高级工|技师|高级技师)?|初级|中级|高级|技师|高级技师)"
        )
        for row in _cluster_rows(words):
            joined = "".join(w[4] for w in row)
            m = level_pat.match(joined)
            if m:
                level_marks.append((row[0][1], m.group(2)))

        # 分桶：词归属最近等级的列流
        page_cols: dict[tuple[str, int], list[tuple]] = {}
        for w in keep:
            lvl = cur_level
            for my, ml in level_marks:
                if w[1] >= my - 2:
                    lvl = ml
            key = (lvl, _col_of(w[0], bounds))
            page_cols.setdefault(key, []).append(w)
        if level_marks:
            cur_level = level_marks[-1][1]

        for key, col in page_cols.items():
            col.sort(key=lambda w: (w[1], w[0]))
            stream = "".join(w[4] for w in col)
            # 编号内空格归一："1. 1. 1" -> "1.1.1"（循环替换至收敛）
            for _ in range(3):
                fixed = re.sub(r"(?<![\d.])(\d+\.)\s+(\d+)", r"\1\2", stream)
                if fixed == stream:
                    break
                stream = fixed
            streams.setdefault(key, []).append(stream)
    doc.close()

    # 逐等级切分并归并
    records: list[dict] = []
    level_names = sorted({lvl for lvl, _ in streams} | {cur_level})
    for lvl in level_names:
        func_items = _split_numbered("".join(streams.get((lvl, 0), [])), 1)
        work_items = _split_numbered("".join(streams.get((lvl, 1), [])), 2)
        skill_items = _split_numbered("".join(streams.get((lvl, 2), [])), 3)
        know_items = _split_numbered("".join(streams.get((lvl, 3), [])), 3)

        func_map = {no: t for no, t in func_items if re.fullmatch(r"\d+", no)}
        for no, wtext in work_items:
            if not re.fullmatch(r"\d+\.\d+", no):
                continue  # 功能列一级编号混入内容流时不作工作内容
            func_no = no.split(".")[0]
            record: dict = {
                "level": lvl,
                "func": func_map.get(func_no, ""),
                "work_no": no,
                "work": wtext,
                "skills": list[str](),
                "knowledge": list[str](),
            }
            prefix = no + "."
            for sno, stext in skill_items:
                if sno == no or sno.startswith(prefix):
                    record["skills"].append(f"{sno} {stext}")
            for kno, ktext in know_items:
                if kno == no or kno.startswith(prefix):
                    record["knowledge"].append(f"{kno} {ktext}")
            records.append(record)
    return records


def cmd_parse(run: RunContext, code: str) -> dict:
    pdf = PDF_DIR / f"{code}.pdf"
    if not pdf.is_file():
        raise SystemExit(f"PDF 不存在: {pdf}（先运行 certget.py pdf {code}）")
    records = parse_standard(pdf)
    out = OUT_DIR / f"{code}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_skill = sum(len(r["skills"]) for r in records)
    n_know = sum(len(r["knowledge"]) for r in records)
    run.log(
        "parse",
        code,
        "SUCCEEDED",
        count={"records": len(records), "skills": n_skill, "knowledge": n_know},
    )
    return {
        "code": code,
        "work_items": len(records),
        "skill_items": n_skill,
        "knowledge_items": n_know,
        "out": str(out.relative_to(ROOT)),
    }


def cmd_parse_all(run: RunContext) -> dict:
    results = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        try:
            results.append(cmd_parse(run, pdf.stem))
        except Exception as exc:  # noqa: BLE001
            run.log(
                "parse",
                pdf.stem,
                "ERROR",
                error_type=type(exc).__name__,
                error_message=str(exc)[:100],
            )
    return {
        "parsed": len(results),
        "total_work_items": sum(r["work_items"] for r in results),
        "total_skill_items": sum(r["skill_items"] for r in results),
        "total_knowledge_items": sum(r["knowledge_items"] for r in results),
        "details": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="certparse")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_one = sub.add_parser("parse")
    p_one.add_argument("code", help="职业编码，如 2-02-10-09")
    sub.add_parser("parse-all")
    args = parser.parse_args(argv)

    if args.cmd == "parse":
        run = RunContext("certparse", {"cmd": "parse", "code": args.code})
        result = cmd_parse(run, args.code)
    else:
        run = RunContext("certparse", {"cmd": "parse-all"})
        result = cmd_parse_all(run)

    run.finish(result)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

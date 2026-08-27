"""md2res: Markdown 简历 -> 多版式产物（pdf 单/双栏、docx、txt）。

用法：
    uv run scripts/md2res.py one data/fixtures/resumes-div/md/div_x.md
    uv run scripts/md2res.py all                # 批量转 md/ 下全部

Markdown 是唯一内容源（可手工编辑）；产物可重建，写入 out/。
pdf 用 pandoc(md->html) + PyMuPDF Story 渲染；双栏按节名拆左右两栏。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "fixtures" / "resumes-div"
MD_DIR = BASE / "md"
OUT_DIR = BASE / "out"

# 双栏布局中放左栏的节（其余节放右栏）
LEFT_SECTIONS = {"基本信息", "技能", "技能清单", "教育背景", "教育", "证书", "语言"}


def pandoc(md_path: Path, fmt: str) -> str:
    """调用 pandoc 转换（原生能力优先，不重写解析器）。"""
    r = subprocess.run(
        ["pandoc", str(md_path), "-t", fmt, "--wrap=none"],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout


def _render_story(html: str | list[str], writer, areas) -> None:
    """把 html 渲染进每页的一个或两个区域（双栏 = 两个 Story 并排）。"""
    import pymupdf

    stories = [pymupdf.Story(html=h) for h in ([html] if isinstance(html, str) else html)]
    media = pymupdf.Rect(0, 0, 595, 842)  # A4 介质框
    more = [1] * len(stories)
    while any(more):
        dev = writer.begin_page(media)
        for story, area, i in zip(stories, areas, range(len(stories))):
            if more[i]:
                more[i], _ = story.place(area)
                story.draw(dev)
        writer.end_page()


def to_pdf(html: str, path: Path) -> None:
    """单栏 A4。"""
    import pymupdf

    with pymupdf.DocumentWriter(str(path)) as w:
        _render_story(html, w, [pymupdf.Rect(54, 54, 541, 788)])


def to_pdf_2col(htmls: tuple[str, str], path: Path) -> None:
    """双栏：左窄栏（技能/教育）+ 右宽栏（项目/经历）。"""
    import pymupdf

    with pymupdf.DocumentWriter(str(path)) as w:
        left_area = pymupdf.Rect(40, 40, 205, 800)
        right_area = pymupdf.Rect(215, 40, 555, 800)
        _render_story(list(htmls), w, [left_area, right_area])


def split_sections(md_text: str) -> tuple[str, str]:
    """按 ## 节标题拆成 (左栏 md, 右栏 md)；无节标题时全部进右栏。"""
    import re

    parts = re.split(r"^(#{1,3} .+)$", md_text, flags=re.M)
    left: list[str] = []
    right: list[str] = [parts[0]] if parts and parts[0].strip() else []
    for i in range(1, len(parts), 2):
        header, body = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        name = header.lstrip("#").strip().rstrip("：:")
        (left if name in LEFT_SECTIONS else right).append(header + body)
    return "\n\n".join(left), "\n\n".join(right)


def _md_text(md_path: Path) -> str:
    return md_path.read_text(encoding="utf-8")


def convert(md_path: Path, formats: list[str] | None = None) -> dict:
    """转换单份 md，返回产物清单。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = _md_text(md_path)
    stem = md_path.stem
    formats = formats or ["pdf", "2col", "docx", "txt"]
    made = {}
    if "pdf" in formats:
        p = OUT_DIR / f"{stem}.pdf"
        to_pdf(pandoc(md_path, "html"), p)
        made["pdf"] = p.name
    if "2col" in formats:
        p = OUT_DIR / f"{stem}-2col.pdf"
        left, right = split_sections(text)
        if not left.strip():  # 无左栏节则退化为单栏内容双栏排
            left, right = "", text
        to_pdf_2col((pandoc_text(left), pandoc_text(right)), p)
        made["2col"] = p.name
    if "docx" in formats:
        p = OUT_DIR / f"{stem}.docx"
        subprocess.run(
            ["pandoc", str(md_path), "-o", str(p)],
            check=True,
        )
        made["docx"] = p.name
    if "txt" in formats:
        p = OUT_DIR / f"{stem}.txt"
        p.write_text(pandoc(md_path, "plain"), encoding="utf-8")
        made["txt"] = p.name
    return made


def pandoc_text(md_text: str) -> str:
    """对 md 字符串（非文件）转 html。"""
    r = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "html"],
        input=md_text,
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout


def cmd_all() -> dict:
    mds = sorted(MD_DIR.glob("*.md"))
    if not mds:
        print(f"未找到 md: {MD_DIR}", file=sys.stderr)
        return {"converted": 0}
    results = {}
    for md in mds:
        results[md.name] = convert(md)
    (OUT_DIR / "convert-log.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"converted": len(results), "out_dir": str(OUT_DIR)}


def cmd_one(md_path: Path) -> dict:
    return convert(md_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="md2res")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_one = sub.add_parser("one")
    p_one.add_argument("md")
    sub.add_parser("all")
    args = parser.parse_args(argv)
    if args.cmd == "one":
        if not shutil.which("pandoc"):
            print("需要 pandoc", file=sys.stderr)
            return 1
        out = cmd_one(Path(args.md))
    else:
        out = cmd_all()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

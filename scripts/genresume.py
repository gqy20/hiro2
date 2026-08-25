"""genresume: LLM 生成多样性合成测试简历（synthetic，永不进入评测指标）。

用法：
    uv run scripts/genresume.py run [--n 20]

多样性矩阵：方向（Agent/大模型/RAG/大数据/算法/转行）x 级别（应届/初中级/高级）
x 格式（txt 为主，另生成 2 份 PDF + 2 份 DOCX 练解析器）。
产物 data/fixtures/resumes/synth_<方向>_<级别>_<nn>.<ext> + manifest.json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "fixtures" / "resumes"
MAX_RETRIES = 2

TRACKS = ["agent", "llm", "rag", "bigdata", "algo", "career_change"]
LEVELS = ["junior", "mid", "senior"]
TRACK_CN = {
    "agent": "AI Agent 开发（LangChain/工作流/工具调用）",
    "llm": "大模型应用（微调/推理部署/LLM 应用）",
    "rag": "RAG 与知识库（检索/向量库/文档解析）",
    "bigdata": "大数据开发（Spark/Flink/数仓）",
    "algo": "算法工程师（机器学习/深度学习/CV）",
    "career_change": "转行 AI（原后端/测试转 AI 应用）",
}
LEVEL_CN = {
    "junior": "应届/实习（1 年内，课程项目为主）",
    "mid": "初中级（2-4 年，有落地项目）",
    "senior": "高级（5-8 年，主导过系统设计带过人）",
}

SPEC = """请生成一份中文技术简历全文（纯文本，不要 Markdown 标记符号，用短横线列表）。

要求：
- 方向：{track}
- 级别：{level}
- 包含：个人信息占位（用"李同学/王同学"等假名，电话邮箱写"138****0000"）、
  技能清单（含具体框架工具名与熟练度措辞"精通/熟悉/了解"及年限）、
  2-4 个项目经历（项目名 + 职责 + 技术栈）、教育背景
- 技术细节要真实合理（版本/场景/指标），技能覆盖方向相关主流栈
- 长度 300-600 字；不要输出任何解释，只输出简历正文"""


async def _gen_one(provider, spec, system) -> str:
    last_err = "unknown"
    for attempt in range(1 + MAX_RETRIES):
        try:
            return await provider.complete(system=system, user=spec, max_tokens=1200, timeout=120)
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"[:150]
    raise RuntimeError(f"生成失败: {last_err}")


def _to_pdf(text: str, path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    rect = page.rect
    y = 72
    for line in text.split("\n"):
        if not line.strip():
            y += 8
            continue
        # 简单折行：每行约 40 个全角字符宽度
        for i in range(0, len(line), 40):
            chunk = line[i : i + 40]
            page.insert_text((54, y), chunk, fontname="china-s", fontsize=10)
            y += 16
            if y > rect.height - 54:
                page = doc.new_page()
                y = 72
    doc.save(str(path))
    doc.close()


def _to_docx(text: str, path: Path) -> None:
    from docx import Document

    doc = Document()
    for line in text.split("\n"):
        if line.strip():
            doc.add_paragraph(line.strip())
    doc.save(str(path))


async def cmd_run(n: int) -> dict:
    from backend.infra.llm.provider import build_provider
    from backend.infra.llm.settings import LLMSettings

    run = RunContext("genresume", {"cmd": "run", "n": n})
    provider = build_provider(LLMSettings())
    system = "你是资深技术简历写手，生成真实感强的合成简历用于系统测试。"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    combos = [(t, lv) for t in TRACKS for lv in LEVELS]  # 18 组合
    combos = (combos * 2)[:n]
    manifest = []
    sem = asyncio.Semaphore(3)

    async def one(i: int, track: str, level: str) -> None:
        spec = SPEC.format(track=TRACK_CN[track], level=LEVEL_CN[level])
        async with sem:
            text = await _gen_one(provider, spec, system)
        stem = f"synth_{track}_{level}_{i:02d}"
        ext = "txt"
        (OUT_DIR / f"{stem}.txt").write_text(text, encoding="utf-8")
        # 前两份与后两份转成 PDF/DOCX 练解析器
        if i in (0, 1):
            _to_pdf(text, OUT_DIR / f"{stem}.pdf")
            ext = "pdf"
        elif i in (n - 2, n - 1):
            _to_docx(text, OUT_DIR / f"{stem}.docx")
            ext = "docx"
        manifest.append(
            {"file": f"{stem}.{ext}", "track": track, "level": level, "synthetic": True}
        )
        run.log("genresume", stem, "ok", count=len(text))

    await asyncio.gather(*(one(i, t, lv) for i, (t, lv) in enumerate(combos)))
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(
            {"synthetic": True, "count": len(manifest), "items": manifest},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    metrics = {"generated": len(manifest), "dir": str(OUT_DIR)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="genresume")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--n", type=int, default=20)
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(cmd_run(args.n)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

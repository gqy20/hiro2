"""genresume: LLM 生成多样性合成测试简历（synthetic，永不进入评测指标）。

用法：
    uv run scripts/genresume.py run [--n 20]      # 基础批次（20 份，txt/pdf/docx）
    uv run scripts/genresume.py diverse           # 多样性批次：Markdown 源 + gold 埋点

基础批次：方向（Agent/大模型/RAG/大数据/算法/转行）x 级别 x 格式。
多样性批次：7 类边缘画像 x 方向级别，产物为 Markdown 源（resumes-div/md/），
含生成时埋点的技能清单（gold，供回归测试比对），版式由 scripts/md2res.py 转换产生。
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


# ---------------------------------------------------------------------------
# diverse 批次：边缘画像 x 方向级别 -> Markdown 源 + gold 埋点
# ---------------------------------------------------------------------------

DIV_DIR = ROOT / "data" / "fixtures" / "resumes-div"
DIV_MD = DIV_DIR / "md"

# 7 类边缘画像：每一类瞄准管线的一个薄弱环节
PROFILE_SPECS = {
    "variant": (
        "技能名尽量用真实世界的变体写法：别名（torch、sklearn、HF/HuggingFace）、"
        "带版本号（LangChain 0.2、Python 3.10）、口语化措辞（玩过/搞过/踩过坑）、"
        "中英夹杂（如\"大模型微调 (SFT/LoRA)\"）。不要用标准教科书式技能清单。"
    ),
    "sparse": "技能极少（只有 3-5 个硬技能），应届生，课程项目为主，内容单薄真实。不要凑技能。",
    "buried": "不要独立的技能清单节：所有硬技能只出现在项目经历和工作经历的描述句子里。",
    "noisy": (
        "技能栏混入大量软技能噪声（沟通能力、团队协作、责任心、Office 三件套、抗压能力），"
        "且同一硬技能在技能栏和项目描述中重复出现。软技能至少 5 个。"
    ),
    "mgmt": (
        "10 年以上经验、带团队 8 人以上的技术管理者的简历：技术栈压缩为一行"
        "（如\"技术栈：Java / Python / Spark / Flink\"），重点写架构决策、团队管理和业务结果，"
        "技能细节淡化。"
    ),
    "typo": (
        "排版带真实世界的输入噪声：全角字母数字（如 Ｐｙｔｈｏｎ、ＲＡＧ）、"
        "全半角标点混用、中英文之间多余空格（\"Prompt 工程\"、\"RAG 检索\"）、"
        "个别错别字。噪声要自然，不要每行都有。"
    ),
    "long": "700-1000 字的长简历：5 个项目经历 + 3 段工作经历 + 教育背景 + 证书节，内容详实。",
}

DIV_PLAN = (
    [("variant", t, "mid") for t in TRACKS]  # 6：全方向覆盖
    + [
        ("sparse", "agent", "junior"), ("sparse", "llm", "junior"), ("sparse", "rag", "junior"),
        ("buried", "agent", "mid"), ("buried", "bigdata", "mid"),
        ("buried", "career_change", "mid"),
        ("noisy", "llm", "mid"), ("noisy", "rag", "mid"), ("noisy", "algo", "senior"),
        ("mgmt", "agent", "senior"), ("mgmt", "bigdata", "senior"), ("mgmt", "llm", "senior"),
        ("typo", "rag", "mid"), ("typo", "agent", "junior"), ("typo", "llm", "mid"),
        ("long", "agent", "senior"), ("long", "bigdata", "senior"), ("long", "algo", "senior"),
    ]
)  # 24 份

DIV_SYSTEM = "你是测试数据工程师，为简历解析系统生成高真实感的中文技术合成简历用于测试。"

DIV_SPEC = """请生成一份中文技术简历，Markdown 格式。

要求：
- 方向：{track}
- 级别：{level}
- 画像特征（必须严格遵守）：{profile_spec}
- 节标题用 ## 二级标题，节名从这些里选：基本信息、技能、技能清单、项目经历、工作经历、教育背景、证书
- 个人信息用占位（"李同学"等假名，电话写 138****0000），不要真实联系方式
- 技术细节真实合理，硬技能 {n_skills} 个左右（画像特征另有要求时以画像为准）
- 长度 {length}

先输出埋入的硬技能清单（gold），再输出简历正文，格式严格如下：

===GOLD===
{{"mentions": [{{"mention": "正文原词", "section": "技能", "proficiency": "熟悉", "years": 2}}]}}
===RESUME===
（Markdown 简历正文）

注意：mention 必须逐字出现在正文里（变体/全角按原样）；软技能不进 gold。"""


def _split_gold(raw: str) -> tuple[dict, str]:
    """拆 ===GOLD=== / ===RESUME=== 两段；解析失败抛异常。"""
    parts = raw.split("===RESUME===")
    if len(parts) != 2 or "===GOLD===" not in parts[0]:
        raise ValueError("输出缺少 GOLD/RESUME 分隔标记")
    gold_json = parts[0].split("===GOLD===", 1)[1].strip()
    if gold_json.startswith("```"):
        gold_json = gold_json.split("\n", 1)[1].rsplit("```", 1)[0]
    gold = json.loads(gold_json)
    if not isinstance(gold.get("mentions"), list):
        raise ValueError("gold 缺少 mentions")
    resume = parts[1].strip()
    if resume.startswith("```"):
        resume = resume.split("\n", 1)[1].rsplit("```", 1)[0]
    return gold, resume


def _check_gold(gold: dict, resume: str) -> list[str]:
    """校验埋点与正文对齐，返回未对齐的 mention（空列表 = 通过）。"""
    flat = resume.replace(" ", "").replace("\n", "")
    return [m["mention"] for m in gold["mentions"] if m["mention"].replace(" ", "") not in flat]


async def cmd_diverse() -> dict:
    from backend.infra.llm.provider import build_provider
    from backend.infra.llm.settings import LLMSettings

    run = RunContext("genresume", {"cmd": "diverse", "n": len(DIV_PLAN)})
    provider = build_provider(LLMSettings())
    DIV_MD.mkdir(parents=True, exist_ok=True)
    manifest = []
    sem = asyncio.Semaphore(3)

    async def one(i: int, profile: str, track: str, level: str) -> None:
        spec = DIV_SPEC.format(
            track=TRACK_CN[track], level=LEVEL_CN[level], profile_spec=PROFILE_SPECS[profile],
            n_skills=8 if profile not in ("sparse", "mgmt") else 5,
            length="700-1000 字" if profile == "long" else "300-600 字",
        )
        last_err = "unknown"
        async with sem:
            for attempt in range(1 + MAX_RETRIES):
                try:
                    raw = await provider.complete(
                        system=DIV_SYSTEM, user=spec, max_tokens=2500, timeout=180,
                    )
                    gold, resume = _split_gold(raw)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = f"{type(exc).__name__}: {exc}"[:150]
            else:
                run.log("genresume", f"div_{profile}_{track}_{i:02d}", "error", error=last_err)
                return
        bad = _check_gold(gold, resume)
        stem = f"div_{profile}_{track}_{i:02d}"
        if bad:
            run.log("genresume", stem, "gold_mismatch", count=len(bad))
            return
        (DIV_MD / f"{stem}.md").write_text(resume + "\n", encoding="utf-8")
        manifest.append({
            "file": f"md/{stem}.md", "profile": profile, "track": track, "level": level,
            "synthetic": True, "gold": gold,
        })
        run.log("genresume", stem, "ok", count=len(gold["mentions"]))

    await asyncio.gather(*(one(i, *plan) for i, plan in enumerate(DIV_PLAN)))
    (DIV_DIR / "manifest.json").write_text(
        json.dumps({
            "synthetic": True, "batch": "diverse-v1", "count": len(manifest),
            "note": "埋点 gold 供回归测试比对；synthetic 不进入官方评测指标（evaluation.md 规则）",
            "items": sorted(manifest, key=lambda x: x["file"]),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metrics = {"generated": len(manifest), "plan": len(DIV_PLAN), "dir": str(DIV_MD)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="genresume")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--n", type=int, default=20)
    sub.add_parser("diverse")
    args = parser.parse_args(argv)
    result = cmd_run(args.n) if args.cmd == "run" else asyncio.run(cmd_diverse())
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

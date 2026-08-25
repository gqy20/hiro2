"""candmatch: 候选人画像构建 + 人岗匹配 + 学习路径（主案例 3 管线）。

用法：
    uv run scripts/candmatch.py parse <简历文件> --candidate-id cand_01
    uv run scripts/candmatch.py match cand_01 --job ai-agent-v2
    uv run scripts/candmatch.py demo          # 合成简历端到端（标注 synthetic，不进指标）

parse：PyMuPDF/python-docx 抽文本 -> LLM 结构化（resume-parse.yml）-> resolver 归一
      -> CandidateProfile 存 data/processed/candidates/<id>.json
match：确定性引擎（match-v1）-> MatchReport + LearningPath 存 matches/
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
CAND_DIR = ROOT / "data" / "processed" / "candidates"
MATCH_DIR = ROOT / "data" / "processed" / "candidates" / "matches"
MAX_RETRIES = 2

# 合成测试简历（synthetic：仅开发联调，永不进入评测指标——AGENTS 规则）
SYNTHETIC_RESUME = """张同学 | 本科 · 计算机科学 | 求职方向：AI Agent 开发

技能：
- 精通 Python（3 年），熟悉 FastAPI、REST API 开发
- 熟悉 LangChain、RAG 检索增强，用过向量数据库 Milvus
- 了解 Prompt 工程，写过简单的对话流程
- 熟悉 Git、Docker 基本使用
- 了解机器学习基础（上过吴恩达课程）

项目经历：
1. 校园问答助手：基于 LangChain + Milvus 的 RAG 问答系统，负责检索链路与 Prompt 模板
2. 数据抓取小工具：Python 多线程爬虫 + FastAPI 接口，处理 10 万条数据
3. 课程设计：手写朴素贝叶斯分类器完成文本分类

教育：XX大学 计算机科学与技术 本科
总年限：实习累计约 1 年
"""


def _parse_llm(raw: str) -> dict:
    from backend.candidates.parse import ResumeRawExtraction

    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    data = json.loads(t)
    if not isinstance(data, dict) or "skills" not in data:
        raise ValueError("输出缺少 skills")
    return ResumeRawExtraction.model_validate(data).model_dump()


async def _extract(text: str) -> dict:
    from backend.infra.llm.promptspec import load_prompt
    from backend.infra.llm.provider import build_provider
    from backend.infra.llm.settings import LLMSettings

    spec = load_prompt("resume-parse")
    provider = build_provider(LLMSettings())
    message = f"candidate_id: demo\n\n简历全文:\n{text[:8000]}"
    last_err = "unknown"
    for attempt in range(1 + MAX_RETRIES):
        user = message if attempt == 0 else f"{message}\n\n上次失败: {last_err}\n重新输出 JSON。"
        try:
            raw = await provider.complete(
                system=spec.system,
                user=user,
                max_tokens=int(spec.limits.get("max_tokens", 2000)),
                timeout=float(spec.limits.get("timeout_seconds", 120)),
            )
            return _parse_llm(raw)
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"[:200]
    raise RuntimeError(f"简历抽取失败: {last_err}")


def cmd_parse(resume: Path, candidate_id: str) -> dict:
    run = RunContext("candmatch", {"cmd": "parse", "candidate": candidate_id})
    from backend.candidates.parse import build_profile, parse_document
    from backend.skills.resolver import load_resolver

    text = parse_document(resume)
    run.log("candmatch", "doc_parsed", "progress", count=len(text))
    raw = asyncio.run(_extract(text))
    from backend.candidates.parse import ResumeRawExtraction, llm_resolve_unmatched

    profile = build_profile(candidate_id, ResumeRawExtraction.model_validate(raw), load_resolver())
    # 归一层 2/2：词典未命中的提及交 LLM 归派（候选 + 置信度 >= 0.6 才采用）
    unresolved = [s.mention for s in profile.skills if not s.skill_id]
    if unresolved:
        cands = asyncio.run(llm_resolve_unmatched(unresolved, text[:400]))
        for s in profile.skills:
            if s.skill_id or s.mention not in cands:
                continue
            c = cands[s.mention]
            if c.is_skill and c.capability_id and c.confidence >= 0.6:
                s.skill_id = c.capability_id
                s.resolved_by = "llm"
                s.reason = c.reason
            else:
                s.resolved_by = "unmatched"
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    out = CAND_DIR / f"{candidate_id}.json"
    out.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    by = {}
    for s in profile.skills:
        by[s.resolved_by] = by.get(s.resolved_by, 0) + 1
    metrics = {"candidate": candidate_id, "skills": len(profile.skills), "resolved_by": by}
    run.finish(metrics)
    return metrics


def cmd_match(candidate_id: str, job_version_id: str) -> dict:
    run = RunContext("candmatch", {"cmd": "match", "candidate": candidate_id})
    from backend.candidates.models import CandidateProfile
    from backend.matching.engine import learning_path, match

    profile = CandidateProfile.model_validate_json(
        (CAND_DIR / f"{candidate_id}.json").read_text(encoding="utf-8")
    )
    report = match(profile, job_version_id)
    path = learning_path(report)
    MATCH_DIR.mkdir(parents=True, exist_ok=True)
    (MATCH_DIR / f"{candidate_id}-{job_version_id}-report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (MATCH_DIR / f"{candidate_id}-{job_version_id}-path.json").write_text(
        path.model_dump_json(indent=2), encoding="utf-8"
    )
    metrics = {
        "overall": report.overall_score,
        "required_coverage": report.required_coverage,
        "preferred_coverage": report.preferred_coverage,
        "key_shortboards": report.key_shortboards,
        "path_steps": len(path.steps),
    }
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, list)})
    return metrics


def cmd_demo() -> dict:
    """合成简历端到端：写入 data/fixtures（synthetic 标记），parse -> match。"""
    fixture = ROOT / "data" / "fixtures" / "resume-synthetic.txt"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(SYNTHETIC_RESUME, encoding="utf-8")
    parsed = cmd_parse(fixture, "cand_demo")
    matched = cmd_match("cand_demo", "ai-agent-v2")
    return {"parse": parsed, "match": matched, "synthetic": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="candmatch")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_parse = sub.add_parser("parse")
    p_parse.add_argument("resume")
    p_parse.add_argument("--candidate-id", required=True)
    p_match = sub.add_parser("match")
    p_match.add_argument("candidate_id")
    p_match.add_argument("--job", default="ai-agent-v2")
    sub.add_parser("demo")
    args = parser.parse_args(argv)
    if args.cmd == "parse":
        result = cmd_parse(Path(args.resume), args.candidate_id)
    elif args.cmd == "match":
        result = cmd_match(args.candidate_id, args.job)
    else:
        result = cmd_demo()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

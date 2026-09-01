"""rolexp: 岗位映射 LLM 路径对照实验——在 100 条冻结样本上对比上下文策略。

实验变体（同一 gold：终审 ai-cross-review 锚点，口径与 evalcmp 一致）：
  e1  职责+技能上下文，岗位目录只有 id+分组+名称（单轮）
  e2  e1 + 每岗职责一句话接地（TGRE 式类描述，单轮）
  e3  agent 式：目录只给 id+名，模型按需 lookup_position 查岗位职责（governed loop）
  e4  最优变体 ×3 采样投票（self-consistency）

gold 构建：终审 ACCEPT 期望=当前 repaired 映射；REJECT/MODIFY 期望=修正岗位
（rationale 中锚定）；UNKNOWN 出分母。这与 evalset score 语义一致。

用法：uv run scripts/rolexp.py e1|e2|e3|e4 [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from backend.application.annotate import load_annotations  # noqa: E402
from backend.application.evalaudit import POOLS  # noqa: E402
from backend.infra.llm.agent import TokenBudget, ToolSpec, run_agent  # noqa: E402
from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import AnthropicProvider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402
from backend.jobs.models import RoleMatch  # noqa: E402

SAMPLES = ROOT / "evaluation" / "samples"
REPAIRED = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map-repaired.jsonl"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"

# 终审锚定的修正岗位（ai-cross-review rationale 中锚定，与 annotations 对齐）
FIXED_TARGETS = {
    "task-role_level-029": "pos_05",
    "task-role_level-055": "pos_13",
    "task-role_level-072": "pos_02",
    "task-role_level-095": "pos_36",
    "task-role_level-097": "pos_13",
}


def gold_map() -> dict[str, str | None]:
    """task_id -> 期望岗位（None=应 unmatched）。UNKNOWN 出分母（不进 dict）。"""
    annotations = load_annotations()  # 最新判定生效
    current = {}
    for line in REPAIRED.open(encoding="utf-8"):
        r = json.loads(line)
        current[r["jd_id"]] = r.get("position_id")
    rows = list(csv.DictReader((SAMPLES / "role-mapping.csv").open(encoding="utf-8-sig")))
    gold: dict[str, str | None] = {}
    for i, row in enumerate(rows):
        task_id = f"task-role_level-{i:03d}"
        ann = annotations.get(task_id)
        if ann is None or ann["decision"] == "UNKNOWN":
            continue
        if ann["decision"] == "ACCEPT":
            gold[task_id] = current.get(row["jd_id"])
        elif task_id in FIXED_TARGETS:
            gold[task_id] = FIXED_TARGETS[task_id]
        else:
            gold[task_id] = None  # REJECT/MODIFY 未锚定修正岗 -> 期望 unmatched
    return gold


def _positions_catalog(with_summary: bool) -> str:
    POOLS.load()
    assert POOLS.positions is not None
    lines = []
    for p in POOLS.positions.values():
        line = f"{p['position_id']} {p.get('group')}/{p['name']}"
        if with_summary:
            # TGRE 式类描述：每岗职责第一句（summary 截断到 60 字）
            first = (p.get("summary") or "").split("。")[0][:60]
            line += f"｜{first}"
        lines.append(line)
    return "\n".join(lines)


def build_task(row: dict, jd: dict, catalog: str) -> str:
    resp = "\n".join(f"- {r[:60]}" for r in (jd.get("responsibilities") or [])[:5])
    skills = ", ".join((jd.get("skill_mentions") or [])[:10])
    return (
        f"jd_id: {row['jd_id']}\n职位名: {row['职位名']}\n职责:\n{resp}\n技能: {skills}\n\n"
        f"标准岗位目录:\n{catalog}"
    )


CASE_EMB = ROOT / "data" / "processed" / "eval" / "case-embeddings.jsonl"


def _retrieve_cases(
    jd_id: str, query_text: str, gold: dict, rows: list, parsed: dict
) -> list[dict]:
    """判例库构建（缓存）+ 余弦 top5 检索；leave-one-out 排除自身。"""
    from backend.infra.llm.embedding import cosine, embed_texts, load_embeddings, save_embeddings

    library = load_embeddings(CASE_EMB)
    if not library:
        print("构建判例向量库（首次，一次性）...")
        recs = []
        for task_id, expect in gold.items():
            idx = int(task_id.rsplit("-", 1)[1])
            jd = parsed.get(rows[idx]["jd_id"], {})
            text = rows[idx]["职位名"] + " " + " ".join((jd.get("responsibilities") or [])[:3])
            recs.append({"jd_id": rows[idx]["jd_id"], "expect": expect, "text": text})
        vecs = embed_texts([r["text"] for r in recs])
        for r, v in zip(recs, vecs):
            library.append({**r, "embedding": v})
        save_embeddings(CASE_EMB, library)
        print(f"判例库 {len(library)} 条 -> {CASE_EMB}")

    qv = embed_texts([query_text[:600]])[0]
    scored = []
    for c in library:
        if c["jd_id"] == jd_id:  # leave-one-out：不得检索到自身
            continue
        scored.append((cosine(qv, c["embedding"]), c))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, c in scored[:5]:
        idx_by_jd = next(i for i, r in enumerate(rows) if r["jd_id"] == c["jd_id"])
        jd = parsed.get(c["jd_id"], {})
        out.append(
            {
                "title": rows[idx_by_jd]["职位名"],
                "expect": c["expect"] or "unmatched（不属46岗目录）",
                "resp": "; ".join((jd.get("responsibilities") or [])[:2])[:60],
                "score": round(score, 3),
            }
        )
    return out


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1 :] if nl != -1 else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


async def run_variant(variant: str, limit: int | None) -> dict:
    spec = load_prompt("role-exp")
    porter = AnthropicProvider(LLMSettings())
    rows = list(csv.DictReader((SAMPLES / "role-mapping.csv").open(encoding="utf-8-sig")))
    parsed = {json.loads(line)["jd_id"]: json.loads(line) for line in PARSED.open(encoding="utf-8")}
    gold = gold_map()
    tasks = [(f"task-role_level-{i:03d}", r) for i, r in enumerate(rows)]
    tasks = [(t, r) for t, r in tasks if t in gold][: limit or 100]

    catalog = _positions_catalog(variant in ("e2", "e5"))
    run = RunContext("rolexp", {"variant": variant, "n": len(tasks)})

    correct = total = 0
    detail_lines = []
    for i, (task_id, row) in enumerate(tasks, 1):
        jd = parsed.get(row["jd_id"], {})
        task_text = build_task(row, jd, catalog)
        pred: str | None = None
        if variant in ("e1", "e2"):
            try:
                raw = await porter.complete(
                    system=spec.system,
                    user=task_text,
                    max_tokens=1500,
                    timeout=float(spec.limits.get("timeout_seconds", 120)),
                )
                m = RoleMatch.model_validate(json.loads(_strip_fences(raw)))
                pred = m.position_id if m.is_match else None
            except Exception:
                pred = "CALL_ERROR"
        elif variant == "e3":
            from backend.application.evalaudit import PositionQuery

            def lookup_position(position_id: str) -> str:
                POOLS.load()
                assert POOLS.positions is not None
                p = POOLS.positions.get(position_id)
                return (
                    json.dumps(
                        {"name": p["name"], "summary": (p.get("summary") or "")[:300]},
                        ensure_ascii=False,
                    )
                    if p
                    else f"未找到 {position_id}"
                )

            tools = [
                ToolSpec(
                    name="lookup_position",
                    description="按 position_id 查标准岗位职责说明",
                    args_model=PositionQuery,
                    func=lookup_position,
                )
            ]
            result = await run_agent(
                porter=porter,
                spec=spec,
                tools=tools,
                task=task_text,
                output_model=RoleMatch,
                run_dir=run.dir / "cases" / task_id,
                max_steps=4,
                budget=TokenBudget(total_tokens=15000),
                exit_tool=None,
            )
            if result.output:
                m = RoleMatch.model_validate(result.output)
                pred = m.position_id if m.is_match else None
            else:
                pred = f"RUN_{result.status}"
        elif variant == "e5":
            # 判例 RAG：职责上下文 + top5 相似已判 JD 判例（leave-one-out 排除自身）
            cases = _retrieve_cases(row["jd_id"], task_text, gold, rows, parsed)
            shot_block = "\n相似 JD 判例（已验证归属）：\n" + "\n".join(
                f"- {c['title'][:40]} -> {c['expect']}（职责: {c['resp'][:50]}）" for c in cases
            )
            sysprompt = spec.system + (
                "\n\n判例使用规则：相似判例是重要参考但不是标签——职责语义仍是首要依据；"
                "判例含 unmatched 归属时说明同类岗位可能不属目录。"
            )
            try:
                raw = await porter.complete(
                    system=sysprompt,
                    user=task_text + shot_block,
                    max_tokens=1500,
                    timeout=float(spec.limits.get("timeout_seconds", 120)),
                )
                m = RoleMatch.model_validate(json.loads(_strip_fences(raw)))
                pred = m.position_id if m.is_match else None
            except Exception:
                pred = "CALL_ERROR"
        elif variant == "e4":
            # 最优单轮变体（e2 形态）×3 采样投票
            votes: list[str | None] = []
            for _ in range(3):
                raw = await porter.complete(
                    system=spec.system,
                    user=task_text,
                    max_tokens=1500,
                    timeout=float(spec.limits.get("timeout_seconds", 120)),
                )
                try:
                    m = RoleMatch.model_validate(json.loads(_strip_fences(raw)))
                    votes.append(m.position_id if m.is_match else None)
                except Exception:
                    votes.append("PARSE_ERROR")
            counts = Counter(votes)
            top, n_top = counts.most_common(1)[0]
            pred = top if n_top >= 2 else votes[0]  # 无多数取首次
        else:
            raise ValueError(f"未知变体 {variant}")

        expect = gold[task_id]
        ok = pred == expect
        correct += ok
        total += 1
        detail_lines.append(
            json.dumps(
                {
                    "task_id": task_id,
                    "title": row["职位名"][:30],
                    "pred": pred,
                    "expect": expect,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )
        if i % 20 == 0:
            print(f"  [{i}/{len(tasks)}] running acc={correct}/{total}")

    acc = round(correct / total, 3) if total else 0
    summary = {
        "variant": variant,
        "n": total,
        "correct": correct,
        "accuracy": acc,
        "token_usage": porter.usage.as_dict(),
    }
    (run.dir / "exp-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run.dir / "exp-detail.jsonl").write_text("\n".join(detail_lines) + "\n", encoding="utf-8")
    run.finish({"accuracy": acc, "correct": correct, "n": total})
    print(f"\n{variant}: accuracy={acc} ({correct}/{total})  tokens={porter.usage.as_dict()}")
    print("gold 口径：终审 ACCEPT 期望=当前映射，REJECT/MODIFY 期望=锚定修正岗位")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rolexp")
    parser.add_argument("variant", choices=("e1", "e2", "e3", "e4", "e5"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    asyncio.run(run_variant(args.variant, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

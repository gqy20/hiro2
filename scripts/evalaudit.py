"""evalaudit CLI：评测抽检智能体——采样与复核。

用法：
    uv run scripts/evalaudit.py sample                # 生成抽检清单（非ACCEPT全选+ACCEPT抽10%）
    uv run scripts/evalaudit.py run [--limit N] [--tasks id1,id2] [--mock]

run 产物（data/runs/<run_id>/）：
  cases/<task_id>/agent-steps.jsonl   每 case 的 agent 全步骤留痕（append-only）
  cases/<task_id>/agent-run.json      每 case 摘要（状态/token/预算）
  audit-report.jsonl                  全部 verdict（含同意项）
  audit-summary.json                  分歧清单 + token 汇总

agent 判定不写入 annotations.jsonl；分歧 case 由人工在 /tasks 复核后才是正式判定。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

from backend.application.annotate import load_annotations  # noqa: E402
from backend.application.evalaudit import (  # noqa: E402
    audit_case,
    find_disagreements,
    load_spotcheck,
    spotcheck_sample,
    write_spotcheck,
)
from backend.infra.llm.agent import ChatTurn  # noqa: E402
from backend.infra.llm.provider import AnthropicProvider, MockChatProvider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402


def cmd_sample() -> int:
    annotations = load_annotations()
    task_ids = spotcheck_sample(annotations)
    path = write_spotcheck(task_ids)
    n_non_accept = sum(1 for t in task_ids if annotations[t]["decision"] != "ACCEPT")
    print(f"抽检清单 {len(task_ids)} 条 -> {path}")
    print(f"  非 ACCEPT 全复核：{n_non_accept}；ACCEPT 抽样：{len(task_ids) - n_non_accept}")
    return 0


def _build_porter(mock: bool, mock_turns: list[ChatTurn] | None = None):
    if mock:
        # mock：全部直接接受预标注（最简单可跑通路径，验证管道不验证判断）
        return MockChatProvider(mock_turns or [])
    return AnthropicProvider(LLMSettings())


async def _run(limit: int | None, only_tasks: list[str] | None, mock: bool) -> dict:
    annotations = load_annotations()
    task_ids = only_tasks or load_spotcheck()
    if limit:
        task_ids = task_ids[:limit]
    run = RunContext("evalaudit", {"cmd": "run", "n_tasks": len(task_ids), "mock": mock})
    cases_dir = run.dir / "cases"
    porter = _build_porter(mock) if not mock else None

    verdicts = []
    totals = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    report_lines = []
    for i, task_id in enumerate(task_ids, 1):
        annotation = annotations.get(task_id)
        if annotation is None:
            print(f"[{i}/{len(task_ids)}] {task_id} 无标注，跳过")
            continue
        if mock:
            # mock 模式：直接给一个接受预标注的 verdict，不烧 API
            layer = {"role_level": "role", "evidence_audit": "domain", "skill_mapping": "event"}[
                task_id.split("-")[1]
            ]
            verdicts.append(
                {
                    "task_id": task_id,
                    "layer": layer,
                    "agent_decision": annotation["decision"],
                    "rationale": "[mock] 透传预标注",
                    "error_type": None,
                }
            )
            report_lines.append(verdicts[-1])
            print(f"[{i}/{len(task_ids)}] {task_id} (mock 透传)")
            continue

        case_dir = cases_dir / task_id
        verdict, result = await audit_case(porter, task_id, annotation, case_dir)
        totals["input_tokens"] += result.usage.get("input_tokens", 0)
        totals["output_tokens"] += result.usage.get("output_tokens", 0)
        totals["calls"] += result.usage.get("calls", 0)
        if verdict is not None:
            verdicts.append(verdict.model_dump())
            report_lines.append(verdict.model_dump())
        else:
            report_lines.append(
                {"task_id": task_id, "agent_status": result.status, "error": result.error}
            )
        decision = verdict.agent_decision if verdict else result.status
        print(f"[{i}/{len(task_ids)}] {task_id}: {decision}")

    # 汇总：verdict 需还原为模型实例以复用分歧逻辑
    from backend.application.evalaudit import AuditVerdict

    parsed = [AuditVerdict.model_validate(v) for v in verdicts]
    disagreements = find_disagreements(parsed, annotations)
    summary = {
        "run_id": run.run_id,
        "n_tasks": len(task_ids),
        "n_verdicts": len(parsed),
        "n_disagreements": len(disagreements),
        "token_totals": totals,
        "disagreements": [d.model_dump() for d in disagreements],
    }
    (run.dir / "audit-report.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in report_lines) + "\n", encoding="utf-8"
    )
    (run.dir / "audit-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.finish(
        {
            "verdicts": len(parsed),
            "disagreements": len(disagreements),
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
        }
    )
    print(
        f"\n完成：{len(parsed)} 判定 / {len(disagreements)} 分歧；"
        f"token: in={totals['input_tokens']} out={totals['output_tokens']}"
    )
    print(f"产物：{run.dir}")
    if disagreements:
        print("人工优先复核：")
        for d in disagreements[:20]:
            print(
                f"  {d.task_id} 预标注={d.prelabel_decision} agent={d.agent_decision} {d.rationale}"
            )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evalaudit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample", help="生成抽检清单")
    p_run = sub.add_parser("run", help="执行抽检复核")
    p_run.add_argument("--limit", type=int, default=None, help="只跑前 N 条")
    p_run.add_argument("--tasks", type=str, default=None, help="逗号分隔的 task_id")
    p_run.add_argument("--mock", action="store_true", help="离线透传模式，不烧 API")
    args = parser.parse_args(argv)

    if args.cmd == "sample":
        return cmd_sample()
    only = args.tasks.split(",") if args.tasks else None
    asyncio.run(_run(args.limit, only, args.mock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

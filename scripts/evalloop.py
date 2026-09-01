"""evalloop CLI：评测-修正飞轮——错误聚类 + 分析智能体 + 规则补丁建议。

用法：
    uv run scripts/evalloop.py run [--layer role|domain|event|all] [--mock]

闭环位置（见 docs/evaluation.md 抽检智能体章节）：
    evalset score -> 本脚本（错误模式 + 补丁建议）-> 人工审核应用（改 rolemap.py）
    -> rolemap 重跑 -> evalcmp 固定样本对比。建议不自动应用；负改进由对比呈现可回滚。

产物（data/runs/<run_id>/）：
  <layer>/agent-steps.jsonl   分析智能体全步骤留痕
  <layer>/agent-run.json      run 摘要（状态/token/预算）
  <layer>/patch-suggestions.json   错误模式 + 补丁建议（人工审核入口）
  summary.json                本轮汇总
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
from backend.application.evalloop import (  # noqa: E402
    analyze_layer,
    collect_error_cases,
    metrics_text,
)
from backend.infra.llm.provider import AnthropicProvider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402

LAYERS = ("role", "domain", "event")


async def _run(layers: list[str], mock: bool) -> None:
    annotations = load_annotations()
    run = RunContext("evalloop", {"cmd": "run", "layers": layers, "mock": mock})
    porter = None if mock else AnthropicProvider(LLMSettings())

    summary: dict[str, object] = {"run_id": run.run_id, "layers": {}}
    for layer in layers:
        cases = collect_error_cases(layer)
        print(f"\n=== {layer} 层：{metrics_text(layer)}；错误 case {len(cases)} 条 ===")
        if not cases:
            print("无错误 case，跳过")
            summary["layers"][layer] = {"n_errors": 0, "skipped": True}
            continue

        if mock:
            # mock：只验证错误收集与落盘，不烧 API
            layer_summary = {
                "n_errors": len(cases),
                "sample": cases[:2],
                "mock": True,
            }
            (run.dir / layer).mkdir(parents=True, exist_ok=True)
            (run.dir / layer / "patch-suggestions.json").write_text(
                json.dumps(layer_summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            summary["layers"][layer] = layer_summary
            print(f"（mock）错误样例: {cases[0]['task_id']} {cases[0]['title'][:30]}")
            continue

        assert porter is not None
        report, result = await analyze_layer(porter, layer, run.dir / layer)
        if report is None:
            print(f"分析未产出有效报告：{result.status} {result.error or ''}")
            summary["layers"][layer] = {"n_errors": len(cases), "status": result.status}
            continue
        payload = {
            "layer": layer,
            "metrics_before": metrics_text(layer),
            "n_error_cases": len(cases),
            "n_annotated": len(annotations),
            "report": report.model_dump(),
            "agent_run": {
                "status": result.status,
                "steps": result.steps,
                "usage": result.usage,
            },
        }
        (run.dir / layer / "patch-suggestions.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary["layers"][layer] = {
            "n_errors": len(cases),
            "n_patterns": len(report.error_patterns),
            "n_suggestions": len(report.suggestions),
            "usage": result.usage,
        }
        print(f"模式 {len(report.error_patterns)} 个 / 建议 {len(report.suggestions)} 条")
        print(f"摘要：{report.summary}")
        for s in report.suggestions:
            print(f"  [{s.target_rule}] {s.change}")
            print(
                f"    预期 {s.expected_gain} | 风险 {s.risk} | 证据 {len(s.evidence_task_ids)} 条"
            )

    (run.dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metrics = {k: v for k, v in summary["layers"].items() if isinstance(v, dict)}
    run.finish(metrics)  # type: ignore[arg-type]
    print(f"\n产物：{run.dir}")
    print("人工审核建议 -> 改 rolemap.py -> 重跑 rolemap + evalcmp 对比")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evalloop")
    p_run = parser.add_subparsers(dest="cmd", required=True).add_parser("run", help="跑一轮分析")
    p_run.add_argument("--layer", choices=(*LAYERS, "all"), default="role")
    p_run.add_argument("--mock", action="store_true", help="只验证错误收集，不烧 API")
    args = parser.parse_args(argv)

    layers = list(LAYERS) if args.layer == "all" else [args.layer]
    asyncio.run(_run(layers, args.mock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

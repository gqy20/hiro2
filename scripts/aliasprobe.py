"""aliasprobe CLI：词表新词闭环——发现、提议、审核入口。

用法：
    uv run scripts/aliasprobe.py probe            # 确定性扫描两路信源（零 LLM 成本）
    uv run scripts/aliasprobe.py propose [--top N] # 提议 agent 查证（烧 LLM）

产物（data/runs/<run_id>/）：
  probe:  alias-candidates.json     新词候选簇（term/来源/频次/样本）
  propose: agent-steps.jsonl        查证全过程留痕
           alias-suggestions.json   词表提议（人工审核入口，格式与 evalloop 补丁一致）

闭环下游：人工审核 -> TITLE_ALIASES 生效 -> rolemap repair 重跑 -> evalcmp 验证。
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

from backend.application.aliasprobe import probe_all, propose_aliases  # noqa: E402
from backend.infra.llm.provider import AnthropicProvider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402


def cmd_probe() -> int:
    run = RunContext("aliasprobe", {"cmd": "probe"})
    candidates = probe_all()
    payload = {"n": len(candidates), "candidates": [c.model_dump() for c in candidates]}
    (run.dir / "alias-candidates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.finish({"n_candidates": len(candidates)})
    print(f"候选 {len(candidates)} 个 -> {run.dir}/alias-candidates.json")
    for c in candidates[:15]:
        src = "JD未匹配" if c.source == "unmatched_jd" else "日报突增"
        print(f"  [{src}] {c.term}  频次={c.jd_freq or c.event_recent}")
    return 0


async def _propose(top: int) -> None:
    run = RunContext("aliasprobe", {"cmd": "propose", "top": top})
    candidates = probe_all()
    if not candidates:
        print("无候选词")
        return
    selected = candidates[:top]
    print(f"对前 {len(selected)} 个候选执行查证（候选总数 {len(candidates)}）")
    porter = AnthropicProvider(LLMSettings())
    suggestions, result = await propose_aliases(porter, selected, run.dir)
    if suggestions is None:
        print(f"提议未产出：{result.status} {result.error or ''}")
        return
    payload = {
        "n_candidates": len(selected),
        "n_suggestions": len(suggestions),
        "token_usage": porter.usage.as_dict(),
        "suggestions": [s.model_dump() for s in suggestions],
    }
    (run.dir / "alias-suggestions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.finish({"n_suggestions": len(suggestions), **porter.usage.as_dict()})
    print(f"\n提议 {len(suggestions)} 条 -> {run.dir}/alias-suggestions.json")
    for s in suggestions:
        if s.action == "add_alias":
            print(f"  [加词] {s.term} -> {s.target_position} (conf={s.confidence}) {s.rationale}")
        elif s.action == "new_position_signal":
            print(f"  [新岗信号] {s.term}  {s.rationale}")
        else:
            print(f"  [弃] {s.term}  {s.rationale}")
    print("\n人工审核后：改 scripts/rolemap.py TITLE_ALIASES -> rolemap repair -> evalcmp 验证")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aliasprobe")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="确定性扫描两路信源（零 LLM）")
    p_propose = sub.add_parser("propose", help="提议 agent 查证（烧 LLM）")
    p_propose.add_argument("--top", type=int, default=15, help="只处理前 N 个候选")
    args = parser.parse_args(argv)

    if args.cmd == "probe":
        return cmd_probe()
    asyncio.run(_propose(args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

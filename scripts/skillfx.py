"""生成能力全景 mock 模式的分岗位图谱 fixture。

用法：uv run python scripts/skillfx.py [version_id ...]
默认为 mock 岗位宇宙（与 apps/web/lib/career-jobs.ts 的 buildMockJobs 对齐，
默认岗位 ai-agent-v2 保留手作 fixture 不覆盖）生成：
    data/fixtures/skill_<version_id>.json

产物与 GET /api/v1/skills/graph 响应同构（复用端点函数，不做转换重复），
仅覆写 mode=synthetic 表明快照来源。重新运行可幂等再生成。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 与 buildMockJobs 对齐，排除默认岗位 ai-agent-v2（手作 fixture）
MOCK_JOBS = ["llm-algo-v2", "bigdata-v3"]


def main() -> None:
    # fixture 必须确定性：禁用 Neo4j 投影校准分支
    os.environ.pop("NEO4J_URI", None)
    from apps.api.main import skills_graph

    for vid in sys.argv[1:] or MOCK_JOBS:
        body = skills_graph(job=vid)
        body["mode"] = "synthetic"
        out = ROOT / "data" / "fixtures" / f"skill_{vid}.json"
        out.write_text(
            json.dumps(body, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[skillfx] {out.name}: {len(body['nodes'])} nodes")


if __name__ == "__main__":
    main()

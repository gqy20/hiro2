"""Rebuild the Neo4j job capability projection from published versions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infra.neo4j import project_job_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "data" / "processed" / "jobversions" / "published"
    versions = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.json"))]
    for version in versions:
        project_job_version(version)
    print(json.dumps({"projected": len(versions)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

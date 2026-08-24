"""运行记录：每次 CLI 运行生成 run_id 与结构化 JSONL 日志。

按 AGENTS.md 第 7 节，运行产物统一放在 data/runs/<run_id>/，
包含 config.json、events.jsonl、metrics.json。
"""

import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

RUNS_DIR = Path("data/runs")

# 必填字段之外的常用可追溯字段，写日志前过滤非法类型
_OPTIONAL_FIELDS = (
    "item_id",
    "source_id",
    "dataset_version",
    "duration_ms",
    "count",
    "error_type",
    "error_message",
    "detail",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class RunContext:
    """单次 CLI 运行的 run_id、事件日志与指标收集。"""

    def __init__(self, component: str, config: dict | None = None) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        self.run_id = f"{stamp}-{uuid.uuid4().hex[:6]}"
        self.component = component
        self.dir = RUNS_DIR / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._events = self.dir / "events.jsonl"
        (self.dir / "config.json").write_text(
            json.dumps(
                {"run_id": self.run_id, "component": component, "config": config or {}},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._t0 = time.monotonic()
        self.log("run", "started", "RUNNING")

    def log(
        self,
        stage: str,
        event: str,
        status: str,
        *,
        level: str = "INFO",
        **fields: object,
    ) -> None:
        record: dict[str, object] = {
            "ts": _now(),
            "level": level,
            "run_id": self.run_id,
            "stage": stage,
            "event": event,
            "component": self.component,
            "status": status,
        }
        for key in _OPTIONAL_FIELDS:
            if key in fields:
                record[key] = fields.pop(key)
        record.update(fields)
        with self._events.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary = fields.get("detail") or event
        print(f"[{self.run_id}] {stage}:{event} {status} {summary}", file=sys.stderr)

    def finish(self, metrics: dict[str, object], status: str = "SUCCEEDED") -> None:
        metrics = {"duration_ms": int((time.monotonic() - self._t0) * 1000), **metrics}
        (self.dir / "metrics.json").write_text(
            json.dumps(
                {"run_id": self.run_id, "status": status, "metrics": metrics},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.log("run", "finished", status, count=metrics)

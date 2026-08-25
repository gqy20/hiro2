"""Application 层 Repository 接口与文件实现（ADR 0006）。

接口先行：Phase B 替换为 PostgresRepository 时 Application 与 API 层零改动。
FileRepository 启动时加载 data/processed 产物（MB 级，内存供给，YAGNI 不做缓存层）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.open(encoding="utf-8")]


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class DataRepository(Protocol):
    def job_changeset(self) -> dict: ...
    def jobversion_draft(self) -> dict: ...
    def emerging(self) -> dict: ...
    def evidence(self) -> list[dict]: ...
    def events_primary(self) -> dict[str, dict]: ...
    def jd_parsed(self) -> dict[str, dict]: ...
    def capabilities(self) -> list[dict]: ...
    def role_map(self) -> list[dict]: ...
    def append_review(self, action: dict) -> None: ...


class FileRepository:
    """读 processed 产物；审核动作 append-only 追加（ADR 0006 决定 4）。"""

    def __init__(self) -> None:
        self._loaded = False
        self._cs: dict = {}
        self._draft: dict = {}
        self._emerging: dict = {}
        self._evidence: list[dict] = []
        self._events: dict[str, dict] = {}
        self._jd: dict[str, dict] = {}
        self._caps: list[dict] = []
        self._roles: list[dict] = []
        self._review_path = P / "review" / "review-actions.jsonl"

    def _ensure(self) -> None:
        if self._loaded:
            return
        self._cs = _load_json(P / "jd-opencli" / "jobchangeset-window-diff.json")
        self._draft = _load_json(P / "jd-opencli" / "jobversion-agent-draft.json")
        self._emerging = _load_json(P / "jd-opencli" / "emerging-agent.json")
        self._evidence = _load_jsonl(P / "evidence" / "evidence.jsonl")
        self._events = {
            e["event_id"]: e
            for e in _load_jsonl(P / "wechat-mp" / "events.jsonl")
            if e.get("is_primary", True)
        }
        self._jd = {r["jd_id"]: r for r in _load_jsonl(P / "jd-opencli" / "jd-parsed.jsonl")}
        self._caps = _load_json(P / "capability-matrix" / "capabilities.json").get(
            "capabilities", []
        )
        self._roles = _load_jsonl(P / "jd-opencli" / "jd-role-map.jsonl")
        self._loaded = True

    def job_changeset(self) -> dict:
        self._ensure()
        return self._cs

    def jobversion_draft(self) -> dict:
        self._ensure()
        return self._draft

    def emerging(self) -> dict:
        self._ensure()
        return self._emerging

    def evidence(self) -> list[dict]:
        self._ensure()
        return self._evidence

    def events_primary(self) -> dict[str, dict]:
        self._ensure()
        return self._events

    def jd_parsed(self) -> dict[str, dict]:
        self._ensure()
        return self._jd

    def capabilities(self) -> list[dict]:
        self._ensure()
        return self._caps

    def role_map(self) -> list[dict]:
        self._ensure()
        return self._roles

    def append_review(self, action: dict) -> None:
        self._review_path.parent.mkdir(parents=True, exist_ok=True)
        with self._review_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(action, ensure_ascii=False) + "\n")

"""Application 层 Repository 接口与文件实现（ADR 0006）。

接口先行：Phase B 替换为 PostgresRepository 时 Application 与 API 层零改动。
FileRepository 启动时加载 data/processed 产物（MB 级，内存供给，YAGNI 不做缓存层）。
"""

from __future__ import annotations

import json
import os
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
    def emerging_roles(self) -> dict: ...
    def evidence(self) -> list[dict]: ...
    def events_primary(self) -> dict[str, dict]: ...
    def jd_parsed(self) -> dict[str, dict]: ...
    def capabilities(self) -> list[dict]: ...
    def role_map(self) -> list[dict]: ...
    def review_actions(self) -> list[dict]: ...

    def append_review(self, action: dict) -> None: ...


class FileRepository:
    """读 processed 产物；审核动作 append-only 追加（ADR 0006 决定 4）。"""

    def __init__(self) -> None:
        self._loaded = False
        self._cs: dict = {}
        self._draft: dict = {}
        self._emerging: dict = {}
        self._emerging_roles: dict = {}
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
        self._emerging_roles = _load_json(P / "jd-opencli" / "emerging-roles.json")
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

    def emerging_roles(self) -> dict:
        self._ensure()
        return self._emerging_roles

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

    def review_actions(self) -> list[dict]:
        """审核事实日志（append-only）；文件为离线/在线统一事实源。"""
        if not self._review_path.is_file():
            return []
        out = []
        for line in self._review_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def append_review(self, action: dict) -> None:
        self._review_path.parent.mkdir(parents=True, exist_ok=True)
        with self._review_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(action, ensure_ascii=False) + "\n")
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            return
        try:
            import psycopg

            with psycopg.connect(dsn) as conn:
                conn.execute(
                    """
                    INSERT INTO review_actions
                        (task_id, target_id, decision, reviewer, note, evidence_ids)
                    VALUES (NULL,%s,%s,%s,%s,%s)
                    """,
                    (
                        action.get("target_id", ""),
                        action.get("decision", "needs_evidence"),
                        action.get("reviewer", os.getenv("HIRO2_REVIEWER", "system")),
                        action.get("note", ""),
                        action.get("evidence_ids", []),
                    ),
                )
                conn.commit()
        except Exception:
            # File audit remains authoritative for offline mode; DB sync retries later.
            return


class PostgresRepository(FileRepository):
    """数据库事实优先；尚未关系化的计算产物保留 FileRepository 回退。"""

    def __init__(self, dsn: str) -> None:
        super().__init__()
        self._dsn = dsn

    def _rows(self, query: str, params: tuple = ()) -> list[dict]:
        import psycopg

        with (
            psycopg.connect(self._dsn) as conn,
            conn.cursor(row_factory=psycopg.rows.dict_row) as cur,
        ):
            cur.execute(query, params)
            return list(cur.fetchall())

    def evidence(self) -> list[dict]:
        rows = self._rows(
            """SELECT evidence_id, source_id, claim_type, published_at, collected_at, quality_score,
                      payload, urls, source_span, review_status FROM evidence"""
        )
        return [
            {
                "evidence_id": row["evidence_id"],
                "source_id": row["source_id"],
                "claim_type": row["claim_type"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                "collected_at": row["collected_at"].isoformat() if row["collected_at"] else None,
                "quality_score": row["quality_score"],
                "payload": row["payload"],
                "urls": row["urls"],
                "source_span": row["source_span"],
                "review_status": row["review_status"],
            }
            for row in rows
        ]

    def events_primary(self) -> dict[str, dict]:
        rows = self._rows(
            """SELECT event_id, summary, title, urls, published_at FROM report_events
               WHERE is_primary"""
        )
        return {
            row["event_id"]: {
                "summary": row["summary"],
                "title": row["title"],
                "urls": row["urls"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
            }
            for row in rows
        }

    def jd_parsed(self) -> dict[str, dict]:
        rows = self._rows(
            "SELECT jd_id, responsibilities, requirements, resolved, publish_date FROM jd_records"
        )
        return {
            row["jd_id"]: {
                "responsibilities": row["responsibilities"],
                "requirements": row["requirements"],
                "resolved": row["resolved"],
                "publish_date": row["publish_date"].isoformat()
                if hasattr(row["publish_date"], "isoformat")
                else (row["publish_date"] or ""),
            }
            for row in rows
        }

    def capabilities(self) -> list[dict]:
        rows = self._rows(
            """SELECT capability_id, name, group_name, sort_order FROM capabilities
               ORDER BY sort_order"""
        )
        return [
            {
                "capability_id": row["capability_id"],
                "name": row["name"],
                "group": row["group_name"],
            }
            for row in rows
        ]


def build_repository() -> DataRepository:
    """DATABASE_URL 配置成功时走事实主库，否则保持可复现离线文件模式。"""
    dsn = os.getenv("DATABASE_URL")
    return PostgresRepository(dsn) if dsn else FileRepository()

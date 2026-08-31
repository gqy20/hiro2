import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402


@pytest.fixture()
def isolated_review_log(tmp_path, monkeypatch):
    """隔离审核事实日志（append-only）。

    发布流与逐条审核类测试统一写临时日志，不污染 data/processed 事实库；
    同时切断 DATABASE_URL，避免审核动作写入 PostgreSQL。日志预置一条
    accepted 动作以满足 jobpub 的发布前置（人工审核留痕）。
    """
    import apps.api.main as api_main
    from scripts import jobpub

    log = tmp_path / "review-actions.jsonl"
    log.write_text(
        '{"target_id": "seed", "decision": "accepted", "note": "fixture seed"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(api_main.svc.repo, "_review_path", log)
    monkeypatch.setattr(jobpub, "REVIEW_LOG", log)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return log

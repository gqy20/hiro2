"""JD 快照域单测：开关解析与快照归档（不联网）。"""

import json
from pathlib import Path

import pytest

from backend.application import snapshot


def test_enabled_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HIRO2_SNAPSHOT_ENABLED", raising=False)
    assert snapshot.snapshot_enabled() is False
    monkeypatch.setenv("HIRO2_SNAPSHOT_ENABLED", "true")
    assert snapshot.snapshot_enabled() is True


def test_archive_snapshot_copies_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corp = tmp_path / "corp"
    corp.mkdir()
    (corp / "tencent.jsonl").write_text('{"jd_id": "tx:1"}\n', encoding="utf-8")
    monkeypatch.setattr(snapshot, "CORP", corp)
    monkeypatch.setattr(snapshot, "SNAPSHOTS", corp / "snapshots")

    stamp1 = snapshot._archive_snapshot()
    day = corp / "snapshots" / stamp1
    assert (day / "tencent.jsonl").is_file()
    # 同日第二轮不覆盖（一天只留首份）
    (corp / "tencent.jsonl").write_text('{"jd_id": "tx:2"}\n', encoding="utf-8")
    stamp2 = snapshot._archive_snapshot()
    assert stamp1 == stamp2
    assert json.loads((day / "tencent.jsonl").read_text(encoding="utf-8"))["jd_id"] == "tx:1"

"""词表新词闭环测试：MockChatProvider 离线，不触真实 API。

覆盖：已覆盖词判定、unmatched 聚类（含 FDE 类新词检出）、突增检测门槛、
提议 agent 提交出口全流程。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import backend.application.aliasprobe as ap  # noqa: E402
from backend.infra.llm.agent import ChatTurn  # noqa: E402
from backend.infra.llm.provider import MockChatProvider  # noqa: E402


def test_is_covered_substring_semantics() -> None:
    """覆盖判定按子串逻辑：已有别名的子串、岗位名片段都算已覆盖。"""
    covered = {"机器学习", "llm", "agent"}
    names = ["大模型算法工程师", "AI Agent开发工程师"]
    assert ap._is_covered("机器学习", covered, names)
    assert ap._is_covered("机器学习平台", covered, names)  # 含已有别名
    assert ap._is_covered("llm", covered, names)
    assert ap._is_covered("大模型算法", covered, names)  # 岗位名子串
    assert not ap._is_covered("machine learning", covered, names)
    assert not ap._is_covered("post training", covered, names)


def test_probe_unmatched_clusters_new_terms(tmp_path: Path, monkeypatch) -> None:
    """unmatched 标题聚类：高频词典外词成候选，已覆盖词与低频词被滤掉。"""
    rows = []
    for i in range(6):  # FDE 出现 6 次 -> 高频新词
        rows.append(
            {"jd_id": f"bd:{i}", "title": f"Frontier Engineer (FDE) #{i}", "method": "unmatched"}
        )
    for i in range(3):  # 低频噪声
        rows.append({"jd_id": f"x:{i}", "title": "冷门词 xyzzy", "method": "unmatched"})
    rows.append(
        {"jd_id": "ok:1", "title": "大模型算法工程师", "method": "exact"}
    )  # 非 unmatched 不扫
    monkeypatch.setattr(ap, "REPAIRED", _fake_jsonl(tmp_path, "repaired", rows))
    monkeypatch.setattr(ap, "_covered_terms", lambda: set())
    monkeypatch.setattr(
        "backend.application.evalaudit.POOLS.positions",
        {"pos_01": {"position_id": "pos_01", "name": "大模型算法工程师"}},
    )

    cands = ap.probe_unmatched_jd(min_freq=5)
    terms = [c.term.lower() for c in cands]
    assert "fde" in terms, terms
    assert not any("xyzzy" in t for t in terms)  # 低频被滤
    fde = next(c for c in cands if c.term.lower() == "fde")
    assert fde.jd_freq == 6 and len(fde.sample_jd_ids) == 6


def test_propose_aliases_submit_flow(tmp_path: Path, monkeypatch) -> None:
    """提议 agent：submit 出口提交提议列表，每步留痕。"""
    suggestions = [
        {
            "term": "machine learning",
            "action": "add_alias",
            "target_position": "大模型算法工程师",
            "confidence": 0.9,
            "rationale": "样本职责均为模型训练与调优",
            "evidence_jd_ids": ["bd:1", "bd:2"],
            "risk": "低",
        },
        {
            "term": "public sector",
            "action": "reject",
            "rationale": "行业词非岗位词",
            "evidence_jd_ids": [],
            "risk": "",
        },
    ]
    porter = MockChatProvider(
        [
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[{"id": "t1", "name": "lookup_jd", "args": {"jd_id": "bd:1"}}],
            ),
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[{"id": "s1", "name": "submit", "args": {"suggestions": suggestions}}],
            ),
        ]
    )
    monkeypatch.setattr(
        "backend.application.evalaudit.POOLS.parsed",
        {
            "bd:1": {
                "title": "ML Engineer",
                "responsibilities": ["模型训练"],
                "skill_mentions": ["ML"],
            }
        },
    )
    cands = [
        ap.AliasCandidate(
            term="machine learning", source="unmatched_jd", jd_freq=76, sample_jd_ids=["bd:1"]
        )
    ]
    result_suggestions, result = asyncio.run(
        ap.propose_aliases(porter, cands, tmp_path / "propose")
    )
    assert result.status == "completed"
    assert result_suggestions is not None and len(result_suggestions) == 2
    s = result_suggestions[0]
    assert s.action == "add_alias" and s.target_position == "大模型算法工程师"
    steps = [
        json.loads(x)
        for x in (tmp_path / "propose" / "agent-steps.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    tools = [r["tool"] for r in steps if r["kind"] == "tool_result"]
    assert tools == ["lookup_jd", "submit"]  # 提交出口留痕


def _fake_jsonl(tmp_path: Path, name: str, rows: list[dict]) -> Path:
    p = tmp_path / f"{name}.jsonl"
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    return p

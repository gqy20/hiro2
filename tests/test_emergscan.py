"""emergscan 涌现岗位扫描器测试：FDE 验证样本必须被自动捞出。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.emergscan import cmd_run  # noqa: E402


def test_fde_detected_as_emerging():
    """FDE（Forward Deployed Engineer）是涌现岗位验证样本：2024-01 仅 1 条，
    2026-08 爆发 134 条、跨 8 平台——扫描器必须自动捞出它。"""
    result = cmd_run()
    assert result["candidates"] >= 1, "应至少产出一个涌现候选"
    out = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/processed/jd-opencli/emerging-roles.json"
        ).read_text(encoding="utf-8")
    )
    fde = next((c for c in out["candidates"] if "forward deployed" in c["keyword"]), None)
    assert fde is not None, "FDE（forward deployed）必须被检出为涌现岗位"
    assert fde["total"] >= 100, "FDE 总量应过百（实测约 137）"
    assert fde["recent_90d"] >= 50, "FDE 近 90 天应有显著量"
    assert fde["growth_ratio"] is None or fde["growth_ratio"] >= 10, "FDE 增长比应极强"
    assert fde["title_variants"] >= 30, "FDE 标题变体应极多（跨公司证据）"
    assert fde["platforms"] >= 5, "FDE 应跨多平台"


def test_known_roles_excluded():
    """已知岗位/技术领域/地名不得作为涌现候选。"""
    out = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/processed/jd-opencli/emerging-roles.json"
        ).read_text(encoding="utf-8")
    )
    for c in out["candidates"]:
        kw = c["keyword"].lower()
        assert "engineer" not in kw.split() or "deployed" in kw, f"泛 engineer 词不应入选: {kw}"
        for geo in ("london", "united kingdom", "singapore", "united states"):
            assert geo not in kw, f"地名不应入选: {kw}"

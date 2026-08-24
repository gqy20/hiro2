"""parsers 纯解析函数测试：用小型夹具验证解析与分级规则。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from parsers import parse_matrix, parse_ts, stage_wechat  # noqa: E402


@pytest.fixture()
def matrix_xlsx(tmp_path: Path) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "岗位能力矩阵"
    ws.append(["分组", "岗位名称", "职责简介", "AI与大模型", "", "数据与编程"])
    ws.append(["", "", "", "LLM应用", "AI Agent", "Python"])
    ws.append(["AI研发", "Agent工程师", "负责智能体构建", 4, 5, 3])
    ws.append(["AI研发", "算法工程师", "负责模型调优", 5, 2, 4])
    ws.append(["AI研发", "坏分值岗位", "", 4, "高", None])
    legend = wb.create_sheet("图例与说明")
    legend.append(["分数含义", "备注"])
    legend.append(["0", "不需要"])
    legend.append(["5", "专家"])
    path = tmp_path / "matrix.xlsx"
    wb.save(path)
    return path


def test_parse_matrix_shapes(matrix_xlsx: Path) -> None:
    parsed = parse_matrix(matrix_xlsx)
    assert len(parsed["positions"]) == 3
    assert len(parsed["capabilities"]) == 3
    assert [c["name"] for c in parsed["capabilities"]] == ["LLM应用", "AI Agent", "Python"]
    # 合并单元格分组向右填充
    assert [c["group"] for c in parsed["capabilities"]] == [
        "AI与大模型",
        "AI与大模型",
        "数据与编程",
    ]
    assert parsed["score_legend"] == {"0": "不需要", "5": "专家"}
    first = parsed["positions"][0]
    assert first["scores"] == {"cap_01": 4, "cap_02": 5, "cap_03": 3}


def test_parse_matrix_flags_bad_scores(matrix_xlsx: Path) -> None:
    parsed = parse_matrix(matrix_xlsx)
    bad = next(p for p in parsed["positions"] if p["name"] == "坏分值岗位")
    assert bad["scores"]["cap_02"] is None and bad["scores"]["cap_03"] is None
    assert any("无法解析的分值" in i for i in parsed["issues"])
    assert any("缺失或越界" in i for i in parsed["issues"])


def test_parse_ts_variants() -> None:
    ok, issue = parse_ts("2026-08-21T01:40:31.1234567+00:00")
    assert ok == "2026-08-21T01:40:31.123456+00:00" and issue is None
    assert parse_ts("不是时间") == (None, "published_at_invalid")
    assert parse_ts("") == (None, "published_at_invalid")


@pytest.fixture()
def wechat_base(tmp_path: Path) -> Path:
    base = tmp_path / "out"
    biz = base / "BIZ1"
    biz.mkdir(parents=True)
    (biz / "2026-08-21-正文.md").write_text("# 早报", encoding="utf-8")
    (biz / "2026-08-21-速览.md").write_text("# 速览", encoding="utf-8")
    (biz / "2026-08-20-孤儿.md").write_text("# 旧文", encoding="utf-8")  # 不在索引
    (base / "jueya-index.csv").write_text(
        "filename,biz,app_msg_id,item_idx,title,published_at,body_status,markdown_path\n"
        "a.md,BIZ1,100,1,正文,2026-08-21T01:40:31.0000000+00:00,succeeded,BIZ1\\2026-08-21-正文.md\n"
        "b.md,BIZ1,100,2,速览,2026-08-21T01:40:31.0000000+00:00,succeeded,BIZ1\\2026-08-21-速览.md\n"
        "c.md,BIZ1,101,1,未保存,2026-08-22T01:00:00.0000000+00:00,failed,\n"
        "d.md,BIZ1,102,1,文件丢失,2026-08-23T01:00:00.0000000+00:00,succeeded,BIZ1\\不存在.md\n",
        encoding="utf-8",
    )
    return base


def test_stage_wechat_statuses(wechat_base: Path) -> None:
    staged = stage_wechat(wechat_base)
    reports = staged["reports"]
    assert len(reports) == 4
    by_title = {r["title"]: r for r in reports}
    assert by_title["正文"]["status"] == "ok"
    assert by_title["正文"]["content_hash"]  # 已回链正文哈希
    assert by_title["未保存"]["issues"] == ["body_not_saved", "body_status=failed"]
    assert by_title["文件丢失"]["status"] == "quarantined"
    assert "file_missing" in by_title["文件丢失"]["issues"]
    # 索引外文件保留，状态降级为 ok_unindexed
    assert len(staged["unindexed"]) == 1
    orphan = staged["unindexed"][0]
    assert orphan["published_date"] == "2026-08-20" and orphan["published_at"] is None
    assert staged["metrics"]["ok"] == 2
    assert staged["metrics"]["body_not_saved"] == 1
    assert staged["metrics"]["first_month"] == "2026-08"

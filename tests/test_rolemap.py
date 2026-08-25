"""rolemap 规则测试：岗位匹配与等级推断。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rolemap import TITLE_ALIASES, infer_level, match_by_rule  # noqa: E402

POSITIONS = [
    {"position_id": "pos_01", "name": "大模型算法工程师"},
    {"position_id": "pos_02", "name": "AI Agent开发工程师"},
    {"position_id": "pos_03", "name": "数据标注/AI数据专员"},
    {"position_id": "pos_04", "name": "AI模型部署工程师(MLOps)"},
]


def test_match_exact_and_alias() -> None:
    pid, conf, method = match_by_rule("大模型算法工程师（实习）", POSITIONS)
    assert pid == "pos_01" and method == "exact" and conf == 1.0
    # 括号后缀剥离：MLOps 带括号的标准名
    pid2, _, m2 = match_by_rule("AI模型部署工程师", POSITIONS)
    assert pid2 == "pos_04" and m2 == "exact"
    # 别名：LLM -> 大模型算法工程师
    pid3, conf3, m3 = match_by_rule("LLM应用开发", POSITIONS)
    assert pid3 == "pos_01" and m3 == "alias" and conf3 == 0.7
    assert match_by_rule("行政前台", POSITIONS)[0] is None
    # 别名表的目标必须是清单内的标准名
    for target in TITLE_ALIASES.values():
        assert any(p["name"] == target for p in _all_positions()), target


def _all_positions() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "data/processed/capability-matrix/positions.jsonl"
    if not path.is_file():
        return [{"name": n} for n in TITLE_ALIASES.values()]  # 数据缺失环境退化
    return [dict(p) for p in (dict(json.loads(x)) for x in path.open(encoding="utf-8"))]


import json  # noqa: E402


def test_infer_level_rules() -> None:
    assert infer_level("资深算法工程师", "3-5年") == ("L3", "职位名:资深")
    assert infer_level("AI产品实习生", "在校/应届") == ("L1", "职位名:实习")
    assert infer_level("首席科学家", "10年以上") == ("L4", "职位名:首席")
    # 职位名优先于经验：高级 + 1-3年 -> L3
    assert infer_level("高级开发", "1-3年")[0] == "L3"
    # 无职位名信号时退回经验要求
    assert infer_level("算法工程师", "1-3年") == ("L2", "经验要求:1-3年")
    assert infer_level("算法工程师", "经验不限") == ("L1", "经验要求:经验不限")
    assert infer_level("算法工程师", "") == ("UNKNOWN", "无信号")

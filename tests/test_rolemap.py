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


def test_has_biz_signal_fde_and_manager_forms() -> None:
    """v4.1 商务信号边界：FDE 含 engineer 放行、Manager 精确形态、中文词不误伤。

    回归背景：FDE 特判首版漏了 key in 判断，所有不含 engineer 的 title
    被误判商务信号（evalcmp 回归 44 拦下）——此测试防止复发。
    """
    from rolemap import _has_biz_signal

    # 普通技术/产品岗不得误伤
    assert _has_biz_signal("产品经理") is False
    assert _has_biz_signal("大模型算法工程师-商业化") is False  # v4.1 撤回的中文宽词
    # FDE：含 engineer 是部署工程岗，放行；无 engineer 才算商务信号
    assert _has_biz_signal("frontieragentsengineer(forwarddeployedengineering)") is False
    assert _has_biz_signal("forwarddeployedspecialist") is True
    # Manager 精确形态命中；Product Manager 不误伤
    assert _has_biz_signal("managerofappliedaiarchitecture") is True
    assert _has_biz_signal("manager-techsolutions(bigdata/ai)") is True
    assert _has_biz_signal("sr.manager–data&ai") is True
    assert _has_biz_signal("aiproductmanager") is False


def test_product_manager_alias_priority() -> None:
    """v4：产品头衔优先于技术词（QQ-Agent产品经理 -> pos_06 而非 pos_02）。"""
    real = _all_positions()
    pid, _, method = match_by_rule("QQ-Agent产品经理", real)
    assert pid == "pos_06" and method == "alias"
    pid2, _, _ = match_by_rule("豆包AI大模型产品实习生-Data AML", real)
    assert pid2 == "pos_06"

"""JD 存量修复测试：字段错位、location 拆分、薪资解析、质量分档。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from jdclean import _quality, fix_51job, fix_boss, parse_salary  # noqa: E402


def test_parse_salary_variants() -> None:
    assert parse_salary("3-5万") == (30, 50)
    assert parse_salary("2.5-4万") == (25, 40)
    assert parse_salary("1.8-3.5万·13薪") == (18, 35)
    assert parse_salary("9-14K") == (9, 14)
    assert parse_salary("面议") is None
    assert parse_salary("") is None


def test_fix_51job_shifts_and_location_split() -> None:
    det = {
        "title": "APP下载",  # 网页标题损坏
        "location": "北京\n3-4年\n招1人",
        "companyType": "北京三快在线科技有限公司",  # 实为公司名
        "companySize": "已上市",  # 实为类型
        "companyIndustry": "10000人以上 / 在线生活服务(O2O)",  # 规模 / 行业
    }
    search = {
        "title": "骑行-数据开发工程师",
        "company": "美团",
        "city": "北京",
        "industry": "互联网",
    }
    fixed = fix_51job(det, search)
    assert fixed["title"] == "骑行-数据开发工程师"  # 以搜索层为准
    assert fixed["company"] == "北京三快在线科技有限公司"
    assert fixed["company_type"] == "已上市"
    assert fixed["company_size"] == "10000人以上"
    assert fixed["industry"] == "在线生活服务(O2O)"
    assert fixed["city"] == "北京"
    assert fixed["work_year"] == "3-4年"
    # 搜索层兜底：详情字段全空时
    fixed2 = fix_51job({}, search)
    assert fixed2["title"] == "骑行-数据开发工程师" and fixed2["city"] == "北京"


def test_fix_boss_passthrough() -> None:
    det = {
        "name": "ai工程师",
        "company": "未名融智",
        "stage": "B轮",
        "scale": "20-99人",
        "industry": "计算机软件",
        "city": "北京",
        "experience": "经验不限",
    }
    fixed = fix_boss(det)
    assert fixed["title"] == "ai工程师"
    assert fixed["company_size"] == "20-99人" and fixed["work_year"] == "经验不限"


def test_quality_tiers() -> None:
    assert _quality("AI 工程师", 561) == "usable"
    assert _quality("AI 工程师", 30) == "insufficient_desc"
    assert _quality("", 800) == "missing_title"

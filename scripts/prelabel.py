"""prelabel: 评测样本 AI 预标注——生成建议判定，供人工确认后回流。

用法：
    uv run scripts/prelabel.py          # 生成/重新生成预标注建议
    uv run scripts/prelabel.py apply    # 批量采纳建议写入正式标注（透明标记）

原则（与产品哲学一致）：AI 只产候选，不直接成为标注事实。
本脚本输出 evaluation/prelabels.jsonl（建议判定 + 置信度 + 理由），
不计入 evalset.py score；人工在 /tasks 页确认或修改后才写入
annotations.jsonl 并计入指标。
apply 子命令用于基线摸底：批量采纳的标注以 reviewer_id=ai-prelabel-batch
透明标记，与人工判定可区分；正式指标宣称前仍需人工抽检覆盖。
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "prelabels.jsonl"
PRELABEL_BY = "claude-prelabel-v3-20260828"

# task 序号 -> (decision, confidence, rationale, corrected_position_id|None)
# v2 判定（eval-v2-20260828 冻结样本）
# 口径：ACCEPT=系统输出正确；MODIFY=方向错但有可修正映射；REJECT=不应映射/漏判
ROLE: dict[int, tuple[str, float, str, str | None]] = {
    # exact 15 条：名称精确匹配全部正确
    **{i: ("ACCEPT", 0.98, "名称精确匹配，岗位语义一致", None) for i in range(15)},
    # alias 25 条
    15: ("ACCEPT", 0.9, "增长策略产品经理归产品岗，口径一致", None),
    16: ("ACCEPT", 0.95, "算法工程师（搜索）即pos_01", None),
    17: ("ACCEPT", 0.85, "机器学习推理框架研发归算法岗可接受", None),
    18: ("ACCEPT", 0.9, "大数据平台后台开发即pos_11", None),
    19: ("ACCEPT", 0.95, "CV算法实习即pos_27", None),
    20: ("ACCEPT", 0.95, "Agent架构研发即pos_02", None),
    21: ("ACCEPT", 0.95, "大模型算法专家即pos_01", None),
    22: ("MODIFY", 0.85, "Agent产品经理是产品岗，“Agent”别名误中研发岗", "pos_06"),
    23: ("ACCEPT", 0.95, "NLP算法即pos_04", None),
    24: ("ACCEPT", 0.7, "大模型Agent算法专家pos_01/02边界，可接受", None),
    25: ("ACCEPT", 0.9, "用户产品经理归产品岗", None),
    26: ("ACCEPT", 0.95, "多模态大模型算法即pos_01", None),
    27: ("ACCEPT", 0.9, "多模态算法工程师归算法岗", None),
    28: ("ACCEPT", 0.9, "AI技术研发工程师归算法岗", None),
    29: ("MODIFY", 0.7, "视觉大模型推理部署工程师核心职责是推理部署，应归MLOps", "pos_05"),
    30: ("ACCEPT", 0.95, "AI应用工程师（知识库）即pos_02，v1漏判已修复", None),
    31: ("ACCEPT", 0.9, "数据挖掘算法归算法岗", None),
    32: ("MODIFY", 0.85, "产品实习生被“大模型”误中算法岗，应归产品岗", "pos_06"),
    33: ("ACCEPT", 0.85, "高性能计算（大模型）归算法/系统岗可接受", None),
    34: ("REJECT", 0.85, "Engineering Manager是管理岗，不应映射技术岗（BIZ未覆盖EM）", None),
    35: ("REJECT", 0.9, "项目管理岗被“AI应用”误中，应unmatched", None),
    36: ("ACCEPT", 0.95, "大模型算法研究员即pos_01", None),
    37: ("MODIFY", 0.85, "大模型数据平台产品经理是产品岗，“大模型”别名优先序误伤", "pos_06"),
    38: ("ACCEPT", 0.9, "算法工程师（地理位置）归算法岗", None),
    39: ("ACCEPT", 0.9, "Agent Infra研发即pos_02", None),
    # llm 50 条
    40: ("ACCEPT", 0.9, "运筹优化算法归算法岗", None),
    41: ("ACCEPT", 0.9, "多模态算法实习归算法岗", None),
    42: ("ACCEPT", 0.75, "机器人运动控制算法归算法岗可接受", None),
    43: ("ACCEPT", 0.9, "AI前线部署工程师族校验归pos_05，正确", None),
    44: ("ACCEPT", 0.9, "具身智能3D仿真归数字孪生，准确", None),
    45: ("ACCEPT", 0.9, "模型推理平台算法专家归算法岗", None),
    46: ("ACCEPT", 0.85, "算法实习生归pos_01", None),
    47: ("MODIFY", 0.65, "AI模型开发工程师偏模型研发，非部署", "pos_01"),
    48: ("REJECT", 0.85, "支持工程经理是管理岗，应unmatched", None),
    49: ("ACCEPT", 0.85, "AI芯片计算软件架构归芯片域可接受", None),
    50: ("ACCEPT", 0.9, "AI应用科学家归算法岗", None),
    51: ("ACCEPT", 0.9, "算法实习生（搜索推荐）归pos_01", None),
    52: ("ACCEPT", 0.95, "大语言模型应用算法研究即pos_01", None),
    53: ("REJECT", 0.85, "AI测试开发是测试岗非MLOps，应unmatched", None),
    54: ("ACCEPT", 0.9, "推荐算法实习归pos_01", None),
    55: ("MODIFY", 0.6, "异构硬件性能评估偏基础设施性能工程", "pos_13"),
    56: ("ACCEPT", 0.65, "大规模训练研究归基础设施边界接受", None),
    57: ("ACCEPT", 0.9, "AI基础设施SRE即pos_13", None),
    58: ("REJECT", 0.85, "整机项目经理是硬件项目管理，非产品经理，应unmatched", None),
    59: ("REJECT", 0.7, "业务系统架构师与CAIO语义不符，应unmatched", None),
    60: ("ACCEPT", 0.85, "算法实习生（质量技术）归pos_01", None),
    61: ("ACCEPT", 0.9, "数据科学（AI业务）归pos_35", None),
    62: ("ACCEPT", 0.85, "多模态预训练研究员归pos_04对口", None),
    63: ("REJECT", 0.8, "应用AI架构经理是管理岗，应unmatched", None),
    64: ("ACCEPT", 0.9, "多模态世界模型算法归pos_01", None),
    65: ("ACCEPT", 0.9, "智能嗅觉=气味传感器，归智能传感器工程师准确", None),
    66: ("ACCEPT", 0.8, "AI原生数据库系统归大数据域可接受", None),
    67: ("ACCEPT", 0.85, "企业基础设施软件工程师即pos_13", None),
    68: ("ACCEPT", 0.85, "算法实习生归pos_01", None),
    69: ("ACCEPT", 0.9, "可控视频生成研究归视觉族，族校验正确", None),
    70: ("ACCEPT", 0.85, "算法专家归pos_01", None),
    71: ("ACCEPT", 0.9, "数据挖掘算法实习归pos_01", None),
    72: ("ACCEPT", 0.8, "GenAI软件工程师归算法岗可接受", None),
    73: ("ACCEPT", 0.8, "数据平台后端归大数据域可接受", None),
    74: ("MODIFY", 0.8, "Applied AI Engineer应归应用开发，非Prompt工程师", "pos_02"),
    75: ("ACCEPT", 0.9, "Core ML研究归算法岗", None),
    76: ("MODIFY", 0.8, "AI产品服务端开发应归应用开发，非部署", "pos_02"),
    77: ("ACCEPT", 0.7, "信息安全方案经理归数据安全域，族校验正确", None),
    78: ("ACCEPT", 0.9, "算法实习归pos_01", None),
    79: ("ACCEPT", 0.9, "Visual AI机器学习工程师归视觉族，正确", None),
    80: ("ACCEPT", 0.85, "算法实习归pos_01", None),
    81: ("MODIFY", 0.65, "Applied AI架构师偏应用侧", "pos_02"),
    82: ("ACCEPT", 0.85, "算法实习归pos_01", None),
    83: ("ACCEPT", 0.65, "AI教育负责人归教育产品域边界接受", None),
    84: ("REJECT", 0.8, "应用AI架构经理（商业方向）是管理岗，应unmatched", None),
    85: ("ACCEPT", 0.6, "AI/ML解决方案工程师归MLOps边界接受", None),
    86: ("REJECT", 0.85, "技术方案经理是管理岗，应unmatched", None),
    87: ("REJECT", 0.85, "战略商业化设计非产品经理，应unmatched", None),
    88: ("ACCEPT", 0.9, "AI运行时工程师归基础设施", None),
    89: ("ACCEPT", 0.9, "AI增长产品经理归pos_06对口", None),
    # unmatched 10 条
    90: ("ACCEPT", 0.9, "FDE实习被排除，正确", None),
    91: ("ACCEPT", 0.95, "合规负责人不属目录，未映射正确", None),
    92: ("ACCEPT", 0.95, "前端开发实习不属目录，未映射正确", None),
    93: ("ACCEPT", 0.95, "渠道运营经理不属目录，未映射正确", None),
    94: ("ACCEPT", 0.9, "医学研究员不属目录，未映射正确", None),
    95: ("REJECT", 0.7, "Frontier红队研究工程师涉AI安全，排除规则误伤漏判", None),
    96: ("ACCEPT", 0.95, "收入工程经理不属目录，未映射正确", None),
    97: ("REJECT", 0.75, "推理/计算工程师应映射pos_05或pos_13，无AI词被误排", None),
    98: ("REJECT", 0.75, "Frontier Agents工程师含Agent信号，BIZ过滤误伤漏判", None),
    99: ("ACCEPT", 0.7, "高性能计算（视频）无对口目录岗，未映射正确", None),
}

# domain：同意系统判定
DOMAIN: dict[int, tuple[str, float, str]] = {
    **{i: ("ACCEPT", 0.9, "AI岗位判定正确") for i in range(35)},
    5: ("ACCEPT", 0.55, "数据统计员是否AI相关取决于公司业务语境，弱接受"),
    13: ("ACCEPT", 0.55, "算法业务推动岗为业务侧，弱接受"),
    15: ("REJECT", 0.85, "项目资料员是行政岗，判定理由牵强，应为非AI"),
    19: ("ACCEPT", 0.6, "农业保险博士后涉遥感+AI研究，边界接受"),
    32: ("REJECT", 0.85, "纯Java开发岗标题无AI语境，应为非AI"),
    **{i: ("ACCEPT", 0.95, "非AI岗位判定正确") for i in range(35, 50)},
}

# event：事件类型与技能提及核对
EVENT: dict[int, tuple[str, float, str]] = {
    **{i: ("ACCEPT", 0.9, "事件类型与技能提及正确") for i in range(30)},
    3: ("ACCEPT", 0.65, "平台上线模型服务在productization与adoption边界，可接受"),
    5: ("ACCEPT", 0.6, "rumor类型正确，技能提及需正文佐证，弱接受"),
    13: ("ACCEPT", 0.6, "类型正确但技能提及缺失视频生成，弱接受"),
    23: ("ACCEPT", 0.55, "技能提及仅“AI”过泛，弱接受"),
}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if mode == "apply":
        # 批量采纳预标注为正式标注（基线摸底用；reviewer_id 透明标记）
        from backend.application.annotate import submit_annotation

        prelabels = (
            json.loads("[]")
            if not OUT.is_file()
            else [json.loads(x) for x in OUT.read_text(encoding="utf-8").splitlines() if x.strip()]
        )
        for rec in prelabels:
            submit_annotation(
                rec["task_id"],
                rec["suggested_decision"],
                rationale=f"[AI预标注批量采纳] {rec['rationale']}",
                reviewer_id="ai-prelabel-batch",
                corrected_payload=rec.get("corrected_payload"),
            )
        print(f"已批量采纳 {len(prelabels)} 条预标注（reviewer_id=ai-prelabel-batch）")
        return 0

    rows: list[dict] = []
    ts = datetime.now(UTC).isoformat()
    for i, (decision, conf, rationale, fix) in ROLE.items():
        rows.append(
            {
                "task_id": f"task-role_level-{i:03d}",
                "suggested_decision": decision,
                "confidence": conf,
                "rationale": rationale,
                "corrected_payload": {"position_id": fix} if fix else None,
                "prelabel_by": PRELABEL_BY,
                "created_at": ts,
            }
        )
    for i, (decision, conf, rationale) in DOMAIN.items():
        rows.append(
            {
                "task_id": f"task-evidence_audit-{i:03d}",
                "suggested_decision": decision,
                "confidence": conf,
                "rationale": rationale,
                "corrected_payload": None,
                "prelabel_by": PRELABEL_BY,
                "created_at": ts,
            }
        )
    for i, (decision, conf, rationale) in EVENT.items():
        rows.append(
            {
                "task_id": f"task-skill_mapping-{i:03d}",
                "suggested_decision": decision,
                "confidence": conf,
                "rationale": rationale,
                "corrected_payload": None,
                "prelabel_by": PRELABEL_BY,
                "created_at": ts,
            }
        )
    rows.sort(key=lambda r: r["task_id"])
    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    from collections import Counter

    dist = Counter(r["suggested_decision"] for r in rows)
    print(f"预标注 {len(rows)} 条 -> {OUT}")
    print(f"分布: {dict(dist)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

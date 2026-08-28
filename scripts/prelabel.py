"""prelabel: 评测样本 AI 预标注——生成建议判定，供人工确认后回流。

用法：
    uv run scripts/prelabel.py

原则（与产品哲学一致）：AI 只产候选，不直接成为标注事实。
本脚本输出 evaluation/prelabels.jsonl（建议判定 + 置信度 + 理由），
不计入 evalset.py score；人工在 /tasks 页确认或修改后才写入
annotations.jsonl 并计入指标。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "prelabels.jsonl"
PRELABEL_BY = "claude-prelabel-20260828"

# task 序号 -> (decision, confidence, rationale, corrected_position_id|None)
# 判定口径：ACCEPT=系统输出正确；MODIFY=方向错但有可修正映射；REJECT=不应映射/漏判
ROLE: dict[int, tuple[str, float, str, str | None]] = {
    # exact 15 条：名称精确匹配全部正确
    **{i: ("ACCEPT", 0.98, "名称精确匹配，岗位语义一致", None) for i in range(15)},
    # alias 25 条
    15: ("ACCEPT", 0.95, "Agent应用开发即AI Agent开发工程师", None),
    16: ("MODIFY", 0.7, "机器学习工程师更贴近大模型算法岗，非NLP/多模态研究员", "pos_01"),
    17: ("ACCEPT", 0.9, "具身智能产品经理属AI产品经理细分", None),
    18: ("ACCEPT", 0.98, "Agent&RAG开发即pos_02", None),
    19: ("ACCEPT", 0.98, "AI Agent工程师精确对应", None),
    20: ("ACCEPT", 0.97, "计算机视觉算法工程师即pos_27", None),
    21: ("ACCEPT", 0.85, "大模型应用与优化属算法岗", None),
    22: ("ACCEPT", 0.95, "AI大模型研发即pos_01", None),
    23: ("ACCEPT", 0.95, "Agent开发实习即pos_02", None),
    24: ("ACCEPT", 0.93, "智能体开发工程师即pos_02", None),
    25: ("ACCEPT", 0.95, "AI大模型工程师即pos_01", None),
    26: ("ACCEPT", 0.95, "Agent/RAG工程师即pos_02", None),
    27: ("ACCEPT", 0.8, "大模型Prompt算法主体为算法岗，pos_03亦合理", None),
    28: ("ACCEPT", 0.95, "AI智能体开发即pos_02", None),
    29: ("MODIFY", 0.7, "多头衔混合岗主体为机器学习/算法，应归算法岗", "pos_01"),
    30: ("ACCEPT", 0.95, "大模型工程师即pos_01", None),
    31: ("MODIFY", 0.75, "感知算法+L4明确指向自动驾驶感知，非NLP研究", "pos_39"),
    32: ("ACCEPT", 0.9, "数据开发工程师即大数据工程师", None),
    33: ("ACCEPT", 0.95, "Python智能体开发即pos_02", None),
    34: ("MODIFY", 0.65, "机器学习+物理仿真无完美匹配，算法岗最接近", "pos_01"),
    35: ("MODIFY", 0.8, "LLM/RAG/MCP应用工程岗应归Agent应用开发", "pos_02"),
    36: ("ACCEPT", 0.95, "多模态大模型工程师即pos_01", None),
    37: ("ACCEPT", 0.85, "大模型评测属算法岗工作范畴", None),
    38: ("ACCEPT", 0.95, "大模型工程师即pos_01", None),
    39: ("REJECT", 0.9, "软件测试工程师(机器学习平台)非研究员，目录无测试岗，应unmatched", None),
    # llm 50 条：重点核查区
    40: ("ACCEPT", 0.9, "应用AI工程师即Agent应用开发", None),
    41: ("MODIFY", 0.85, "AI应用工程师无CV语境，应归pos_02", "pos_02"),
    42: ("ACCEPT", 0.8, "AI技术研发工程师归算法岗可接受", None),
    43: ("ACCEPT", 0.9, "AI应用部署工程师即MLOps部署岗", None),
    44: ("ACCEPT", 0.95, "智慧交通算法即pos_44", None),
    45: ("ACCEPT", 0.7, "泛算法工程师在AI目录下归pos_01可接受", None),
    46: ("REJECT", 0.85, "技术支持工程师与云基础设施语义不符，应unmatched", None),
    47: ("ACCEPT", 0.9, "AI应用工程师实习即pos_02", None),
    48: ("MODIFY", 0.7, "数智化AI应用实施偏企业应用，非智能制造", "pos_02"),
    49: ("ACCEPT", 0.95, "高级AI算法工程师即pos_01", None),
    50: ("MODIFY", 0.85, "AI算法工程师无CV语境，应归pos_01", "pos_01"),
    51: ("MODIFY", 0.75, "泛ai工程师无部署语境，归算法岗", "pos_01"),
    52: ("MODIFY", 0.7, "AI应用官为高管岗，更接近CAIO", "pos_21"),
    53: ("ACCEPT", 0.9, "AI应用开发工程师即pos_02", None),
    54: ("MODIFY", 0.7, "AI直播应用工程偏应用开发，非部署", "pos_02"),
    55: ("ACCEPT", 0.6, "AI安全研发归AI合规/治理范畴，边界可接受", None),
    56: ("ACCEPT", 0.6, "物理算法+机器人方向与数字孪生仿真部分重合，边界", None),
    57: ("ACCEPT", 0.8, "网络安全归数据安全工程师可接受", None),
    58: ("REJECT", 0.9, "全栈后端工程师非大数据岗，应unmatched", None),
    59: ("MODIFY", 0.85, "AI应用开发工程师应归pos_02", "pos_02"),
    60: ("REJECT", 0.9, "应用开发实习生无AI语境，应unmatched", None),
    61: ("MODIFY", 0.9, "AI工程师校招与AI审计师语义无关", "pos_01"),
    62: ("ACCEPT", 0.85, "人工智能工程师归算法主体岗可接受", None),
    63: ("ACCEPT", 0.9, "AI应用工程师即pos_02", None),
    64: ("ACCEPT", 0.8, "AI应用顾问属应用侧岗位", None),
    65: ("MODIFY", 0.7, "网安AI工程师偏技术安全，数据安全更接近", "pos_36"),
    66: ("MODIFY", 0.8, "知识库方向应用工程师应归Agent/RAG应用开发", "pos_02"),
    67: ("REJECT", 0.8, "泛IT岗位无数据中心运维证据，应unmatched", None),
    68: ("ACCEPT", 0.9, "ai应用工程师即pos_02", None),
    69: ("ACCEPT", 0.8, "软件开发(AI模型方向)归算法岗可接受", None),
    70: ("ACCEPT", 0.9, "算法工程师(人工智能)即pos_01", None),
    71: ("ACCEPT", 0.9, "AI应用工程师即pos_02", None),
    72: ("ACCEPT", 0.75, "IT开发/运维归数据中心运维可接受", None),
    73: ("REJECT", 0.9, "软件研发工程师无知识图谱语境，应unmatched", None),
    74: ("ACCEPT", 0.8, "ai工程师归算法岗可接受", None),
    75: ("ACCEPT", 0.8, "AI工程师归算法岗可接受", None),
    76: ("ACCEPT", 0.9, "谱图识别属视觉识别，归pos_27", None),
    77: ("MODIFY", 0.6, "RAG工程师偏应用开发则pos_02，偏算法则pos_01，真边界case", "pos_02"),
    78: ("ACCEPT", 0.95, "高级AI算法工程师即pos_01", None),
    79: ("ACCEPT", 0.85, "AI工程师实习归算法岗可接受", None),
    80: ("ACCEPT", 0.9, "机器人服务工程师即机器人运维", None),
    81: ("REJECT", 0.8, "编程讲师非教育产品设计岗，目录无讲师岗，应unmatched", None),
    82: ("ACCEPT", 0.95, "AI agent工程师即pos_02", None),
    83: ("ACCEPT", 0.9, "智能嗅觉=气味传感器，归智能传感器工程师准确", None),
    84: ("ACCEPT", 0.95, "图像算法工程师即计算机视觉", None),
    85: ("ACCEPT", 0.85, "AI Native应用开发即pos_02", None),
    86: ("ACCEPT", 0.8, "信息安全归数据安全工程师可接受", None),
    87: ("ACCEPT", 0.65, "数据统计员归数据专员边界可接受", None),
    88: ("REJECT", 0.85, "信息化管理(AI)偏IT管理，非产品经理，应unmatched", None),
    89: ("ACCEPT", 0.9, "AI产品助理即AI产品经理序列", None),
    # unmatched 10 条：判定未映射是否正确
    90: ("ACCEPT", 0.98, "结构工程师不属46岗位，未映射正确", None),
    91: ("ACCEPT", 0.98, "青苗计划为培养计划非岗位，未映射正确", None),
    92: ("ACCEPT", 0.98, "生产技术员不属目录，未映射正确", None),
    93: ("ACCEPT", 0.95, "产品测试工程师目录无对应岗，未映射正确", None),
    94: ("ACCEPT", 0.95, "纯Java开发不属AI岗位目录，未映射正确", None),
    95: ("REJECT", 0.85, "算法工程师应映射pos_01，系统漏判", None),
    96: ("REJECT", 0.8, "AI技术管培生含明确AI语境，应映射，系统漏判", None),
    97: ("ACCEPT", 0.9, "信息岗过于泛化，无法映射正确", None),
    98: ("ACCEPT", 0.9, "技术支持过于泛化，无法映射正确", None),
    99: ("ACCEPT", 0.98, "专利代理师不属目录，未映射正确", None),
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

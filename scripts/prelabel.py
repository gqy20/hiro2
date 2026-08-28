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
PRELABEL_BY = "claude-prelabel-20260828"

# task 序号 -> (decision, confidence, rationale, corrected_position_id|None)
# v2 判定（eval-v2-20260828 冻结样本）
# 口径：ACCEPT=系统输出正确；MODIFY=方向错但有可修正映射；REJECT=不应映射/漏判
ROLE: dict[int, tuple[str, float, str, str | None]] = {
    # exact 15 条：名称精确匹配全部正确
    **{i: ("ACCEPT", 0.98, "名称精确匹配，岗位语义一致", None) for i in range(15)},
    # alias 25 条
    15: (
        "REJECT",
        0.85,
        "大模型平台运营（市场品牌）是运营岗非算法岗，“大模型”别名误中，应unmatched",
        None,
    ),
    16: ("ACCEPT", 0.97, "大语言模型算法研究即pos_01", None),
    17: ("ACCEPT", 0.85, "风控算法工程师归算法主体岗可接受", None),
    18: ("ACCEPT", 0.95, "ML Engineer, LLM即pos_01", None),
    19: ("ACCEPT", 0.9, "数据挖掘算法归算法岗可接受", None),
    20: ("ACCEPT", 0.65, "图像算法+多模态大模型研发，pos_01与pos_27边界，可接受", None),
    21: ("ACCEPT", 0.95, "大数据开发即pos_11", None),
    22: ("ACCEPT", 0.9, "机器学习平台研发归算法岗可接受", None),
    23: ("MODIFY", 0.85, "产品实习生是产品岗非算法岗，“大模型”别名误中，应归AI产品经理", "pos_06"),
    24: ("ACCEPT", 0.95, "AI应用工程师即pos_02（v2新别名生效）", None),
    25: ("ACCEPT", 0.95, "智能体开发即pos_02", None),
    26: ("ACCEPT", 0.9, "大模型评测算法研究归pos_01", None),
    27: ("ACCEPT", 0.97, "大模型预训练算法即pos_01", None),
    28: ("ACCEPT", 0.95, "NLP算法即pos_04", None),
    29: ("ACCEPT", 0.65, "视觉多模态算法，pos_01与pos_27边界，可接受", None),
    30: ("ACCEPT", 0.95, "推荐算法工程师即算法岗", None),
    31: ("ACCEPT", 0.9, "内容安全算法+大模型方向归算法岗", None),
    32: ("ACCEPT", 0.95, "多模态大模型算法即pos_01", None),
    33: ("ACCEPT", 0.7, "Agent自进化算法归pos_02与pos_01边界，可接受", None),
    34: ("ACCEPT", 0.6, "SLAM算法（XR场景）目录无对口岗，算法岗边界接受", None),
    35: ("ACCEPT", 0.95, "大数据开发即pos_11", None),
    36: ("ACCEPT", 0.95, "AIOS产品经理即pos_06", None),
    37: ("ACCEPT", 0.9, "初级算法工程师即pos_01", None),
    38: ("ACCEPT", 0.9, "多模态算法（搜索）归算法岗", None),
    39: ("ACCEPT", 0.85, "视频算法工程师归算法岗可接受", None),
    # llm 50 条
    40: ("ACCEPT", 0.6, "网络工程归基础设施域边界接受", None),
    41: ("REJECT", 0.9, "Engagement Manager是咨询项目管理，非AI产品经理，应unmatched", None),
    42: ("ACCEPT", 0.9, "数据工程（AI方向）即pos_11", None),
    43: ("ACCEPT", 0.6, "核心基础设施TPM归基础设施域边界接受", None),
    44: ("ACCEPT", 0.95, "数据仓库开发即pos_11", None),
    45: ("ACCEPT", 0.6, "数据库内核工程归大数据域边界接受", None),
    46: ("REJECT", 0.9, "产品营销经理（Figma编辑器）非AI产品经理，应unmatched", None),
    47: ("REJECT", 0.95, "销售岗（Account Executive）与产品经理无关，应unmatched", None),
    48: ("ACCEPT", 0.95, "机器视觉工程师族校验修正为pos_27，正确", None),
    49: ("ACCEPT", 0.6, "数据库引擎内核归大数据域边界接受", None),
    50: ("MODIFY", 0.85, "机器人运动控制非强化学习，更接近机器人运维", "pos_22"),
    51: ("ACCEPT", 0.8, "SRE归基础设施域可接受", None),
    52: ("ACCEPT", 0.9, "数据分析实习即pos_35", None),
    53: ("ACCEPT", 0.9, "Data Engineer即pos_11", None),
    54: ("REJECT", 0.9, "纯后端工程师与大数据无关，应unmatched", None),
    55: ("REJECT", 0.8, "人审平台产品专家无AI语境，应unmatched", None),
    56: ("ACCEPT", 0.85, "基础设施软件工程师即pos_13", None),
    57: ("REJECT", 0.9, "GTM系统工程师是销售系统岗，非Agent开发，应unmatched", None),
    58: ("ACCEPT", 0.85, "AI全栈工程师归应用开发岗可接受", None),
    59: ("REJECT", 0.9, "后端开发实习（内容发现）与大数据无关，应unmatched", None),
    60: ("ACCEPT", 0.9, "专有云产品研发即云计算基础设施岗", None),
    61: ("ACCEPT", 0.75, "数据科学家（战略财务）归数据分析边界接受", None),
    62: ("MODIFY", 0.8, "视频感知与理解是计算机视觉域，族关键词漏“视频”", "pos_27"),
    63: ("REJECT", 0.85, "安全TPM是项目管理岗非AI合规，应unmatched", None),
    64: ("ACCEPT", 0.85, "算法实习生归pos_01", None),
    65: ("ACCEPT", 0.6, "数据库后端实习归大数据域边界接受", None),
    66: ("ACCEPT", 0.8, "游戏图形算法归算法岗可接受（非计算机视觉）", None),
    67: ("ACCEPT", 0.95, "AI agent工程师即pos_02", None),
    68: ("ACCEPT", 0.6, "基带硬件工程师归嵌入式边界接受", None),
    69: ("ACCEPT", 0.75, "洞察分析师归数据分析可接受", None),
    70: ("ACCEPT", 0.9, "数据工程实习即pos_11", None),
    71: ("ACCEPT", 0.85, "算法实习生归pos_01", None),
    72: ("ACCEPT", 0.85, "算法实习生（质量技术）归pos_01", None),
    73: ("MODIFY", 0.8, "Responsible AI研究即算法公平性/AI伦理方向", "pos_40"),
    74: ("ACCEPT", 0.6, "搜索质量工程涉排序算法，归算法岗边界接受", None),
    75: ("ACCEPT", 0.6, "广告平台基础架构后端归基础设施域边界接受", None),
    76: ("ACCEPT", 0.9, "基础设施与稳定性工程即pos_13", None),
    77: ("ACCEPT", 0.85, "ML应用研究归算法岗", None),
    78: ("REJECT", 0.9, "FDE（客户现场工程）与大数据无关，应unmatched", None),
    79: ("ACCEPT", 0.75, "AI原生数据库系统归数据基础设施边界接受", None),
    80: ("ACCEPT", 0.65, "ML系统研究归MLOps边界接受", None),
    81: ("ACCEPT", 0.75, "数据统计员归数据专员可接受", None),
    82: ("ACCEPT", 0.6, "算力平台产品经理为技术平台PM，边界接受", None),
    83: ("ACCEPT", 0.9, "经营分析归数据分析", None),
    84: ("REJECT", 0.8, "解决方案架构师（售前）与基础设施工程不同，应unmatched", None),
    85: ("ACCEPT", 0.8, "数据科学家（开发者效能）归数据分析可接受", None),
    86: ("ACCEPT", 0.9, "网络安全AI知识专家族校验修正为pos_36，正确", None),
    87: ("ACCEPT", 0.55, "风控策略运营归数据分析弱接受", None),
    88: ("ACCEPT", 0.95, "AI模型部署专家即pos_05", None),
    89: ("ACCEPT", 0.85, "算法实习生归pos_01", None),
    # unmatched 10 条
    90: ("ACCEPT", 0.95, "供应链安全经理不属目录，未映射正确", None),
    91: ("ACCEPT", 0.9, "战略财务（GenAI语境）为财务岗，未映射正确", None),
    92: ("REJECT", 0.85, "AI全栈工程师应映射pos_02，系统漏判（与同池058不一致）", None),
    93: ("ACCEPT", 0.95, "前端开发实习不属目录，未映射正确", None),
    94: ("ACCEPT", 0.95, "企业销售不属目录，未映射正确", None),
    95: ("ACCEPT", 0.95, "渠道拓展经理不属目录，未映射正确", None),
    96: ("ACCEPT", 0.95, "收入策略运营不属目录，未映射正确", None),
    97: ("ACCEPT", 0.95, "生态合作运营不属目录，未映射正确", None),
    98: ("ACCEPT", 0.95, "前端工程实习不属目录，未映射正确", None),
    99: ("ACCEPT", 0.9, "开发者关系岗不属目录，未映射正确", None),
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

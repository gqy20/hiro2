"""Training Use Case：岗位标准下游输出——JD 模板 / 培养任务 / 能力证明（F-T3.6）。"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from .repos import P


class _VM(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JDSkillItem(_VM):
    name: str
    weight: float
    is_required: bool


class JDTemplateVM(_VM):
    job_title: str
    version: str
    responsibilities: list[str]
    required_skills: list[JDSkillItem]
    preferred_skills: list[JDSkillItem]
    scenarios: list[str]


class TrainingTaskVM(_VM):
    task_id: str
    name: str
    skill_id: str
    skill_name: str
    level: str  # L1/L2/L3
    learn: str
    practice: str
    evaluate: str
    certify: str


class CertRequirementVM(_VM):
    skill_id: str
    skill_name: str
    evidence_types: list[str]
    min_quality: float


class TrainingOutputVM(_VM):
    job_version_id: str
    job_title: str
    jd_template: JDTemplateVM
    training_tasks: list[TrainingTaskVM]
    cert_requirements: list[CertRequirementVM]
    generated_by: str = "training-v1"


def build_training_output(job_version_id: str = "ai-agent-v2") -> TrainingOutputVM:
    """从 PUBLISHED 版本生成四类下游输出（确定性组装，无 LLM）。"""
    job: dict = {}
    p = P / "jobversions" / "published" / f"{job_version_id}.json"
    if p.is_file():
        job = json.loads(p.read_text(encoding="utf-8"))

    # Excel 职责画像作为 JD 模板的职责来源
    pos_skills: dict = {}
    ps_path = P / "capability-matrix" / "position-skills.jsonl"
    if ps_path.is_file():
        for line in ps_path.open(encoding="utf-8"):
            r = json.loads(line)
            pos_skills[r["position_id"]] = r

    # 找到该岗位对应的 Excel 职责
    resp_from_excel: list[str] = []
    for pid, ps in pos_skills.items():
        if "agent" in pid.lower() or "Agent" in ps.get("name", ""):
            resp_from_excel = [x for x in ps.get("responsibilities", [])[:6]]
            break

    # 始终加载 emerging（scenarios 需要它）
    emerging: dict = {}
    em_path = P / "jd-opencli" / "emerging-agent.json"
    if em_path.is_file():
        emerging = json.loads(em_path.read_text(encoding="utf-8"))
    if not resp_from_excel:
        card = emerging.get("evidence", {}).get("definition_card", {})
        resp_from_excel = [x["phrase"] for x in card.get("core_responsibilities", [])]

    req = [
        JDSkillItem(name=s["name"], weight=s.get("weight", 0), is_required=True)
        for s in job.get("required_skill_ids", [])
    ]
    pref = [
        JDSkillItem(name=s["name"], weight=s.get("weight", 0), is_required=False)
        for s in job.get("preferred_skill_ids", [])
    ]

    jd_tmpl = JDTemplateVM(
        job_title=job.get("title", job_version_id),
        version=job_version_id,
        responsibilities=resp_from_excel,
        required_skills=req,
        preferred_skills=pref,
        scenarios=[
            x.get("name", "")
            for x in emerging.get("evidence", {})
            .get("definition_card", {})
            .get("typical_industries", [])
        ],
    )

    # 培养任务：必备域各一条 L2 级 + 加分域 L1
    tasks: list[TrainingTaskVM] = []
    for i, s in enumerate(req):
        tasks.append(
            TrainingTaskVM(
                task_id=f"train-{s.name}-L2",
                name=f"{s.name} 实战训练",
                skill_id=s.name,
                skill_name=s.name,
                level="L2",
                learn=f"系统学习 {s.name} 核心概念、主流工具与方法论",
                practice=f"完成一个包含 {s.name} 的端到端项目并沉淀文档",
                evaluate=f"在项目中独立完成 {s.name} 相关模块并通过复盘",
                certify=f"整理项目证据 + 技能自评形成 {s.name} 能力证明",
            )
        )
    for s in pref[:3]:
        tasks.append(
            TrainingTaskVM(
                task_id=f"train-{s.name}-L1",
                name=f"{s.name} 入门了解",
                skill_id=s.name,
                skill_name=s.name,
                level="L1",
                learn=f"了解 {s.name} 的基本概念与应用场景",
                practice=f"尝试一个 {s.name} 小实验或 demo",
                evaluate=f"能解释 {s.name} 的核心原理与适用边界",
                certify=f"整理学习笔记形成 {s.name} 初步认知证明",
            )
        )

    # 能力证明要求
    certs = [
        CertRequirementVM(
            skill_id=s.name,
            skill_name=s.name,
            evidence_types=["项目代码/文档", "复盘报告", "技能自评"],
            min_quality=0.8,
        )
        for s in req[:5]
    ]

    return TrainingOutputVM(
        job_version_id=job_version_id,
        job_title=job.get("title", ""),
        jd_template=jd_tmpl,
        training_tasks=tasks,
        cert_requirements=certs,
    )

"""求职成长工作区的个人事实写入。PostgreSQL 未配置时显式拒绝持久化。"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from ..candidates.models import CandidateProfile
from ..matching.engine import match


def _connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("个人成长数据需要配置 PostgreSQL 后才能保存。")
    import psycopg

    return psycopg.connect(dsn)


def save_growth_task(
    candidate_id: str, job_version_id: str, skill_id: str, completed: bool
) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO growth_tasks (candidate_id, job_version_id, skill_id, status, completed_at)
            VALUES (%s, %s, %s, %s, CASE WHEN %s THEN now() ELSE NULL END)
            ON CONFLICT (candidate_id, job_version_id, skill_id) DO UPDATE
            SET status = EXCLUDED.status, completed_at = EXCLUDED.completed_at
            RETURNING task_id, status, completed_at
            """,
            (
                candidate_id,
                job_version_id,
                skill_id,
                "COMPLETED" if completed else "PENDING",
                completed,
            ),
        )
        task_id, status, completed_at = cur.fetchone()
    return {
        "taskId": task_id,
        "status": status,
        "completedAt": completed_at.isoformat() if completed_at else None,
    }


def add_proof(
    candidate_id: str,
    skill_id: str,
    title: str,
    description: str,
    proof_url: str | None,
) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO candidate_proofs (candidate_id, skill_id, title, description, proof_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING proof_id, created_at
            """,
            (candidate_id, skill_id, title, description, proof_url),
        )
        proof_id, created_at = cur.fetchone()
    return {"proofId": proof_id, "createdAt": created_at.isoformat()}


def load_career_state(candidate_id: str, job_version_id: str) -> dict:
    """读取个人成长事实；未配置数据库时返回空状态以保持离线诊断可用。"""
    if not os.getenv("DATABASE_URL"):
        return {"completedSkills": [], "proofs": []}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT skill_id FROM growth_tasks
               WHERE candidate_id = %s AND job_version_id = %s AND status = 'COMPLETED'""",
            (candidate_id, job_version_id),
        )
        completed = [row[0] for row in cur.fetchall()]
        cur.execute(
            """SELECT proof_id, skill_id, title, description, proof_url, created_at
               FROM candidate_proofs WHERE candidate_id = %s ORDER BY created_at DESC""",
            (candidate_id,),
        )
        proofs = [
            {
                "id": row[0],
                "skill": row[1],
                "title": row[2],
                "description": row[3],
                "url": row[4],
                "createdAt": row[5].isoformat(),
            }
            for row in cur.fetchall()
        ]
    return {"completedSkills": completed, "proofs": proofs}


def set_active_target(candidate_id: str, job_version_id: str) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE candidate_targets SET is_active = FALSE WHERE candidate_id = %s",
            (candidate_id,),
        )
        cur.execute(
            """
            INSERT INTO candidate_targets (candidate_id, job_version_id, is_active)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (candidate_id, job_version_id) DO UPDATE
            SET is_active = TRUE, selected_at = now()
            """,
            (candidate_id, job_version_id),
        )
    return {"candidateId": candidate_id, "jobVersionId": job_version_id, "isActive": True}


def save_profile(candidate_id: str, updates: list[dict], projects: list[str]) -> dict:
    """追加画像快照，并保存一份不可覆盖的确定性匹配报告。"""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT effective_profile, correction_log FROM candidates WHERE candidate_id = %s",
            (candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError("候选人不存在")
        profile = CandidateProfile.model_validate(row[0])
        corrections = list(row[1] or [])
        update_by_name = {item["name"]: item["status"] for item in updates}
        for skill in profile.skills:
            status = update_by_name.get(skill.mention)
            if not status:
                continue
            before = skill.proficiency
            if status == "missing":
                skill.skill_id = None
                skill.point_id = None
            elif status == "partial":
                skill.proficiency = "初级"
            else:
                skill.proficiency = "中级" if skill.proficiency == "初级" else skill.proficiency
            corrections.append(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "field": "skill_status",
                    "target": skill.mention,
                    "before": before,
                    "after": status,
                }
            )
        if projects:
            profile.projects = [item for item in profile.projects if item.name in projects]
        profile.correction_log = corrections
        snapshot = profile.model_dump(mode="json")
        cur.execute(
            """UPDATE candidates SET effective_profile = %s, correction_log = %s
               WHERE candidate_id = %s""",
            (json.dumps(snapshot), json.dumps(corrections), candidate_id),
        )
        cur.execute(
            """INSERT INTO candidate_profile_versions
               (candidate_id, effective_profile, correction_log) VALUES (%s, %s, %s)""",
            (candidate_id, json.dumps(snapshot), json.dumps(corrections)),
        )
        cur.execute(
            "SELECT job_version_id FROM candidate_targets WHERE candidate_id = %s AND is_active",
            (candidate_id,),
        )
        target = cur.fetchone()
        job_version_id = target[0] if target else "ai-agent-v2"
        report = match(profile, job_version_id)
        report_id = f"{report.match_id}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        cur.execute(
            """
            INSERT INTO match_reports (match_id, candidate_id, job_version_id, algorithm_version,
                overall_score, dimensions, gaps, evidence_ids, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                report_id,
                candidate_id,
                job_version_id,
                report.algorithm_version,
                report.overall_score,
                json.dumps(report.dimensions),
                json.dumps([gap.model_dump() for gap in report.gaps]),
                report.evidence_ids,
                report.status,
            ),
        )
    return {"profileVersion": "saved", "matchId": report_id, "overallScore": report.overall_score}

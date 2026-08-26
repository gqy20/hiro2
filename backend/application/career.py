"""求职成长工作区的个人事实写入。PostgreSQL 未配置时显式拒绝持久化。"""

from __future__ import annotations

import os


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

-- 求职成长工作区：个人目标、行动状态和能力证明均为追加事实。

CREATE TABLE IF NOT EXISTS candidate_targets (
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    job_version_id TEXT NOT NULL REFERENCES job_versions(version_id),
    selected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (candidate_id, job_version_id)
);

CREATE TABLE IF NOT EXISTS growth_tasks (
    task_id BIGSERIAL PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    job_version_id TEXT NOT NULL REFERENCES job_versions(version_id),
    skill_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'COMPLETED')),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, job_version_id, skill_id)
);

CREATE TABLE IF NOT EXISTS candidate_proofs (
    proof_id BIGSERIAL PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    skill_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    proof_url TEXT,
    completed_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_proofs_candidate ON candidate_proofs(candidate_id, skill_id);

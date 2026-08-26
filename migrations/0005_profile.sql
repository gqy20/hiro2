-- 个人目标和画像版本：当前目标唯一，画像与匹配报告均追加保留历史。

ALTER TABLE candidate_targets
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_target_active
    ON candidate_targets(candidate_id) WHERE is_active;

CREATE TABLE IF NOT EXISTS candidate_profile_versions (
    profile_version_id BIGSERIAL PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    effective_profile JSONB NOT NULL,
    correction_log JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_profile_versions_candidate
    ON candidate_profile_versions(candidate_id, created_at DESC);

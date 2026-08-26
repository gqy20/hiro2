-- 审核质量指标所需的结构化字段；只追加，不重写 0001。
ALTER TABLE review_tasks
    ADD COLUMN IF NOT EXISTS needs_dual_review BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE review_actions
    ADD COLUMN IF NOT EXISTS error_type TEXT;

CREATE INDEX IF NOT EXISTS idx_review_actions_error ON review_actions(error_type);

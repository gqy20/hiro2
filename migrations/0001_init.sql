-- Hiro2 核心表结构（Phase B，ADR 0002/0006）
-- PostgreSQL 17；schema 只经 migrations/ 修改，已应用的不可重写。

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================ 来源

CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    source_type     TEXT NOT NULL,
    license         TEXT NOT NULL DEFAULT '',
    time_range      TEXT[],
    ingestion_mode  TEXT NOT NULL DEFAULT 'backfill',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================ 证据（D7）

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id     TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES sources,
    claim_type      TEXT NOT NULL CHECK (claim_type IN ('trend_signal','job_requirement','expert_baseline')),
    published_at    DATE,
    collected_at    TIMESTAMPTZ DEFAULT now(),
    content_hash    TEXT NOT NULL,
    quality_score   REAL NOT NULL DEFAULT 0.5 CHECK (quality_score >= 0 AND quality_score <= 1),
    payload         JSONB NOT NULL DEFAULT '{}',
    urls            TEXT[] DEFAULT '{}',
    source_span     JSONB NOT NULL DEFAULT '{}',
    review_status   TEXT NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING','ACCEPTED','MODIFIED','REJECTED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_type);
CREATE INDEX IF NOT EXISTS idx_evidence_published ON evidence(published_at);

-- ============================================================ 技能

CREATE TABLE IF NOT EXISTS capabilities (
    capability_id   TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id        TEXT PRIMARY KEY,  -- cap_XX 或 cap_XX.点级
    capability_id   TEXT NOT NULL REFERENCES capabilities,
    point_name      TEXT,
    aliases         TEXT[] NOT NULL DEFAULT '{}',
    rule_version    INT NOT NULL DEFAULT 1,
    effective_from  DATE,             -- 习得别名的时间闸门
    is_earned       BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_skills_capability ON skills(capability_id);

-- ============================================================ 岗位版本

CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    group_name      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS job_versions (
    version_id      TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES jobs,
    status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','REVIEWING','PUBLISHED','ARCHIVED')),
    title           TEXT NOT NULL,
    required_skills JSONB NOT NULL DEFAULT '[]',
    preferred_skills JSONB NOT NULL DEFAULT '[]',
    changeset       JSONB NOT NULL DEFAULT '[]',
    evidence_ids    TEXT[] NOT NULL DEFAULT '{}',
    review_action_ids TEXT[] NOT NULL DEFAULT '{}',
    version_hash    TEXT,
    valid_from      DATE,
    valid_until     DATE,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jv_job ON job_versions(job_id);
CREATE INDEX IF NOT EXISTS idx_jv_status ON job_versions(status);

-- ============================================================ 候选人与匹配

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id    TEXT PRIMARY KEY,
    raw_extraction  JSONB NOT NULL DEFAULT '{}',
    effective_profile JSONB NOT NULL DEFAULT '{}',
    correction_log  JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS match_reports (
    match_id        TEXT PRIMARY KEY,
    candidate_id    TEXT NOT NULL REFERENCES candidates,
    job_version_id  TEXT NOT NULL REFERENCES job_versions(version_id),
    algorithm_version TEXT NOT NULL,
    overall_score   REAL NOT NULL,
    dimensions      JSONB NOT NULL DEFAULT '[]',
    gaps            JSONB NOT NULL DEFAULT '[]',
    evidence_ids    TEXT[] NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'FINAL',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================ 审核

CREATE TABLE IF NOT EXISTS review_tasks (
    task_id         TEXT PRIMARY KEY,
    task_type       TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    run_id          TEXT,
    dataset_version TEXT,
    priority        TEXT NOT NULL DEFAULT 'medium',
    assignee_id     TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','CLAIMED','IN_REVIEW','SUBMITTED','ADJUDICATING','RESOLVED')),
    system_output   JSONB NOT NULL DEFAULT '{}',
    evidence_ids    TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rt_status ON review_tasks(status);

CREATE TABLE IF NOT EXISTS review_actions (
    action_id       BIGSERIAL PRIMARY KEY,
    task_id         TEXT REFERENCES review_tasks,
    target_id       TEXT NOT NULL,
    decision        TEXT NOT NULL CHECK (decision IN ('accepted','rejected','modified','needs_evidence')),
    reviewer        TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    evidence_ids    TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- append-only：不提供 UPDATE/DELETE

-- ============================================================ 事件（日报）

CREATE TABLE IF NOT EXISTS report_events (
    event_id        TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL DEFAULT '',
    entities        TEXT[] NOT NULL DEFAULT '{}',
    fact_grade      TEXT NOT NULL DEFAULT 'report',
    skill_mentions  TEXT[] NOT NULL DEFAULT '{}',
    urls            TEXT[] NOT NULL DEFAULT '{}',
    published_at    DATE,
    is_primary      BOOLEAN NOT NULL DEFAULT TRUE,
    duplicate_group_id TEXT,
    prompt_version  INT,
    model_version   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_re_published ON report_events(published_at);
CREATE INDEX IF NOT EXISTS idx_re_primary ON report_events(is_primary) WHERE is_primary;

-- ============================================================ JD

CREATE TABLE IF NOT EXISTS jd_records (
    jd_id           TEXT PRIMARY KEY,
    platform        TEXT NOT NULL,
    title           TEXT NOT NULL,
    is_ai_role      BOOLEAN NOT NULL DEFAULT TRUE,
    domain_reason   TEXT DEFAULT '',
    publish_date    DATE,
    city            TEXT,
    salary          TEXT DEFAULT '',
    work_year       TEXT DEFAULT '',
    responsibilities JSONB NOT NULL DEFAULT '[]',
    requirements    JSONB NOT NULL DEFAULT '[]',
    skill_mentions  TEXT[] NOT NULL DEFAULT '{}',
    resolved        JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jd_platform ON jd_records(platform);
CREATE INDEX IF NOT EXISTS idx_jd_ai ON jd_records(is_ai_role) WHERE is_ai_role;
CREATE INDEX IF NOT EXISTS idx_jd_date ON jd_records(publish_date);

-- 数据资产版本登记：本地处理产物导入 PostgreSQL 后的可追溯快照。
CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_id          TEXT NOT NULL,
    dataset_version     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'IMPORTED'
                        CHECK (status IN ('IMPORTED','PARTIAL','FAILED','FROZEN')),
    record_count        INT NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    valid_record_count  INT NOT NULL DEFAULT 0 CHECK (valid_record_count >= 0),
    pending_record_count INT NOT NULL DEFAULT 0 CHECK (pending_record_count >= 0),
    quality_score       REAL NOT NULL DEFAULT 0 CHECK (quality_score >= 0 AND quality_score <= 1),
    manifest_hash       TEXT NOT NULL DEFAULT '',
    manifest            JSONB NOT NULL DEFAULT '{}',
    run_id              TEXT NOT NULL DEFAULT '',
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, dataset_version)
);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_latest
    ON dataset_versions(dataset_id, imported_at DESC);

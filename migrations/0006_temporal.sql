-- 时间情报和运行记录：预测结果与岗位影响建议均可回溯到运行与数据版本。

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    dataset_version TEXT NOT NULL DEFAULT '',
    config JSONB NOT NULL DEFAULT '{}',
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trend_signals (
    signal_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    skill_id TEXT NOT NULL REFERENCES capabilities(capability_id),
    signal_type TEXT NOT NULL DEFAULT 'mention',
    observed_at TIMESTAMPTZ NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.6,
    evidence_ids TEXT[] NOT NULL DEFAULT '{}',
    payload JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_signals_skill_time ON trend_signals(skill_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS backtest_records (
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id),
    as_of_date DATE NOT NULL,
    skill_id TEXT NOT NULL REFERENCES capabilities(capability_id),
    predicted_direction TEXT NOT NULL,
    actual_direction TEXT NOT NULL,
    hit BOOLEAN NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    recent REAL NOT NULL DEFAULT 0,
    prior REAL NOT NULL DEFAULT 0,
    rule_version INT NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id, as_of_date, skill_id)
);

CREATE TABLE IF NOT EXISTS forecasts (
    forecast_id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES pipeline_runs(run_id),
    skill_id TEXT NOT NULL REFERENCES capabilities(capability_id),
    as_of_date DATE NOT NULL,
    horizon_days INT NOT NULL,
    predicted_direction TEXT NOT NULL,
    predicted_heat REAL NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    valid_until DATE,
    rule_version INT NOT NULL DEFAULT 1,
    evidence_ids TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS job_impact_suggestions (
    suggestion_id TEXT PRIMARY KEY,
    forecast_id TEXT REFERENCES forecasts(forecast_id),
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    skill_id TEXT NOT NULL REFERENCES capabilities(capability_id),
    change_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

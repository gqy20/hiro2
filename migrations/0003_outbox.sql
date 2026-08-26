-- 业务事务提交后的异步投影事件；event_id 保证幂等。
CREATE TABLE IF NOT EXISTS outbox_events (
    event_id       TEXT PRIMARY KEY,
    event_type     TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id   TEXT NOT NULL,
    payload        JSONB NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED')),
    attempts       INT NOT NULL DEFAULT 0,
    available_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at   TIMESTAMPTZ,
    error_message  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox_events(status, available_at);

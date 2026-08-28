-- 域扩展：政策/大典/arXiv/简历档案入 PG 事实主库（ADR 0002）。
-- O*NET 与 snapshot-changesets 为分析快照/草稿语义，不入库（文件层即可）。

CREATE TABLE IF NOT EXISTS policies (
    policy_id   TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    puborg      TEXT NOT NULL DEFAULT '',
    pubdate     DATE,
    url         TEXT NOT NULL DEFAULT '',
    keyword     TEXT NOT NULL DEFAULT '',
    library     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_policies_pubdate ON policies(pubdate);
CREATE INDEX IF NOT EXISTS idx_policies_keyword ON policies(keyword);

CREATE TABLE IF NOT EXISTS dadian_careers (
    career_code TEXT NOT NULL,
    name        TEXT NOT NULL,
    parent      TEXT NOT NULL DEFAULT '',
    work_num    INT NOT NULL DEFAULT 0,
    version_id  INT NOT NULL,           -- 2015 / 2022（公示稿）/ 2（API 活数据）
    PRIMARY KEY (career_code, version_id)
);
CREATE INDEX IF NOT EXISTS idx_dadian_name ON dadian_careers(name);

CREATE TABLE IF NOT EXISTS arxiv_papers (
    arxiv_id    TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    published   DATE,
    categories  TEXT[] DEFAULT '{}',
    query       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_arxiv_published ON arxiv_papers(published);

CREATE TABLE IF NOT EXISTS resume_archive (
    resume_id   TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    size        INT NOT NULL DEFAULT 0,
    uploaded_at TIMESTAMPTZ,
    source      TEXT NOT NULL DEFAULT '',
    stats       JSONB DEFAULT '{}',
    profile     JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_resume_source ON resume_archive(source);

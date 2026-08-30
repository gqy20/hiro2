-- 学练赛证实体入库（ADR 0002 事实主库模式）：证书目录、竞赛目录、
-- 标准 PDF 工作要求表（certget/certparse/raceget 产物的结构化入库）。
-- CERTS.yml/CONTESTS.yml 的人工映射层不入库（文件层即事实，version 字段管理）。

CREATE TABLE IF NOT EXISTS cert_catalog (
    cert_id        TEXT PRIMARY KEY,          -- osta-std-<编码> / onex-<id> / hw-<name> / aidaxue-*
    name           TEXT NOT NULL,
    cert_type      TEXT NOT NULL DEFAULT '',  -- national_standard / onex_certificate / vendor_cert
    issuer         TEXT NOT NULL DEFAULT '',
    level          TEXT NOT NULL DEFAULT '',
    career_code    TEXT NOT NULL DEFAULT '',  -- osta 职业编码
    effective_from DATE,
    description    TEXT NOT NULL DEFAULT '',
    doc_number     TEXT NOT NULL DEFAULT '',  -- 发文号（osta）
    source         TEXT NOT NULL DEFAULT '',  -- osta / onex / huawei
    source_url     TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cert_name ON cert_catalog(name);
CREATE INDEX IF NOT EXISTS idx_cert_source ON cert_catalog(source);

CREATE TABLE IF NOT EXISTS race_catalog (
    race_id        TEXT PRIMARY KEY,          -- xfyun-<flag> / tianchi-<id> / df-<id>
    name           TEXT NOT NULL,
    race_type      TEXT NOT NULL DEFAULT '',  -- algorithm / application
    industry       TEXT NOT NULL DEFAULT '',  -- 平台行业分类（讯飞）
    organizer      TEXT NOT NULL DEFAULT '',
    bonus          TEXT NOT NULL DEFAULT '',
    team_count     INT,
    register_end   DATE,
    final_end      DATE,
    tags           TEXT[] DEFAULT '{}',       -- 平台技能标签（天池/DF）
    description    TEXT NOT NULL DEFAULT '',
    source         TEXT NOT NULL DEFAULT '',  -- xfyun / tianchi / datafountain
    source_url     TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_race_industry ON race_catalog(industry);
CREATE INDEX IF NOT EXISTS idx_race_source ON race_catalog(source);
CREATE INDEX IF NOT EXISTS idx_race_register_end ON race_catalog(register_end);

-- 国家职业标准 PDF 工作要求表（certparse 产物）：
-- 一行 = 某标准某等级的一个"工作内容"，skills/knowledge 为官方能力/知识要求条目
CREATE TABLE IF NOT EXISTS std_requirements (
    career_code  TEXT NOT NULL,
    level        TEXT NOT NULL DEFAULT '',    -- 初级/中级/高级/五级-初级工...
    func         TEXT NOT NULL DEFAULT '',    -- 职业功能
    work_no      TEXT NOT NULL DEFAULT '',    -- 工作内容编号（1.1）
    work         TEXT NOT NULL DEFAULT '',    -- 工作内容名
    skills       TEXT[] DEFAULT '{}',         -- 专业能力要求条目
    knowledge    TEXT[] DEFAULT '{}',         -- 相关知识要求条目
    PRIMARY KEY (career_code, level, work_no)
);
CREATE INDEX IF NOT EXISTS idx_std_level ON std_requirements(level);

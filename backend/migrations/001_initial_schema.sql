-- MCC Migration 001: Initial Schema
-- Run: psql $DATABASE_URL -f backend/migrations/001_initial_schema.sql

-- Extensions (already enabled, but idempotent)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enums
DO $$ BEGIN
    CREATE TYPE platform_enum AS ENUM ('x', 'slack');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE project_status_enum AS ENUM ('on_track', 'at_risk', 'blocked', 'completed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ingestion_status_enum AS ENUM ('success', 'failed', 'running');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE engine_enum AS ENUM ('keyword', 'semantic', 'side_by_side');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- posts table
CREATE TABLE IF NOT EXISTS posts (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform             platform_enum NOT NULL,
    external_id          VARCHAR NOT NULL UNIQUE,
    author               VARCHAR,
    content              TEXT,
    content_tsv          TSVECTOR,
    source_url           VARCHAR NOT NULL,
    published_at         TIMESTAMP,
    ingested_at          TIMESTAMP DEFAULT NOW(),
    likes                INT DEFAULT 0,
    retweets             INT DEFAULT 0,
    replies              INT DEFAULT 0,
    channel              VARCHAR,
    links                JSONB,
    embedding            VECTOR(1536),
    engagement_updated_at TIMESTAMP
);

-- project_updates table
CREATE TABLE IF NOT EXISTS project_updates (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_name VARCHAR NOT NULL,
    status       project_status_enum,
    update_text  TEXT,
    published_at TIMESTAMP DEFAULT NOW()
);

-- ingestion_checkpoints table
CREATE TABLE IF NOT EXISTS ingestion_checkpoints (
    source               VARCHAR PRIMARY KEY,
    last_id              VARCHAR,
    last_run_at          TIMESTAMP,
    status               ingestion_status_enum DEFAULT 'success',
    consecutive_failures INT DEFAULT 0
);

-- query_history table
CREATE TABLE IF NOT EXISTS query_history (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          VARCHAR,
    query_text       TEXT,
    filters          JSONB,
    engine           engine_enum,
    summary          TEXT,
    results_snapshot JSONB,
    result_count     INT,
    latency_ms       INT,
    created_at       TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS posts_content_tsv_idx ON posts USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS posts_embedding_idx ON posts USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS posts_platform_date_idx ON posts (platform, published_at);
CREATE INDEX IF NOT EXISTS posts_channel_idx ON posts (channel);
-- external_id unique index already created by UNIQUE constraint

-- Trigger: auto-generate content_tsv on insert/update
CREATE OR REPLACE FUNCTION posts_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS posts_tsv_trigger ON posts;
CREATE TRIGGER posts_tsv_trigger
    BEFORE INSERT OR UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION posts_tsv_update();

-- Seed ingestion checkpoints
INSERT INTO ingestion_checkpoints (source, status, consecutive_failures)
VALUES ('slack', 'success', 0), ('x', 'success', 0), ('openclaw', 'success', 0)
ON CONFLICT (source) DO NOTHING;

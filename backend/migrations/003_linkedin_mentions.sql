-- MCC Migration 002: LinkedIn Mentions
-- Run: psql $DATABASE_URL -f backend/migrations/002_linkedin_mentions.sql

-- Add 'linkedin' to the platform enum
ALTER TYPE platform_enum ADD VALUE IF NOT EXISTS 'linkedin';

-- Add is_mention flag to posts (used to tag mention-search results vs. feed posts)
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_mention BOOLEAN DEFAULT FALSE;

-- Index for fast @Mentions tab queries
CREATE INDEX IF NOT EXISTS posts_is_mention_idx ON posts (is_mention, published_at DESC);

-- Seed checkpoint for linkedin_mentions ingestion
INSERT INTO ingestion_checkpoints (source, status, consecutive_failures)
VALUES ('linkedin_mentions', 'success', 0)
ON CONFLICT (source) DO NOTHING;

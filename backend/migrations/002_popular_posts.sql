-- Migration 002: Popular Posts
-- Creates the popular_posts table for tracking high-engagement content

CREATE TABLE popular_posts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id        UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  flagged_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  triggered_by   TEXT NOT NULL,  -- 'likes' | 'views' | 'reposts' | 'replies' | 'slack_thread_replies'
  metric_value   INTEGER NOT NULL,  -- value that crossed the threshold
  alerted        BOOLEAN DEFAULT FALSE,
  alerted_at     TIMESTAMPTZ,
  UNIQUE(post_id)  -- one record per post, first trigger wins
);

CREATE INDEX idx_popular_posts_flagged ON popular_posts(flagged_at DESC);

-- Add views column to posts for X impression_count
ALTER TABLE posts ADD COLUMN IF NOT EXISTS views INTEGER;

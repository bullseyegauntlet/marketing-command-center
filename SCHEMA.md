# SCHEMA.md — Database Schema

Marketing Command Center | PostgreSQL 16 + pgvector

> Keep this file in sync with actual migrations. Update it whenever a migration runs.

---

## Tables

### `posts`

Stores all ingested social content (X tweets + Slack messages).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| platform | ENUM('x', 'slack') | Source platform |
| external_id | VARCHAR UNIQUE | Tweet ID or Slack message ts |
| author | VARCHAR | Username or display name |
| content | TEXT | Full post/message text |
| content_tsv | TSVECTOR | Auto-generated full-text search index (via trigger) |
| source_url | VARCHAR NOT NULL | Direct link to original post |
| published_at | TIMESTAMP | When post was created (UTC) |
| ingested_at | TIMESTAMP | When we indexed it |
| likes | INT | X only; refreshed periodically |
| retweets | INT | X only; refreshed periodically |
| replies | INT | X only; refreshed periodically |
| channel | VARCHAR | Slack channel name or X list name |
| links | JSONB | Array of URLs extracted from post |
| embedding | VECTOR(1536) | For semantic search via pgvector |
| engagement_updated_at | TIMESTAMP | Last engagement metric refresh |

### `project_updates`

Stores OpenClaw project status updates ingested from Slack.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| project_name | VARCHAR | e.g. "Website Redesign" |
| status | ENUM('on_track', 'at_risk', 'blocked', 'completed') | |
| update_text | TEXT | Full update body |
| published_at | TIMESTAMP | When sent (UTC) |

### `ingestion_checkpoints`

Tracks ingestion state per source for resumability.

| Column | Type | Notes |
|--------|------|-------|
| source | VARCHAR PK | 'slack' \| 'x' \| 'openclaw' |
| last_id | VARCHAR | Last ingested external ID or cursor |
| last_run_at | TIMESTAMP | When job last completed |
| status | ENUM('success', 'failed', 'running') | |
| consecutive_failures | INT | Alert triggered at >= 2 |

### `query_history`

Stores every query and its full result snapshot.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| user_id | VARCHAR | Who ran the query |
| query_text | TEXT | Original natural-language query |
| filters | JSONB | Platform, time range, channel/list filters |
| engine | ENUM('keyword', 'semantic', 'side_by_side') | |
| summary | TEXT | AI-generated grounded summary |
| results_snapshot | JSONB | Full result set at query time |
| result_count | INT | Number of results returned |
| latency_ms | INT | Total query response time |
| created_at | TIMESTAMP | When query was run |

---

## Indexes

| Name | Type | Column(s) | Purpose |
|------|------|-----------|---------|
| posts_content_tsv | GIN | content_tsv | Full-text keyword search |
| posts_embedding_idx | HNSW (vector_cosine_ops) | embedding | Semantic similarity search |
| posts_platform_date | B-tree composite | (platform, published_at) | Fast platform + date filtering |
| posts_channel | B-tree | channel | Fast channel/list filtering |
| posts_external_id | Unique B-tree | external_id | Deduplication at ingestion |

---

## Triggers

- `posts_tsv_update` — on INSERT or UPDATE to `posts`, auto-generates `content_tsv` from `content` using `to_tsvector('english', content)`

---

## Extensions Required

```sql
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- UUID generation
```

---

## Backup & Restore

- Railway automated daily backups are enabled for the PostgreSQL instance
- To restore: Railway dashboard → Database → Backups → select snapshot → Restore
- After restore, re-run any pending migrations manually

---

## Migration History

| File | Description | Date |
|------|-------------|------|
| 001_initial_schema.sql | Created posts, project_updates, ingestion_checkpoints, query_history tables + all indexes + tsvector trigger | 2026-03-20 |

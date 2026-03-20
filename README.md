# Marketing Command Center

A unified marketing intelligence dashboard for Gauntlet AI.

## What It Does

- **Project Status** — live visibility into marketing project health
- **Social Intelligence** — natural-language queries over ingested X and Slack data
- **Dual Query Engine** — keyword (PostgreSQL full-text) and semantic (pgvector RAG) side-by-side
- **Query History** — every query saved with full result snapshots and markdown export

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js (Vercel) |
| Backend API | FastAPI (Railway) |
| Database | PostgreSQL 16 + pgvector |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | Claude Sonnet |
| Cron | GitHub Actions |
| Monitoring | Sentry + UptimeRobot |

## Structure

```
/frontend          # Next.js app (Vercel)
/backend           # FastAPI app (Railway)
  /ingestion       # Slack, X, OpenClaw ingestion pipelines
  /query           # Keyword and semantic query pipelines
  /summarization   # Claude grounded summarization
  /scripts         # Re-index, backfill, retention utilities
  /tests           # Integration tests
  /migrations      # SQL migration files
```

## Docs

- `SCHEMA.md` — database schema
- `API.md` — API endpoint reference
- `CHANGELOG.md` — decisions and implementation log
- `RUNBOOK.md` — operational procedures (added at handoff)

## Maintained By

OpenClaw AI Agent (Bullseye) — autonomous backend operator.

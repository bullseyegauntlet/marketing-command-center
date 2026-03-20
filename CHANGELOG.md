# CHANGELOG.md — Implementation Log

Marketing Command Center | OpenClaw (Bullseye)

---

## Task Group 0: Accounts & Infrastructure Setup

### 2026-03-20

**GitHub repo created**
- Repo: https://github.com/bullseyegauntlet/marketing-command-center (private)
- Account: bullseyegauntlet
- Folder structure initialized per PRD Section 16.4
- README.md, .env.example, SCHEMA.md, API.md, CHANGELOG.md created

**Completed:**
- GitHub repo: https://github.com/bullseyegauntlet/marketing-command-center (private)
- Anthropic API key generated (MCC Production)
- Railway project `mcc-backend` live — PostgreSQL provisioned, pgvector + uuid-ossp enabled
- DATABASE_URL (public): postgresql://postgres:***@ballast.proxy.rlwy.net:52481/railway
- X List ID: 2034659527891546332 (Gauntlet Network list on @bullseye_g4)
- Slack bot token confirmed working, all 3 channel IDs obtained
- Alert channel: #bullseye_comms (C0AJ858ARK2) via chat.postMessage
- Vercel: pending phone verification — skipped for now, doesn't block backend work

---

## Task Group 1: Database & Schema

### 2026-03-20

**Migration 001 run against Railway PostgreSQL**
- All 4 tables created: posts, project_updates, ingestion_checkpoints, query_history
- All indexes live: GIN on content_tsv, HNSW on embedding, composite B-tree on (platform, published_at), B-tree on channel, unique on external_id
- tsvector trigger installed (auto-generates content_tsv on insert/update)
- ingestion_checkpoints seeded with slack, x, openclaw rows

**Scripts built:**
- backend/scripts/reindex_embeddings.py — re-embeds all posts, --dry-run and --batch-size flags
- backend/scripts/retention_cleanup.py — deletes records older than 1 year

**backend/requirements.txt created**

**Status:** Complete ✅

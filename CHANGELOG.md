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

---

## Task Group 5: Frontend — Next.js Dashboard

### 2026-03-24

**Next.js 16.2.1 app scaffolded** in `/frontend`
- TypeScript + Tailwind CSS (v4) + App Router
- shadcn/ui initialized (Tailwind v4 compatible)
- shadcn components added: button, badge, card, tabs, separator, skeleton, input, label, textarea, select

**Design system:**
- Dark theme throughout (no light mode — this is a command center, not a SaaS landing page)
- Color palette: `#0a0a0f` background, `#111118` cards, `#2563ff` electric blue accent
- Fonts: Geist Sans (UI chrome) + Geist Mono (data/content)
- Staggered card reveal animation (50ms delay per card, max 500ms)

**Pages built:**

1. **Query page** (`/`) — main intelligence query interface
   - Text input with Enter-to-run, Shift+Enter for newline
   - 3 modes: Keyword / Semantic / Side-by-Side (toggle pill selector)
   - Results as cards: author + content + source link + timestamp + engagement
   - Side-by-Side: two columns + Claude summary at top
   - Loading skeletons, error state, empty state

2. **Query History page** (`/history`) — paginated query log
   - Paginated table (20/page) with engine badge, query text, result count, latency, relative timestamp
   - Click to expand: loads full result snapshot + AI summary
   - Export to markdown button (triggers download of .md file from backend)
   - Loading skeletons throughout

**Shared components:**
- `NavBar` — sticky top bar with logo + page nav
- `StatsBar` — live stats strip: total posts, X count, Slack count, last ingest time
- `ResultCard` — post card with platform badge, engagement metrics, source link

**API client** (`lib/api.ts`):
- Typed wrappers for all MCC endpoints: keyword/semantic/compare queries, stats, history, export
- `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000`)
- `.env.local` created

**Build:** ✅ `npm run build` passes clean — 0 errors, 0 warnings
- Routes compiled: `/` (static), `/history` (static)

**Status:** Complete ✅

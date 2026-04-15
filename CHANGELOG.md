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

---

## LinkedIn Mentions Ingestion

### 2026-04-15

**Research completed** — see `LINKEDIN_RESEARCH.md`
- Official LinkedIn API ruled out (can't fetch arbitrary posts)
- Decision: `linkedin-api` (unofficial, free) as primary; Proxycurl as paid fallback
- Primary use case: keyword/mention monitoring (not profile following)

**Migration 002 written** (`backend/migrations/002_linkedin_mentions.sql`)
- Added `linkedin` to `platform_enum`
- Added `is_mention BOOLEAN` column + index to `posts` table
- Seeded `linkedin_mentions` row in `ingestion_checkpoints`

**Ingestion script built** (`backend/ingestion/linkedin_mentions_ingestion.py`)
- Searches LinkedIn for each keyword in `LINKEDIN_MENTION_KEYWORDS` (default: "Gauntlet AI,gauntletai")
- Parses author name, post text, engagement metrics, links, URN-based external_id
- Embeds and inserts with `platform='linkedin'`, `is_mention=True`, `channel='linkedin_mentions'`
- Full dedup (across keyword runs + DB), dead letter logging, Slack alerts on repeated failures
- Checkpoint pattern matches X/Slack ingestion (source = `'linkedin_mentions'`)

**`requirements.txt`** updated: added `linkedin-api>=2.3.1`

**2026-04-15 — LinkedIn bot account created + full pipeline wired**
- Bot account: `bullseye.gauntlet@gmail.com` via Google OAuth
- Profile: `linkedin.com/in/bullseye-undefined-290927403/`
- Session cookies saved to `~/.openclaw/secrets/linkedin_cookies.json` + GitHub Actions secret `LINKEDIN_COOKIES_JSON`
- Migration `003_linkedin_mentions.sql` renumbered (was 002, collided with popular_posts migration) and run on Railway ✅
- `linkedin_mentions_ingestion.py` updated to:
  - Match popular posts pattern from `x_ingestion.py` — calls `check_popular_thresholds()` on each new insert
  - Fire `🔥 Viral LinkedIn Post Detected` Slack alert to `#bullseye_comms` when thresholds crossed
  - Popularity thresholds: `POPULAR_THRESHOLD_LI_LIKES=500`, `POPULAR_THRESHOLD_LI_REPOSTS=100`, `POPULAR_THRESHOLD_LI_REPLIES=50`
- `cron-ingestion.yml` GitHub Actions workflow created:
  - `engagement_recheck.py` — every 4 hours (matches PRD cadence)
  - `linkedin_mentions_ingestion.py` — daily at 08:00 UTC
  - Manual `workflow_dispatch` trigger for both jobs
- GitHub secrets set: `LINKEDIN_COOKIES_JSON`, `LINKEDIN_EMAIL`, `LINKEDIN_MENTION_KEYWORDS`

**Pending:**
- Build `GET /api/mentions` backend endpoint (Phase 2 of @Mentions tab PRD)
- Build frontend @Mentions tab + Popular Posts tab (PRD phases 2-3)
- Cookie refresh reminder: LinkedIn session cookies expire ~every 2 weeks — refresh manually when needed

# PRD: Popular Posts Tab — Marketing Command Center
**Status:** Draft  
**Author:** Bullseye  
**Date:** 2026-04-14  
**Version:** 1.0

---

## Overview

Add a **Popular Posts** tab to the MCC — a persistent, auto-curated list of the highest-engagement content from X and Slack. When a post crosses defined viral thresholds, it's flagged, stored permanently, and an alert fires to `#bullseye_comms`. The tab gives the team a living record of what's breaking through, without any manual curation.

---

## Problem Statement

High-engagement posts on X or explosive Slack threads are the team's clearest signal of what's resonating — with the community, with the industry, or about Gauntlet specifically. Right now there's no systematic way to catch these. They get noticed by whoever happens to be watching at the right time. Popular Posts makes this automatic and persistent.

---

## Goals

- Surface high-engagement X posts and Slack threads in a single persistent feed
- Alert `#bullseye_comms` in real time when a new post qualifies
- Store popular posts permanently in the DB — they never age out
- Keep infrastructure cost increase minimal (no new services, no polling frequency increase beyond what's justified)

---

## Non-Goals

- No LinkedIn in v1 (LinkedIn ingestion isn't live yet)
- No manual curation or "add to list" feature — fully automated
- No sentiment analysis or AI summaries on popular posts in v1
- No email or other notification channels in v1 — Slack only
- Not a replacement for the search tab — popular posts is a curated feed, not a query interface

---

## Qualification Thresholds

A post is flagged as popular if it meets **any** of the following:

| Platform | Metric | Threshold |
|---|---|---|
| X | Views (impression_count) | > 10,000 |
| X | Likes | > 500 |
| X | Comments/replies | > 50 |
| X | Reposts | > 100 |
| Slack | Thread replies | > 20 |

These thresholds are configurable via env vars (`POPULAR_THRESHOLD_X_VIEWS`, etc.) so they can be tuned without a code deploy.

---

## UI Changes

### Tab Toggle — StatsBar

The StatsBar pill toggle (introduced in the @Mentions PRD) extends to three tabs:

```
[  Search  ]  [  @Mentions  ]  [  🔥 Popular  ]
```

- `🔥` emoji badge on the tab label (optional — can be dropped if too busy)
- When a new popular post is added since the user last visited the tab, show a numeric badge: `Popular (3)`
- Badge count stored in `localStorage` keyed to `popular_posts_last_seen` timestamp

### Popular Posts Feed Layout

```
┌─────────────────────────────────────────────────────────┐
│  NavBar                                                 │
├─────────────────────────────────────────────────────────┤
│  Live · 5,403 posts · [ Search ] [ @Mentions ] [🔥 Popular] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Popular Posts                                          │
│  High-engagement content from X and Slack               │
│                                                         │
│  ┌── Filter bar ────────────────────────────────────┐  │
│  │  Platform: [ All ▾ ]  [ X ]  [ Slack ]           │  │
│  │  Time:     [ Last 30 days ▾ ]                    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌── Popular post card ─────────────────────────────┐  │
│  │  🔥 [X]  @username  ·  3h ago                    │  │
│  │  "Just finished Gauntlet AI's program — this      │  │
│  │   changed everything about how I build with AI"  │  │
│  │  👁 14.2K  ❤ 823  🔁 142  💬 67                 │  │
│  │  [Open on X →]                          Flagged ✓ │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌── Popular slack thread card ─────────────────────┐  │
│  │  💬 [Slack]  #claude-maxxing  ·  Yesterday       │  │
│  │  "Has anyone actually shipped a production RAG   │  │
│  │   system with sub-100ms latency? Asking for..."  │  │
│  │  💬 34 replies                     Flagged ✓     │  │
│  │  [Open in Slack →]                               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [ Load more ]                                          │
└─────────────────────────────────────────────────────────┘
```

Cards reuse `ResultCard` with additions:
- `🔥` flame indicator and "Flagged ✓" label
- Engagement metric row (views, likes, reposts, replies) — already available on existing `Post` type
- Default sort: most recently flagged first

---

## Data Model

### Option A: `is_popular` flag on `posts` table (simple)
```sql
ALTER TABLE posts ADD COLUMN is_popular BOOLEAN DEFAULT FALSE;
ALTER TABLE posts ADD COLUMN popular_flagged_at TIMESTAMPTZ;
ALTER TABLE posts ADD COLUMN popular_alerted BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_posts_popular ON posts(is_popular, popular_flagged_at DESC) WHERE is_popular = TRUE;
```

### Option B: Separate `popular_posts` table (richer)
```sql
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
```

**Recommendation: Option B.** The separate table lets us record *why* a post was flagged (which metric crossed first), when it was alerted, and deduplicate alerts cleanly. It also means the `posts` table stays lean and popular posts can be queried efficiently without a full-table filter. The `UNIQUE(post_id)` constraint prevents duplicate flagging.

---

## Detection Architecture

This is the core design challenge: engagement grows *after* initial ingestion, so a post that doesn't qualify at insert time may qualify hours later. We need a way to re-check without hammering APIs.

### Layer 1: Check at Ingestion Time (free)

In `x_ingestion.py` and `slack_ingestion.py`, after inserting each post, immediately check thresholds against the just-fetched metrics. If a brand-new post already has >500 likes at ingestion time (rare but possible for viral content), flag it immediately.

Cost: zero — we already have the data.

### Layer 2: Engagement Re-check Pass (low cost)

Add a new lightweight script: `engagement_recheck.py`

**Logic:**
- Query posts ingested in the last 72 hours that are NOT yet flagged as popular
- For X posts: fetch updated metrics from `GET /2/tweets?ids=...` (supports batches of 100 per request)
- For Slack threads: fetch updated reply counts from `conversations.replies` (count only, no full fetch)
- Check thresholds; flag any that now qualify

**Cadence:** Run every **4 hours** via cron. 

**Cost analysis for X:**
- Typical MCC X ingestion: ~100 new tweets/day
- Posts stay in the re-check window for 72 hours → ~300 tweets in the pool at any time
- 3 API calls per run (100 per batch) × 6 runs/day = **18 X API calls/day**
- X free tier allows 500k tweet reads/month — this is negligible
- Slack `conversations.replies` with `limit=1` to get count: one call per thread per run; at ~50 active threads in 72h window → ~50 Slack calls per run. Fine.

**Why 4 hours?** Viral X content typically peaks within the first few hours. 4h cadence catches most events within half a day of going viral. This is the best cost/latency tradeoff. Could go to 2h if the team wants faster detection — still cheap.

### Layer 3: X Webhook / Filtered Stream (optional, v2)

X's filtered stream (`/2/tweets/search/stream`) can push tweets matching keywords in real time. This would eliminate the re-check polling entirely for *new* mentions. However:
- Requires the same API tier we already have
- Adds infrastructure complexity (persistent connection)
- Overkill for v1 given the re-check pass works fine

**Defer to v2.**

### Slack Thread Detection

Slack doesn't offer webhooks for "thread now has >20 replies." Options:

1. **Re-check on ingestion cron**: existing `slack_ingestion.py` fetches recent messages — when it sees a message that is itself a thread root (has `reply_count` in the API response), check if `reply_count > 20`. This runs at the existing cron cadence (daily currently; recommend bumping to every 4h to match X re-check).

2. **Slack Events API**: `message.replied` event fires when someone replies to a thread. Would require a persistent webhook endpoint. More infrastructure, more reliability risk. **Defer to v2.**

**v1 approach:** Add reply count threshold check inside the existing Slack ingestion loop. When fetching channel history, Slack's `conversations.history` already returns `reply_count` on threaded messages — no extra API call needed.

---

## Alert System — #bullseye_comms

Channel ID: `C0AJ858ARK2`

### Alert Message Format

**X post alert:**
```
🔥 *Viral X Post Detected*

*@username* posted something taking off:

> "Just finished Gauntlet AI's program — this changed everything about how I build with AI..."

👁 *14,200 views*  ❤ *823 likes*  🔁 *142 reposts*  💬 *67 replies*
📎 https://x.com/username/status/12345

_Triggered by: 823 likes (threshold: 500)_
```

**Slack thread alert:**
```
🔥 *Hot Slack Thread Detected*

*#claude-maxxing* thread is blowing up:

> "Has anyone actually shipped a production RAG system with sub-100ms latency?..."

💬 *34 replies*
📎 https://gauntlet-ai.slack.com/archives/C0962HWTYAK/p1234567890

_Triggered by: 34 thread replies (threshold: 20)_
```

### Deduplication

- `popular_posts.alerted` column prevents double-alerting for the same post
- Alert fires once — when `alerted = FALSE` → send message → set `alerted = TRUE`, `alerted_at = NOW()`
- If engagement continues to grow (post gains more likes), no additional alerts (unless we add "milestone" alerts in v2)

### Alert sending

Reuses the existing `send_alert()` pattern from `x_ingestion.py` — `POST /chat.postMessage` with `SLACK_BOT_TOKEN`. No new infrastructure.

---

## Backend API Changes

### New endpoint: `GET /api/popular`

```
GET /api/popular?platform=x&days=30&page=1&page_size=20
```

**Query params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `platform` | `x` \| `slack` \| `all` | `all` | Filter by platform |
| `days` | int | `30` | Look-back window (based on `popular_flagged_at`, not `published_at`) |
| `page` | int | `1` | Pagination |
| `page_size` | int | `20` | Results per page |

**Response:**
```json
{
  "posts": [Post],
  "total": 47,
  "page": 1,
  "page_size": 20,
  "by_platform": { "x": 41, "slack": 6 }
}
```

`Post` shape is the same existing type in `lib/api.ts`, extended with:
```typescript
flagged_at?: string;       // ISO timestamp when flagged as popular
triggered_by?: string;     // 'likes' | 'views' | 'reposts' | 'replies' | 'slack_thread_replies'
metric_value?: number;     // value that triggered the flag
```

### Stats endpoint update

`GET /api/stats` response adds:
```json
{
  "popular": { "total": 47, "last_24h": 3 }
}
```

Used to drive the badge count on the Popular Posts tab.

---

## New Backend Files

### `backend/ingestion/engagement_recheck.py`
- Standalone script, runs on cron every 4 hours
- Fetches posts from last 72h that aren't flagged as popular
- Batch-fetches X metrics (100/req), checks Slack reply counts
- Flags qualifying posts in `popular_posts` table
- Sends Slack alerts for newly flagged posts

### `backend/query/popular.py` (or inline in `main.py`)
- `GET /api/popular` endpoint handler
- Joins `popular_posts` with `posts` for the feed

---

## Frontend Changes

### `components/stats-bar.tsx`
- Extend tab toggle to three pills: Search / @Mentions / Popular
- Fetch `stats.popular.last_24h` and show as badge if > 0

### `app/page.tsx`
- Add `"popular"` to `activeTab` type
- Render `<PopularFeed />` when Popular tab is active

### New `components/popular-feed.tsx`
- Fetches from `/api/popular`
- Platform filter (All / X / Slack) + time range (7d / 30d / All time)
- Uses `ResultCard` with a flame badge overlay and triggered-by metadata
- Empty state: "No posts have crossed the popularity threshold yet."
- Sort: most recently flagged first (not most recently published)

### `lib/api.ts` additions
```typescript
export interface PopularFeed {
  posts: PopularPost[];
  total: number;
  page: number;
  page_size: number;
  by_platform: { x: number; slack: number };
}

export interface PopularPost extends Post {
  flagged_at: string;
  triggered_by: string;
  metric_value: number;
}

export async function getPopularPosts(params: {
  platform?: "x" | "slack" | "all";
  days?: number;
  page?: number;
  page_size?: number;
}): Promise<PopularFeed>
```

---

## Phased Delivery

### Phase 1 — Core detection + alerts (1.5–2 days)
- `popular_posts` DB table + migration
- Threshold check at ingestion time (in both `x_ingestion.py` and `slack_ingestion.py`)
- `engagement_recheck.py` script + cron (every 4h)
- Slack alert to `#bullseye_comms` on new flags
- `GET /api/popular` endpoint

### Phase 2 — UI (1 day)
- Three-tab toggle in StatsBar
- `popular-feed.tsx` component
- Badge count on tab label
- `lib/api.ts` additions

### Phase 3 — Polish (0.5 days)
- Configurable thresholds via env vars
- "New since last visit" badge in localStorage
- `triggered_by` label on cards ("Flagged for 823 likes")

---

## Open Questions

1. **Cron cadence for Slack ingestion**: Currently runs daily. Should bump to every 4h to match X re-check and catch hot threads faster. Any concern about Slack API rate limits at that cadence?

2. **Threshold tuning**: The proposed thresholds (10k views / 500 likes / 50 comments / 100 reposts / 20 Slack replies) — are these right for Gauntlet's current volume? Could calibrate after a week of data.

3. **X views field**: The `impression_count` field requires `tweet.fields=public_metrics` in the API call. Current X ingestion already fetches `public_metrics` — but confirm `impression_count` is included (it was added by X later and may need to be explicitly requested).

4. **All-time popular posts**: The tab defaults to "last 30 days" but popular posts are stored permanently. Should there be an "All time" option in the time filter from day one?

5. **Milestone alerts**: Should we send a second alert when a post crosses a higher threshold (e.g., first alert at 500 likes, second at 5,000)? Out of scope for v1 but worth designing for.

---

## Success Metrics

- At least one popular post detected and alerted per week
- Alert fires within 4 hours of a post crossing a threshold
- Zero duplicate alerts for the same post
- Team reports the tab is useful in the first two weeks without prompting

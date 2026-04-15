# PRD: @Mentions Tab — Marketing Command Center
**Status:** Draft  
**Author:** Bullseye  
**Date:** 2026-04-14  
**Version:** 1.0

---

## Overview

Add an **@Mentions** tab to the MCC that surfaces any public conversation mentioning Gauntlet AI — on X and LinkedIn — in near real-time. This gives the marketing team a single place to monitor brand presence, engagement opportunities, and competitive chatter without manually searching either platform.

---

## Problem Statement

Right now MCC is a **search-first** tool: you have to know what you're looking for. There's no passive monitoring. If someone tweets about Gauntlet AI or mentions us in a LinkedIn post, the team finds out by accident — or not at all. At the volume Gauntlet is growing, that's a gap.

The @Mentions tab flips the posture: instead of pulling signal on demand, it surfaces the signal that's already out there and pointing at us.

---

## Goals

- Give the marketing team instant visibility into who is talking about Gauntlet AI publicly, on which platforms, and with what sentiment
- Require zero active searching — the feed is always there, auto-refreshed
- Support action: make it easy to open the original post and engage
- Lay the groundwork for LinkedIn as a data source in MCC (complementary to the LinkedIn ingestion work)

---

## Non-Goals

- No Slack mentions (Slack is internal — @mentions there are a different product problem)
- No auto-reply or engagement workflows (out of scope for v1)
- No sentiment scoring or AI analysis in v1 (can add later)
- No Instagram, TikTok, or other platforms in v1

---

## UI Changes

### Tab Toggle — StatsBar area

The current `StatsBar` renders below the `NavBar` as a thin bar:
```
Live · 5,403 posts · 2,910 Slack · 2,493 X · Updated 6h ago
```

This bar becomes a **dual-purpose component**: the left side retains the live stats, and the right side (or center) gets a **two-tab toggle**:

```
[  Search  ]  [  @Mentions  ]
```

- Tabs are pill-style toggles, consistent with the existing nav link style in `nav-bar.tsx`
- Active tab is highlighted (uses existing `bg-accent text-primary` pattern)
- Toggle lives **inside the StatsBar strip** — keeps the page structure flat, no new header row
- On mobile, the stats text can truncate; the tab toggle stays visible

**Alternate placement (if StatsBar feels cramped):** Tabs move just below StatsBar as a standalone row — same pill style, full width, left-aligned. Decide at implementation.

### @Mentions Page Layout

The @Mentions tab replaces the main content area (not a new route — it's a state switch on the homepage, same as how the existing search/results are managed in `page.tsx`).

```
┌─────────────────────────────────────────────────────────┐
│  NavBar                                                 │
├─────────────────────────────────────────────────────────┤
│  Live · 5,403 posts · [  Search  ] [● @Mentions ]      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  @Mentions                                              │
│  People talking about Gauntlet AI                       │
│                                                         │
│  ┌── Filter bar ────────────────────────────────────┐  │
│  │  Platform: [ All ▾ ]  [ X ]  [ LinkedIn ]        │  │
│  │  Time:     [ Last 7 days ▾ ]                     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌── Mention card ──────────────────────────────────┐  │
│  │  [X]  @username  ·  2h ago                       │  │
│  │  "Just got accepted into @GauntletAI's cohort    │  │
│  │   — insane program, can't wait to start..."      │  │
│  │  ❤ 24  🔁 8  💬 3      [Open on X →]            │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [ Load more ]                                          │
└─────────────────────────────────────────────────────────┘
```

**Mention cards** reuse the existing `ResultCard` component with a minor addition: a colored platform badge (X = black, LinkedIn = blue) and a direct "Open →" link to the source post.

**No search bar** on this tab — the feed is the product. The filter bar provides enough control.

---

## Data Model

### New `mentions` table (or `is_mention` flag on `posts`)

**Option A (preferred for v1): Add a boolean column to `posts`**

```sql
ALTER TABLE posts ADD COLUMN is_mention BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_posts_is_mention ON posts(is_mention, published_at DESC);
```

Simpler, no schema migration complexity. Mentions are just tagged posts — they can still be searched and queried like any other post.

**Option B:** Separate `mentions` table. Better long-term if mention-specific metadata (context, matched keyword, etc.) becomes important. Overkill for v1.

**Recommendation:** Option A now, migrate to Option B if we need mention-specific fields later.

---

## Ingestion Changes

### X Mentions Ingestion

X API v2 provides a **search endpoint** that can find mentions:

```
GET /2/tweets/search/recent?query=@GauntletAI OR "Gauntlet AI" OR gauntletai
```

- Requires Basic tier ($100/mo) or above for full search access; free tier has limited search
- Returns up to 100 results per page, up to 7 days back on Basic tier
- Fields: same as current list tweet fields — maps directly to existing `posts` schema
- **Different from the current list-based ingestion** — this is search, not list feed

**Implementation:**
- New `x_mentions_ingestion.py` alongside `x_ingestion.py`
- Runs on its own cron (every 2-4h recommended; search quota is separate from list quota)
- Tags inserted posts with `is_mention = TRUE`
- Uses same checkpoint pattern (`ingestion_checkpoints` table, source = `'x_mentions'`)
- Search query: `"Gauntlet AI" OR @GauntletAI OR gauntletai -is:retweet lang:en`
  - `-is:retweet` filters out pure RTs (still captures quotes)
  - `lang:en` optional but recommended

### LinkedIn Mentions Ingestion

**Keyword-search only — no profile list.** The goal is a pulse on what people are broadly saying about Gauntlet AI, not monitoring specific accounts. We search LinkedIn for posts containing our keywords and ingest whatever comes back.

Using `linkedin-api` keyword search:

```python
api.search_posts(keywords="Gauntlet AI")
# Also run: "gauntletai", "Gauntlet AI program", "Gauntlet cohort"
```

- No `LINKEDIN_PROFILE_IDS` env var needed for mentions — just `LINKEDIN_KEYWORDS`
- New `linkedin_mentions_ingestion.py` (separate from any future profile-follow ingestion)
- Tags inserted posts with `is_mention = TRUE`, `platform = 'linkedin'`
- Runs daily (LinkedIn scraping is rate-limited — daily cadence is safe)
- Uses checkpoint pattern, source = `'linkedin_mentions'`
- Deduplicates by `external_id` as usual

**Keyword set (configurable via env):**
```
LINKEDIN_MENTION_KEYWORDS=Gauntlet AI,gauntletai,Gauntlet AI program,GauntletAI
```

**Note:** `linkedin-api` post search reliability can vary; if a keyword returns zero results consistently, it may need a session refresh or slight query variation. The ingestion script should log zero-result runs for monitoring.

---

## Backend API Changes

### New endpoint: `GET /api/mentions`

```
GET /api/mentions?platform=x&days=7&page=1&page_size=20
```

**Query params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `platform` | `x` \| `linkedin` \| `all` | `all` | Filter by platform |
| `days` | int | `7` | Look-back window |
| `page` | int | `1` | Pagination |
| `page_size` | int | `20` | Results per page |

**Response:**
```json
{
  "mentions": [Post],
  "total": 142,
  "page": 1,
  "page_size": 20,
  "by_platform": { "x": 118, "linkedin": 24 }
}
```

`Post` shape is identical to the existing `Post` type in `lib/api.ts` — no new types needed on the frontend.

### Stats bar update

`GET /api/stats` response should include a mention count summary:

```json
{
  "total_posts": 5403,
  "posts_by_platform": { "x": 2493, "slack": 2910, "linkedin": 0 },
  "mentions": { "total": 142, "x": 118, "linkedin": 24, "last_24h": 12 },
  "last_ingestion": [...]
}
```

The StatsBar component can optionally surface the `last_24h` count as a small badge on the @Mentions tab label.

---

## Frontend Changes

### `components/stats-bar.tsx`
- Add tab toggle state: `"search" | "mentions"`
- Pass active tab + setter up to parent (or use a shared context/URL param)
- Optionally: show `mentions.last_24h` as a small badge on the @Mentions tab pill

### `app/page.tsx`
- Accept `activeTab` prop or read from URL param (`?tab=mentions`)
- Render either `<SearchView />` (existing content) or `<MentionsView />` (new) based on active tab
- Recommended: URL param approach (`?tab=mentions`) so the tab state is shareable/bookmarkable

### New `components/mentions-feed.tsx`
- Fetches from `/api/mentions` with filter state
- Platform filter pills: All / X / LinkedIn
- Time range select: 24h / 7 days / 30 days
- Infinite scroll or paginated "Load more"
- Uses `ResultCard` for each mention card (no new card component needed)
- Empty state: "No mentions found in the last 7 days. Try expanding the time range."

### `lib/api.ts` additions
```typescript
export interface MentionsFeed {
  mentions: Post[];
  total: number;
  page: number;
  page_size: number;
  by_platform: { x: number; linkedin: number };
}

export async function getMentions(params: {
  platform?: "x" | "linkedin" | "all";
  days?: number;
  page?: number;
  page_size?: number;
}): Promise<MentionsFeed>
```

---

## Stats Bar Mock — After Change

```
Live · [  Search  ] [● @Mentions  12 new ]   5,403 posts · 2,910 Slack · 2,493 X · Updated 6h ago
```

On smaller viewports the post counts can truncate; the tab toggle stays visible and accessible.

---

## Phased Delivery

### Phase 1 — UI shell + X mentions (1-2 days)
- Tab toggle in StatsBar
- `mentions-feed.tsx` with platform/time filters  
- `x_mentions_ingestion.py` using search endpoint
- `/api/mentions` backend endpoint
- `is_mention` column + index on `posts` table

### Phase 2 — LinkedIn mentions (1 day, dependent on LinkedIn ingestion setup)
- `linkedin_mentions_ingestion.py`
- Update Stats API to include LinkedIn mention counts
- Update StatsBar `posts_by_platform` to show LinkedIn

### Phase 3 — Polish (0.5 days)
- Badge on @Mentions tab for new-since-last-visit count
- Auto-refresh every 5 minutes while tab is active
- "Mark as seen" state (local storage, not persisted server-side)

---

## Open Questions

1. ~~**X API tier**~~ **RESOLVED**: Search endpoint (`/2/tweets/search/recent`) already works with existing credentials. Confirmed 300 req/15min rate limit. No upgrade needed.

2. **Mention keywords**: Start with `"Gauntlet AI" OR @GauntletAI OR gauntletai`? Any other brand terms or program names we should capture (e.g., specific cohort hashtags)?

3. **Tab placement**: Inside StatsBar (compact) vs. standalone row below StatsBar (more breathing room)? Design call.

4. **LinkedIn search reliability**: The `linkedin-api` keyword search is less battle-tested than the profile-feed approach. Acceptable to launch Phase 1 (X only) and add LinkedIn in Phase 2 after testing?

---

## Success Metrics

- Team checks @Mentions tab at least 3x/week without being prompted
- Catch at least one high-engagement mention per week that would have been missed
- Zero false-positive rate above 5% (mentions that aren't actually about Gauntlet AI)

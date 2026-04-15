"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

type Section = "overview" | "search" | "mentions" | "popular" | "history" | "ingestion" | "accounts";

const sections: { id: Section; label: string; emoji: string }[] = [
  { id: "overview", label: "Overview", emoji: "🗺️" },
  { id: "search", label: "Search Tab", emoji: "🔍" },
  { id: "popular", label: "Popular Tab", emoji: "🔥" },
  { id: "mentions", label: "@Mentions Tab", emoji: "📡" },
  { id: "history", label: "History Tab", emoji: "🕐" },
  { id: "ingestion", label: "Ingestion Pipelines", emoji: "⚙️" },
  { id: "accounts", label: "Platform Accounts", emoji: "🎯" },
];

function Badge({ children, color = "gray" }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    gray: "bg-gray-100 text-gray-700",
    blue: "bg-blue-100 text-blue-700",
    green: "bg-emerald-100 text-emerald-700",
    purple: "bg-purple-100 text-purple-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
  };
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium", colors[color] ?? colors.gray)}>
      {children}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold text-foreground border-b border-border pb-2">{title}</h3>
      {children}
    </div>
  );
}

function DataRow({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
      <span className="text-xs text-muted-foreground w-40 shrink-0 pt-0.5">{label}</span>
      <span className={cn("text-sm text-foreground flex-1", mono && "font-mono text-xs bg-secondary px-2 py-0.5 rounded")}>
        {value}
      </span>
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="bg-gray-950 text-green-400 text-xs rounded-xl p-4 overflow-x-auto font-mono leading-relaxed">
      {children}
    </pre>
  );
}

export default function DocsPage() {
  const [active, setActive] = useState<Section>("overview");

  return (
    <div className="flex gap-8">
      {/* Sidebar */}
      <aside className="w-48 shrink-0 sticky top-24 self-start">
        <nav className="space-y-1">
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => setActive(s.id)}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-left",
                active === s.id
                  ? "bg-accent text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )}
            >
              <span>{s.emoji}</span>
              <span>{s.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-8">

        {/* ── OVERVIEW ── */}
        {active === "overview" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">System Architecture</h1>
              <p className="text-sm text-muted-foreground mt-1">
                How the Marketing Command Center is built and maintained
              </p>
            </div>

            <Section title="Stack">
              <DataRow label="Frontend" value={<span>Next.js 15 (App Router) — deployed on <Badge color="green">Netlify</Badge></span>} />
              <DataRow label="Backend" value={<span>FastAPI (Python) — deployed on <Badge color="purple">Railway</Badge></span>} />
              <DataRow label="Database" value={<span>PostgreSQL 16 + pgvector — hosted on <Badge color="purple">Railway</Badge></span>} />
              <DataRow label="Embeddings" value="text-embedding-3-small via OpenRouter" />
              <DataRow label="Summaries" value="claude-sonnet-4.5 via OpenRouter" />
              <DataRow label="Auth" value="Clerk (Google SSO)" />
            </Section>

            <Section title="Data Sources">
              <DataRow label="X (Twitter)" value="gauntlet_graduates list — tweets from Gauntlet alumni and community" />
              <DataRow label="Slack" value="#ai-first-methodologies, #claude-maxxing, #industry-news" />
            </Section>

            <Section title="Scheduled Jobs">
              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-secondary">
                    <tr>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Job</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Schedule</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">What it does</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    <tr>
                      <td className="px-3 py-2.5 font-medium">MCC Daily Ingestion</td>
                      <td className="px-3 py-2.5 font-mono">0 2 * * * CDT</td>
                      <td className="px-3 py-2.5 text-muted-foreground">Fetches new X tweets + Slack messages, embeds them, inserts into DB</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2.5 font-medium">LinkedIn Mentions Ingestion</td>
                      <td className="px-3 py-2.5 font-mono">0 8 * * * UTC</td>
                      <td className="px-3 py-2.5 text-muted-foreground">Keyword search on LinkedIn, tags posts is_mention=true — via GitHub Actions</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2.5 font-medium">MCC Engagement Recheck</td>
                      <td className="px-3 py-2.5 font-mono">0 */4 * * * CDT</td>
                      <td className="px-3 py-2.5 text-muted-foreground">Re-fetches metrics for posts from last 72h, flags newly popular ones</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Section>

            <Section title="Repository Structure">
              <CodeBlock>{`mcc/
├── backend/
│   ├── main.py                    # FastAPI app — all API endpoints
│   ├── ingestion/
│   │   ├── x_ingestion.py         # X (Twitter) pipeline
│   │   ├── slack_ingestion.py     # Slack pipeline
│   │   └── engagement_recheck.py  # 4h popularity recheck cron
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   └── 002_popular_posts.sql
│   └── scripts/
│       └── reindex_embeddings.py  # One-off reindex utility
└── frontend/
    ├── app/
    │   ├── page.tsx               # Search + Popular tabs
    │   ├── history/page.tsx       # Query history
    │   └── docs/page.tsx          # This page
    ├── components/
    │   ├── stats-bar.tsx          # Live stats bar
    │   ├── result-card.tsx        # Shared post card
    │   └── popular-feed.tsx       # Popular posts feed
    └── lib/
        └── api.ts                 # All API calls + types`}
              </CodeBlock>
            </Section>
          </div>
        )}

        {/* ── SEARCH TAB ── */}
        {active === "search" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Search Tab</h1>
              <p className="text-sm text-muted-foreground mt-1">Semantic search across all ingested X and Slack content</p>
            </div>

            <Section title="How it works">
              <div className="space-y-3 text-sm text-foreground leading-relaxed">
                <p>The search tab uses <strong>semantic (vector) search</strong> — your query is embedded with <code className="bg-secondary px-1 rounded text-xs">text-embedding-3-small</code> and compared against all stored post embeddings using cosine similarity via pgvector.</p>
                <p>Results below a <strong>0.3 similarity threshold</strong> are dropped. The ranking blends similarity (70%) with recency (30%) unless a time filter is active, in which case it ranks by similarity only.</p>
                <p>After retrieval, an AI summary is generated by Claude using the top 10 results as grounded context.</p>
              </div>
            </Section>

            <Section title="Query pipeline">
              <DataRow label="1. Parse query" value="Extract temporal expressions (last week, March 2025, Q1 2026) and platform hints (on Slack, from X)" />
              <DataRow label="2. Embed" value="Clean query → text-embedding-3-small → 1536-dim vector" />
              <DataRow label="3. Vector search" value="pgvector HNSW index, cosine similarity, fetch up to 100 candidates" />
              <DataRow label="4. Filter" value="Drop results below 0.3 similarity; apply platform/date filters" />
              <DataRow label="5. Rank" value="Blend similarity × 0.7 + recency × 0.3 (skipped when time filter active)" />
              <DataRow label="6. Summarize" value="Top 10 results → Claude → 2-3 sentence grounded summary" />
              <DataRow label="7. Save" value="Query + results snapshot saved to query_history table" />
            </Section>

            <Section title="API endpoint">
              <DataRow label="Route" value="POST /api/query/semantic-with-summary" mono />
              <DataRow label="Payload" value='{ "query": "string", "platform"?: "x|slack", "days"?: number }' mono />
              <DataRow label="Returns" value='{ posts, summary, count, latency_ms }' mono />
            </Section>

            <Section title="Database tables used">
              <DataRow label="Read" value={<><Badge color="blue">posts</Badge> — full-text + vector search</>} />
              <DataRow label="Write" value={<><Badge color="blue">query_history</Badge> — every query + snapshot saved</>} />
            </Section>

            <Section title="Frontend">
              <DataRow label="Page" value="app/page.tsx (Search tab)" mono />
              <DataRow label="Components" value="ResultCard, SummaryBox, Skeleton loaders" />
              <DataRow label="State" value="Query text, loading, error, QueryResult (posts + summary + count)" />
            </Section>
          </div>
        )}

        {/* ── MENTIONS TAB ── */}
        {active === "mentions" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">@Mentions Tab</h1>
              <p className="text-sm text-muted-foreground mt-1">Brand mention monitoring across X and LinkedIn</p>
            </div>

            <Section title="How it works">
              <div className="space-y-3 text-sm text-foreground leading-relaxed">
                <p>The @Mentions tab surfaces all posts tagged <code className="bg-secondary px-1 rounded text-xs">is_mention = TRUE</code> in the database — ingested via keyword search on X and LinkedIn. No manual searching needed.</p>
                <p>X mentions are found via the search endpoint (<code className="bg-secondary px-1 rounded text-xs">GET /2/tweets/search/recent</code>) with the query <code className="bg-secondary px-1 rounded text-xs">"Gauntlet AI" OR @GauntletAI OR gauntletai -is:retweet lang:en</code>. LinkedIn mentions are found by keyword search using the unofficial Voyager API.</p>
                <p>All mention posts are also searchable in the Search tab — the <code className="bg-secondary px-1 rounded text-xs">is_mention</code> flag is additive, not exclusive.</p>
              </div>
            </Section>

            <Section title="Ingestion sources">
              <DataRow label="X" value={<span>Search: <code className="bg-secondary px-1 rounded text-xs">"Gauntlet AI" OR @GauntletAI OR gauntletai -is:retweet lang:en</code> · runs daily</span>} />
              <DataRow label="LinkedIn" value='Keywords: Gauntlet AI, gauntletai, Gauntlet AI program, GauntletAI · runs daily at 08:00 UTC' />
            </Section>

            <Section title="API endpoint">
              <DataRow label="Route" value="GET /api/mentions" mono />
              <DataRow label="Params" value="platform (x|linkedin|all), days (default 7), page, page_size" mono />
              <DataRow label="Returns" value="{ mentions[], total, page, page_size, by_platform: {x, linkedin} }" mono />
              <DataRow label="Stats" value="GET /api/stats → .mentions.total + .last_24h + .x + .linkedin" mono />
            </Section>

            <Section title="Database">
              <DataRow label="Column" value={<span><code className="bg-secondary px-1 rounded text-xs">is_mention BOOLEAN DEFAULT FALSE</code> on the <Badge color="blue">posts</Badge> table</span>} />
              <DataRow label="Index" value="posts_is_mention_idx ON (is_mention, published_at DESC)" mono />
              <DataRow label="Set by" value="linkedin_mentions_ingestion.py at insert time" />
            </Section>

            <Section title="Frontend">
              <DataRow label="Page" value="app/page.tsx (@Mentions tab)" mono />
              <DataRow label="Component" value="components/mentions-feed.tsx" mono />
              <DataRow label="Filters" value="Platform (All/X/LinkedIn) + time range (24h/7d/30d)" />
              <DataRow label="Badge" value="Tab shows count of mentions from last 24h; clears when tab is visited" />
            </Section>
          </div>
        )}

        {/* ── POPULAR TAB ── */}
        {active === "popular" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Popular Tab</h1>
              <p className="text-sm text-muted-foreground mt-1">Auto-curated feed of high-engagement original posts from X and Slack</p>
            </div>

            <Section title="How it works">
              <div className="space-y-3 text-sm text-foreground leading-relaxed">
                <p>Posts are flagged as popular when any single engagement metric crosses a threshold. Only <strong>original posts</strong> qualify — retweets, quote tweets, replies, and posts by excluded authors are skipped.</p>
                <p>Detection runs at two points: immediately at ingestion time, and again every 4 hours via the engagement recheck cron (which re-fetches live metrics for all posts ingested in the last 72h).</p>
                <p>When a post is flagged, a 🔥 alert fires to <strong>#bullseye_comms</strong> with the post content, metrics, and permalink. Alerts are deduplicated — one alert per post, ever.</p>
              </div>
            </Section>

            <Section title="Thresholds">
              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-secondary">
                    <tr>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Platform</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Metric</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Threshold</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Env var</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {[
                      ["X", "Views (impressions)", "> 50,000", "POPULAR_THRESHOLD_X_VIEWS"],
                      ["X", "Likes", "> 300", "POPULAR_THRESHOLD_X_LIKES"],
                      ["X", "Reposts", "> 50", "POPULAR_THRESHOLD_X_REPOSTS"],
                      ["X", "Replies", "> 50", "POPULAR_THRESHOLD_X_REPLIES"],
                      ["Slack", "Thread replies", "> 20", "POPULAR_THRESHOLD_SLACK_REPLIES"],
                    ].map(([platform, metric, threshold, env]) => (
                      <tr key={env}>
                        <td className="px-3 py-2.5"><Badge color={platform === "X" ? "gray" : "purple"}>{platform}</Badge></td>
                        <td className="px-3 py-2.5">{metric}</td>
                        <td className="px-3 py-2.5 font-medium">{threshold}</td>
                        <td className="px-3 py-2.5 font-mono text-muted-foreground">{env}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground mt-2">All thresholds are configurable via env vars — no code deploy needed to tune them.</p>
            </Section>

            <Section title="Exclusions">
              <DataRow label="Excluded authors" value={<><code className="bg-secondary px-1 rounded text-xs">@jason</code> — configured via <code className="bg-secondary px-1 rounded text-xs">POPULAR_EXCLUDED_AUTHORS</code> env var (comma-separated)</>} />
              <DataRow label="Post types excluded" value="Retweets (RT @…), quote tweets, replies to other posts" />
            </Section>

            <Section title="Detection flow">
              <DataRow label="At ingestion" value="x_ingestion.py and slack_ingestion.py check thresholds immediately after INSERT RETURNING id" />
              <DataRow label="Recheck cron" value="Every 4h — re-fetches live X metrics (batch of 100/request) and Slack reply counts for posts from last 72h" />
              <DataRow label="Deduplication" value="UNIQUE(post_id) on popular_posts — first threshold crossed wins, no double-flagging" />
              <DataRow label="Alert channel" value="#bullseye_comms (SLACK_ALERT_CHANNEL env var)" />
            </Section>

            <Section title="API endpoint">
              <DataRow label="Route" value="GET /api/popular" mono />
              <DataRow label="Params" value="platform (x|slack|all), days (default 30), page, page_size" mono />
              <DataRow label="Returns" value="{ posts[], total, page, page_size, by_platform: {x, slack} }" mono />
              <DataRow label="Stats" value="GET /api/stats → .popular.total + .popular.last_24h" mono />
            </Section>

            <Section title="Database">
              <DataRow label="Migration" value="002_popular_posts.sql" mono />
              <DataRow label="Table" value={<><Badge color="amber">popular_posts</Badge> — id, post_id (FK), flagged_at, triggered_by, metric_value, alerted, alerted_at</>} />
              <DataRow label="Index" value="idx_popular_posts_flagged ON flagged_at DESC" mono />
              <DataRow label="Retention" value="Permanent — popular posts are never deleted" />
            </Section>

            <Section title="Frontend">
              <DataRow label="Page" value="app/page.tsx (Popular tab)" mono />
              <DataRow label="Component" value="components/popular-feed.tsx" mono />
              <DataRow label="Filters" value="Platform (All/X/Slack) + time range (7d/30d/All time)" />
              <DataRow label="Badge" value="Tab shows count of posts flagged in last 24h; clears when tab is visited" />
            </Section>
          </div>
        )}

        {/* ── HISTORY TAB ── */}
        {active === "history" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">History Tab</h1>
              <p className="text-sm text-muted-foreground mt-1">Persistent log of every search query with full result snapshots</p>
            </div>

            <Section title="How it works">
              <div className="text-sm text-foreground leading-relaxed space-y-3">
                <p>Every query run through the Search tab is automatically saved — including the query text, which engine was used, the AI summary, and a snapshot of the top 5 results at query time.</p>
                <p>The snapshot is frozen at query time, so it reflects what was in the database when the search ran — useful for auditing how answers have changed over time.</p>
              </div>
            </Section>

            <Section title="API endpoints">
              <DataRow label="List" value="GET /api/query/history?page=1&page_size=20" mono />
              <DataRow label="Detail" value="GET /api/query/history/{id}" mono />
              <DataRow label="Export" value="GET /api/query/history/{id}/export → Markdown download" mono />
            </Section>

            <Section title="Database">
              <DataRow label="Table" value={<><Badge color="blue">query_history</Badge> — id, user_id, query_text, filters, engine, summary, results_snapshot (JSONB), result_count, latency_ms, created_at</>} />
              <DataRow label="Written by" value="POST /api/query/semantic-with-summary after every search" />
              <DataRow label="Snapshot size" value="Top 5 results stored as JSONB (not the full result set)" />
            </Section>

            <Section title="Frontend">
              <DataRow label="Page" value="app/history/page.tsx" mono />
              <DataRow label="Pagination" value="20 queries per page, server-side" />
              <DataRow label="Expand" value="Click any row to load full detail + result snapshot" />
              <DataRow label="Export" value="Downloads .md file with query, summary, and top results" />
            </Section>
          </div>
        )}

        {/* ── INGESTION PIPELINES ── */}
        {active === "ingestion" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Ingestion Pipelines</h1>
              <p className="text-sm text-muted-foreground mt-1">How data gets into the database from each platform</p>
            </div>

            <Section title="X (Twitter) — x_ingestion.py">
              <DataRow label="Source" value="gauntlet_graduates X list" />
              <DataRow label="API endpoint" value="GET /2/lists/:id/tweets" mono />
              <DataRow label="Fields fetched" value="created_at, public_metrics (views/likes/reposts/replies), entities (links), author_id, referenced_tweets" />
              <DataRow label="Pagination" value="100 tweets/page, up to 50 pages per run; stops when reaching already-seen tweet IDs" />
              <DataRow label="Deduplication" value="ON CONFLICT (external_id) DO NOTHING — tweet ID is the unique key" />
              <DataRow label="Embeddings" value="Generated in batches of 50 via text-embedding-3-small" />
              <DataRow label="Checkpoint" value="ingestion_checkpoints table — stores last seen tweet ID (since_id)" />
              <DataRow label="Popularity check" value="After each INSERT RETURNING id — checks thresholds, skips retweets/quotes/replies and excluded authors" />
              <DataRow label="Dead letter" value="Failed inserts logged to backend/logs/dead_letter_x.json" />
              <DataRow label="Failure alerts" value="Slack alert to #bullseye_comms after 2 consecutive failures" />
              <DataRow label="Schedule" value="Daily at 2:00 AM CDT" />
            </Section>

            <Section title="Slack — slack_ingestion.py">
              <DataRow label="Source" value="#ai-first-methodologies, #claude-maxxing, #industry-news" />
              <DataRow label="API endpoint" value="conversations.history + conversations.replies" mono />
              <DataRow label="Fields fetched" value="ts, text, user, reply_count, thread_ts" />
              <DataRow label="Thread handling" value="When a message has reply_count > 0 and is a thread root, all replies are fetched and ingested as individual posts" />
              <DataRow label="Deduplication" value="ON CONFLICT (external_id) DO NOTHING — Slack message ts is the unique key" />
              <DataRow label="Embeddings" value="Generated in batches of 50 via text-embedding-3-small" />
              <DataRow label="Checkpoint" value="ingestion_checkpoints table — stores last seen message ts per channel (shared checkpoint)" />
              <DataRow label="Popularity check" value="After each INSERT RETURNING id — checks reply_count against threshold (> 20)" />
              <DataRow label="Author resolution" value="Slack user IDs (U…) resolved to display names via backend/slack_users.json" />
              <DataRow label="Dead letter" value="Failed inserts logged to backend/logs/dead_letter.json" />
              <DataRow label="Schedule" value="Daily at 2:00 AM CDT" />
            </Section>

            <Section title="LinkedIn — linkedin_mentions_ingestion.py">
              <DataRow label="Source" value="Keyword search for brand mentions" />
              <DataRow label="Keywords" value='Gauntlet AI, gauntletai, Gauntlet AI program, GauntletAI (env: LINKEDIN_MENTION_KEYWORDS)' />
              <DataRow label="Auth" value="LinkedIn session cookies (Google OAuth account — no password). Cookies stored at ~/.openclaw/secrets/linkedin_cookies.json and expire ~every 2 weeks" />
              <DataRow label="API" value="linkedin-api (unofficial Voyager API wrapper)" />
              <DataRow label="Deduplication" value="ON CONFLICT (external_id) DO NOTHING — URN-based external_id" />
              <DataRow label="Tags posts" value="is_mention = TRUE, platform = 'linkedin'" />
              <DataRow label="Embeddings" value="Batches of 50 via text-embedding-3-small" />
              <DataRow label="Popularity check" value="Checks POPULAR_THRESHOLD_LI_LIKES (500), POPULAR_THRESHOLD_LI_REPOSTS (100), POPULAR_THRESHOLD_LI_REPLIES (50)" />
              <DataRow label="Schedule" value="Daily at 08:00 UTC via GitHub Actions (cron-ingestion.yml)" />
              <DataRow label="Cookie refresh" value={<span>When expired: log into LinkedIn in Chrome browser profile, then run the cookie extraction command in the script header. Update <code className="bg-secondary px-1 rounded text-xs">LINKEDIN_COOKIES_JSON</code> GitHub secret too.</span>} />
            </Section>

            <Section title="Engagement Recheck — engagement_recheck.py">
              <DataRow label="Purpose" value="Catch posts that went viral after initial ingestion — metrics grow over time" />
              <DataRow label="Window" value="Posts ingested in last 72h not yet in popular_posts (configurable via RECHECK_WINDOW_HOURS)" />
              <DataRow label="X recheck" value="Batch-fetches live metrics from GET /2/tweets?ids=… (100/request) with public_metrics + referenced_tweets" />
              <DataRow label="Slack recheck" value="Re-fetches reply count via conversations.replies with limit=1 per thread root" />
              <DataRow label="Filtering" value="Same rules as ingestion — skips retweets/quotes/replies and excluded authors" />
              <DataRow label="Deduplication" value="UNIQUE(post_id) on popular_posts — safe to run repeatedly" />
              <DataRow label="Schedule" value="Every 4 hours (0 */4 * * * CDT)" />
            </Section>

            <Section title="Database migrations">
              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-secondary">
                    <tr>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">File</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">What it created</th>
                      <th className="text-left px-3 py-2 text-muted-foreground font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    <tr>
                      <td className="px-3 py-2.5 font-mono">001_initial_schema.sql</td>
                      <td className="px-3 py-2.5 text-muted-foreground">posts, project_updates, ingestion_checkpoints, query_history + all indexes + tsvector trigger</td>
                      <td className="px-3 py-2.5 text-muted-foreground">2026-03-20</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2.5 font-mono">002_popular_posts.sql</td>
                      <td className="px-3 py-2.5 text-muted-foreground">popular_posts table, idx_popular_posts_flagged, views column on posts</td>
                      <td className="px-3 py-2.5 text-muted-foreground">2026-04-15</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground mt-2">Migrations are run manually against the Railway Postgres instance via <code className="bg-secondary px-1 rounded">psql $DATABASE_URL -f backend/migrations/&lt;file&gt;.sql</code></p>
            </Section>
          </div>
        )}

        {/* ── PLATFORM ACCOUNTS ── */}
        {active === "accounts" && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Platform Accounts</h1>
              <p className="text-sm text-muted-foreground mt-1">Bullseye's accounts and credentials across each platform</p>
            </div>

            <Section title="X (Twitter)">
              <DataRow label="Account" value={<a href="https://x.com/bullseye_g4" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">@bullseye_g4</a>} />
              <DataRow label="User ID" value="2031768916515835904" mono />
              <DataRow label="Auth" value="OAuth 1.0a — credentials in ~/.openclaw/secrets/x_oauth1.json" />
              <DataRow label="OAuth 2.0" value="~/.openclaw/secrets/x_oauth2.json" mono />
              <DataRow label="API tier" value="Free (75 req/15min user endpoints, 300 req/15min list management)" />
              <DataRow label="Data source" value={<span>gauntlet_graduates list — env var <code className="bg-secondary px-1 rounded text-xs">X_LIST_ID</code></span>} />
              <DataRow label="Also tracking" value={<a href="https://x.com/gauntletai" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">@gauntletai</a>} />
            </Section>

            <Section title="Slack">
              <DataRow label="Bot name" value="Bullseye" />
              <DataRow label="Auth" value={<span>Bot token — env var <code className="bg-secondary px-1 rounded text-xs">SLACK_BOT_TOKEN</code></span>} />
              <DataRow label="Monitored channels" value="#ai-first-methodologies, #claude-maxxing, #industry-news" />
              <DataRow label="Alert channel" value={<span>#bullseye_comms — env var <code className="bg-secondary px-1 rounded text-xs">SLACK_ALERT_CHANNEL</code></span>} />
              <DataRow label="Channel IDs env var" value="SLACK_CHANNEL_IDS" mono />
            </Section>

            <Section title="LinkedIn">
              <DataRow label="Account" value={<a href="https://linkedin.com/in/bullseye-undefined-290927403/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">bullseye-undefined-290927403</a>} />
              <DataRow label="Email" value="bullseye.gauntlet@gmail.com (Google OAuth — no password)" />
              <DataRow label="Auth" value="Session cookies — stored at ~/.openclaw/secrets/linkedin_cookies.json" />
              <DataRow label="Cookie expiry" value="~2 weeks — refresh manually when expired (see ingestion script header for instructions)" />
              <DataRow label="GitHub secret" value="LINKEDIN_COOKIES_JSON" mono />
              <DataRow label="Keywords tracked" value="Gauntlet AI, gauntletai, Gauntlet AI program, GauntletAI" />
            </Section>

            <Section title="Google / Gmail">
              <DataRow label="Account" value="bullseye.gauntlet@gmail.com" />
              <DataRow label="Auth" value="OAuth 2.0 via gog CLI" />
              <DataRow label="Token location" value="Managed by gog CLI (run gog auth list to check status)" mono />
            </Section>

            <Section title="Railway (Backend hosting)">
              <DataRow label="Project" value="c980a5a3-8020-4a5c-9378-0e100e6c53ec" mono />
              <DataRow label="Backend service" value="921d64e6-a106-4593-b46d-220e21c7dc99" mono />
              <DataRow label="Environment" value="6e686ddb-1999-4980-b637-a5bbb6a5e18d" mono />
              <DataRow label="Deploy trigger" value="Push to main branch → GitHub Actions → railway up" />
            </Section>

            <Section title="Netlify (Frontend hosting)">
              <DataRow label="Site" value={<a href="https://marketing-command-center-55ff2635.netlify.app" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">marketing-command-center-55ff2635.netlify.app</a>} />
              <DataRow label="Deploy trigger" value="Push to main branch → GitHub Actions → Netlify deploy" />
            </Section>

            <Section title="OpenRouter">
              <DataRow label="Purpose" value="Embeddings (text-embedding-3-small) + summaries (claude-sonnet-4.5)" />
              <DataRow label="Auth" value={<span>env var <code className="bg-secondary px-1 rounded text-xs">OPENROUTER_API_KEY</code></span>} />
            </Section>
          </div>
        )}

      </div>
    </div>
  );
}

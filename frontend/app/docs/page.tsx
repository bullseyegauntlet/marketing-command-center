"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

type Section = "overview" | "search" | "mentions" | "popular" | "history" | "ingestion" | "accounts";

const sections: { id: Section; label: string; emoji: string }[] = [
  { id: "overview", label: "Overview", emoji: "🗺️" },
  { id: "search", label: "Search", emoji: "🔍" },
  { id: "mentions", label: "@Mentions", emoji: "📡" },
  { id: "popular", label: "Popular", emoji: "🔥" },
  { id: "history", label: "History", emoji: "🕐" },
  { id: "ingestion", label: "Ingestion", emoji: "⚙️" },
  { id: "accounts", label: "Accounts", emoji: "🎯" },
];

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-border/50 last:border-0">
      <span className="text-xs text-muted-foreground w-36 shrink-0 pt-0.5">{label}</span>
      <span className="text-sm text-foreground flex-1">{value}</span>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-white p-5 space-y-1">
      <h3 className="text-sm font-semibold text-foreground mb-3">{title}</h3>
      {children}
    </div>
  );
}

export default function DocsPage() {
  const [active, setActive] = useState<Section>("overview");

  return (
    <div className="flex gap-8">
      {/* Sidebar */}
      <aside className="w-44 shrink-0 sticky top-24 self-start">
        <nav className="space-y-0.5">
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
      <div className="flex-1 min-w-0 space-y-5">

        {/* ── OVERVIEW ── */}
        {active === "overview" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Marketing Command Center</h1>
              <p className="text-sm text-muted-foreground mt-1">A real-time intelligence dashboard for Gauntlet AI marketing & sales</p>
            </div>
            <Card title="What it does">
              <Row label="Search" value="Semantic search across all ingested Slack and X content with AI-generated summaries" />
              <Row label="@Mentions" value="Auto-ingested brand mentions from X and LinkedIn — no manual searching required" />
              <Row label="🔥 Popular" value="Automatically flags high-engagement original posts and alerts #bullseye_comms" />
              <Row label="History" value="Every search query is saved with its results for future reference" />
            </Card>
            <Card title="Stack">
              <Row label="Frontend" value="Next.js — deployed on Netlify" />
              <Row label="Backend" value="FastAPI (Python) — deployed on Railway" />
              <Row label="Database" value="PostgreSQL + pgvector on Railway" />
              <Row label="AI" value="Embeddings + summaries via OpenRouter (Claude + text-embedding-3-small)" />
              <Row label="Auth" value="Clerk (Google SSO)" />
            </Card>
            <Card title="Data sources">
              <Row label="X" value="Gauntlet graduates list + brand mention search" />
              <Row label="Slack" value="#ai-first-methodologies, #claude-maxxing, #industry-news" />
              <Row label="LinkedIn" value="Keyword mention search (Gauntlet AI, gauntletai, etc.)" />
            </Card>
            <Card title="Scheduled jobs">
              <Row label="Daily at 2am CDT" value="Fetch new X tweets and Slack messages, generate embeddings, insert into DB" />
              <Row label="Daily at 8am UTC" value="LinkedIn keyword search for brand mentions" />
              <Row label="Every 4 hours" value="Re-check engagement metrics on recent posts, flag newly popular content" />
            </Card>
          </div>
        )}

        {/* ── SEARCH ── */}
        {active === "search" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Search</h1>
              <p className="text-sm text-muted-foreground mt-1">Ask anything about your Slack channels and X posts</p>
            </div>
            <Card title="How it works">
              <Row label="Query" value="Natural language — ask questions, use platform names, reference time ranges" />
              <Row label="Search type" value="Semantic (vector similarity) — finds conceptually related content, not just keyword matches" />
              <Row label="Summary" value="Claude generates a 2–3 sentence grounded answer from the top results" />
              <Row label="History" value="Every search is saved and surfaced as recent searches below the search bar" />
            </Card>
            <Card title="Tips">
              <Row label="Platform filter" value='Say "on Slack" or "from X" to restrict results to one platform' />
              <Row label="Time filter" value='Say "last week", "in March 2025", or "Q1 2026" to scope by date' />
              <Row label="Recent searches" value="Shown below the search bar — click any to re-run it instantly" />
            </Card>
          </div>
        )}

        {/* ── MENTIONS ── */}
        {active === "mentions" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">@Mentions</h1>
              <p className="text-sm text-muted-foreground mt-1">People talking about Gauntlet AI across X and LinkedIn</p>
            </div>
            <Card title="How it works">
              <Row label="X" value='Brand mention search runs daily — finds posts matching "Gauntlet AI", @GauntletAI, or gauntletai. Retweets excluded.' />
              <Row label="LinkedIn" value="Keyword search runs daily — same brand terms. Results vary by session freshness." />
              <Row label="Filters" value="Filter by platform (All / X / LinkedIn) and time range (24h / 7d / 30d)" />
            </Card>
            <Card title="Badge">
              <Row label="Tab badge" value="Shows count of new mentions in the last 24 hours. Clears when you visit the tab." />
            </Card>
          </div>
        )}

        {/* ── POPULAR ── */}
        {active === "popular" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">🔥 Popular</h1>
              <p className="text-sm text-muted-foreground mt-1">High-engagement original posts, automatically flagged</p>
            </div>
            <Card title="How it works">
              <Row label="Detection" value="Posts are checked at ingestion and again every 4 hours. Any post that crosses a threshold is flagged permanently." />
              <Row label="Alerts" value="A Slack alert fires to #bullseye_comms the first time a post is flagged — one alert per post, ever." />
              <Row label="Originals only" value="Retweets, quote tweets, and replies are excluded. Only original posts qualify." />
              <Row label="Exclusions" value="@jason is excluded from flagging." />
            </Card>
            <Card title="Thresholds">
              <Row label="X views" value="> 50,000" />
              <Row label="X likes" value="> 300" />
              <Row label="X reposts" value="> 50" />
              <Row label="X replies" value="> 50" />
              <Row label="Slack thread replies" value="> 20" />
            </Card>
            <Card title="Filters">
              <Row label="Platform" value="All / X / Slack" />
              <Row label="Time range" value="7 days / 30 days / All time" />
              <Row label="Sort" value="Most recently flagged first" />
            </Card>
          </div>
        )}

        {/* ── HISTORY ── */}
        {active === "history" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">History</h1>
              <p className="text-sm text-muted-foreground mt-1">Your saved search queries</p>
            </div>
            <Card title="How it works">
              <Row label="Auto-saved" value="Every search run in the Search tab is automatically saved — query text, engine, result count, AI summary, and a snapshot of the top results." />
              <Row label="Access" value="Recent searches appear below the search bar in the Search tab. Click any to re-run it instantly." />
              <Row label="Snapshots" value="Results are frozen at query time — useful for seeing how answers change as new content is ingested." />
            </Card>
          </div>
        )}

        {/* ── INGESTION ── */}
        {active === "ingestion" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Ingestion</h1>
              <p className="text-sm text-muted-foreground mt-1">How content gets into the database</p>
            </div>
            <Card title="X (Twitter)">
              <Row label="Source" value="Gauntlet graduates list — fetches new tweets since last run" />
              <Row label="Schedule" value="Daily at 2am CDT" />
              <Row label="Also" value="Brand mention search runs on the same schedule, tags matching posts as mentions" />
            </Card>
            <Card title="Slack">
              <Row label="Source" value="#ai-first-methodologies, #claude-maxxing, #industry-news" />
              <Row label="Threads" value="Full thread replies are fetched and ingested as individual posts" />
              <Row label="Schedule" value="Daily at 2am CDT" />
            </Card>
            <Card title="LinkedIn">
              <Row label="Source" value="Keyword search — Gauntlet AI, gauntletai, and related terms" />
              <Row label="Schedule" value="Daily at 8am UTC via GitHub Actions" />
              <Row label="Note" value="Uses session cookies that expire every ~2 weeks. Refresh when ingestion starts returning zero results." />
            </Card>
            <Card title="Engagement recheck">
              <Row label="What" value="Re-fetches current metrics (views, likes, reposts, replies) for posts from the last 72 hours" />
              <Row label="Why" value="Posts can go viral hours after initial ingestion — this catches them" />
              <Row label="Schedule" value="Every 4 hours" />
            </Card>
          </div>
        )}

        {/* ── ACCOUNTS ── */}
        {active === "accounts" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Platform Accounts</h1>
              <p className="text-sm text-muted-foreground mt-1">Bullseye's accounts across each platform</p>
            </div>
            <Card title="X (Twitter)">
              <Row label="Account" value="@bullseye_g4" />
              <Row label="Also tracking" value="@gauntletai" />
            </Card>
            <Card title="Slack">
              <Row label="Bot name" value="Bullseye" />
              <Row label="Alert channel" value="#bullseye_comms" />
            </Card>
            <Card title="LinkedIn">
              <Row label="Account" value="Bullseye (bullseye.gauntlet@gmail.com)" />
            </Card>
            <Card title="Google / Gmail">
              <Row label="Account" value="bullseye.gauntlet@gmail.com" />
            </Card>
          </div>
        )}

      </div>
    </div>
  );
}

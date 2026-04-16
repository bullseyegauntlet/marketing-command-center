"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

type Section = "overview" | "search" | "mentions" | "popular" | "ingestion" | "accounts";

const sections: { id: Section; label: string; emoji: string }[] = [
  { id: "overview", label: "Overview", emoji: "🗺️" },
  { id: "search", label: "Search", emoji: "🔍" },
  { id: "mentions", label: "@Mentions", emoji: "📡" },
  { id: "popular", label: "Popular", emoji: "🔥" },
  { id: "ingestion", label: "Ingestion", emoji: "⚙️" },
  { id: "accounts", label: "Accounts", emoji: "🎯" },
];

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-[#1e1e1e] last:border-0">
      <span className="text-xs text-[rgba(255,255,255,0.35)] w-36 shrink-0 pt-0.5">{label}</span>
      <span className="text-sm text-[rgba(255,255,255,0.7)] flex-1">{value}</span>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-[#2B2B2B] bg-[#121212] p-5 space-y-1">
      <h3 className="text-sm font-semibold text-[rgba(255,255,255,0.85)] mb-3">{title}</h3>
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
                  ? "bg-[rgba(192,158,90,0.1)] text-[#C09E5A] font-medium"
                  : "text-[rgba(255,255,255,0.35)] hover:text-[rgba(255,255,255,0.8)] hover:bg-[rgba(255,255,255,0.04)]"
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
              <h1 className="text-2xl font-bold text-white">Marketing Command Center</h1>
              <p className="text-sm text-[rgba(255,255,255,0.4)] mt-1">A real-time intelligence dashboard for Gauntlet AI marketing & sales</p>
            </div>
            <Card title="What it does">
              <Row label="Search" value="Semantic search across all ingested Slack, X, and Reddit content with AI-generated summaries" />
              <Row label="@Mentions" value="Auto-ingested brand mentions from X, Reddit, and LinkedIn — no manual searching required" />
              <Row label="🔥 Popular" value="Automatically flags high-engagement original posts and alerts #bullseye_comms" />

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
              <Row label="Reddit" value='Keyword search + r/gauntletai + related subreddits (ML, cs careers, etc.)' />
              <Row label="LinkedIn" value="Keyword mention search (Gauntlet AI, gauntletai, etc.)" />
            </Card>
            <Card title="Scheduled jobs">
              <Row label="Daily at 2am CDT" value="Fetch new X tweets, Slack messages, and Reddit posts — generate embeddings, insert into DB" />
              <Row label="Daily at 8am UTC" value="LinkedIn keyword search for brand mentions" />
              <Row label="Every 4 hours" value="Re-check engagement metrics on recent posts, flag newly popular content" />
            </Card>
          </div>
        )}

        {/* ── SEARCH ── */}
        {active === "search" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold text-white">Search</h1>
              <p className="text-sm text-[rgba(255,255,255,0.4)] mt-1">Ask anything about your Slack channels, X posts, and Reddit threads</p>
            </div>
            <Card title="How it works">
              <Row label="Query" value="Natural language — ask questions, use platform names, reference time ranges" />
              <Row label="Search type" value="Semantic (vector similarity) — finds conceptually related content, not just keyword matches" />
              <Row label="Summary" value="Claude generates a 2–3 sentence grounded answer from the top results" />
              <Row label="History" value="Every search is saved and surfaced as recent searches below the search bar" />
            </Card>

          </div>
        )}

        {/* ── MENTIONS ── */}
        {active === "mentions" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold text-white">@Mentions</h1>
              <p className="text-sm text-[rgba(255,255,255,0.4)] mt-1">People talking about Gauntlet AI across X, Reddit, and LinkedIn</p>
            </div>
            <Card title="How it works">
              <Row label="X" value='Brand mention search runs daily — finds posts matching "Gauntlet AI", @GauntletAI, or gauntletai. Retweets excluded.' />
              <Row label="Reddit" value='Keyword search + r/gauntletai + related subreddits. Runs daily. No OAuth needed.' />
              <Row label="LinkedIn" value="Keyword search runs daily — same brand terms. Results vary by session freshness." />
              <Row label="Filters" value="Filter by platform (All / X / Reddit / LinkedIn) and time range (24h / 7d / 30d)" />
            </Card>

          </div>
        )}

        {/* ── POPULAR ── */}
        {active === "popular" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold text-white">🔥 Popular</h1>
              <p className="text-sm text-[rgba(255,255,255,0.4)] mt-1">High-engagement original posts, automatically flagged</p>
            </div>
            <Card title="How it works">
              <Row label="Detection" value="Posts are checked at ingestion and again every 4 hours. Any post that crosses a threshold is flagged permanently." />
              <Row label="Alerts" value="A Slack alert fires to #bullseye_comms the first time a post is flagged — one alert per post, ever." />
              <Row label="Originals only" value="On X: retweets, quote tweets, and replies are excluded. Only original authored posts qualify." />
              <Row label="Exclusions" value="@jason, @eriktorenberg, and @austen are excluded from flagging." />
            </Card>
            <Card title="Thresholds">
              <Row label="X views" value="> 50,000" />
              <Row label="X likes" value="> 500" />
              <Row label="X reposts" value="> 100" />
              <Row label="X replies" value="> 100" />
              <Row label="Slack thread replies" value="> 20" />
              <Row label="Reddit upvotes" value="> 100" />
              <Row label="Reddit comments" value="> 50" />
              <Row label="LinkedIn likes" value="> 500" />
              <Row label="LinkedIn reposts" value="> 100" />
              <Row label="LinkedIn replies" value="> 50" />
            </Card>
            <Card title="Filters">
              <Row label="Platform" value="All / X / Slack / Reddit" />
              <Row label="Time range" value="7 days / 30 days / All time" />
              <Row label="Sort" value="Most recently flagged first" />
            </Card>
          </div>
        )}

        {/* ── INGESTION ── */}
        {active === "ingestion" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold text-white">Ingestion</h1>
              <p className="text-sm text-[rgba(255,255,255,0.4)] mt-1">How content gets into the database</p>
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
            <Card title="Reddit">
              <Row label="Source" value='Keyword search ("Gauntlet AI", gauntletai, etc.) + r/gauntletai + related subreddits (r/MachineLearning, r/cscareerquestions, r/learnmachinelearning)' />
              <Row label="Schedule" value="Daily at 2am CDT (runs alongside X and Slack)" />
              <Row label="Auth" value="Public API — no OAuth required for read-only access. Add REDDIT_CLIENT_ID/SECRET to .env for higher rate limits." />
            </Card>
            <Card title="LinkedIn">
              <Row label="Source" value="Keyword search — Gauntlet AI, gauntletai, and related terms" />
              <Row label="Schedule" value="Daily at 8am UTC via GitHub Actions" />
              <Row label="Note" value="Uses session cookies that expire every ~2 weeks. Refresh when ingestion starts returning zero results." />
            </Card>
            <Card title="Engagement recheck">
              <Row label="What" value="Re-fetches current metrics for X, Slack, and Reddit posts from the last 72 hours" />
              <Row label="Why" value="Posts can go viral hours after initial ingestion — this catches them" />
              <Row label="Schedule" value="Every 4 hours" />
            </Card>
          </div>
        )}

        {/* ── ACCOUNTS ── */}
        {active === "accounts" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold text-white">Platform Accounts</h1>
              <p className="text-sm text-[rgba(255,255,255,0.4)] mt-1">Bullseye's accounts across each platform</p>
            </div>
            <Card title="X (Twitter)">
              <Row label="Account" value={<a href="https://x.com/bullseye_g4" target="_blank" rel="noopener noreferrer" className="text-[#C09E5A] hover:text-[#D4B575] underline">@bullseye_g4</a>} />
              <Row label="Also tracking" value={<a href="https://x.com/gauntletai" target="_blank" rel="noopener noreferrer" className="text-[#C09E5A] hover:text-[#D4B575] underline">@gauntletai</a>} />
            </Card>
            <Card title="Slack">
              <Row label="Bot name" value="Bullseye" />
              <Row label="Alert channel" value="#bullseye_comms" />
            </Card>
            <Card title="Reddit">
              <Row label="Account" value={<a href="https://www.reddit.com/user/Bullseye_Gauntlet/" target="_blank" rel="noopener noreferrer" className="text-[#C09E5A] hover:text-[#D4B575] underline">u/Bullseye_Gauntlet</a>} />
            </Card>
            <Card title="LinkedIn">
              <Row label="Account" value={<a href="https://linkedin.com/in/bullseye-undefined-290927403/" target="_blank" rel="noopener noreferrer" className="text-[#C09E5A] hover:text-[#D4B575] underline">Bullseye</a>} />
            </Card>
            <Card title="Google / Gmail">
              <Row label="Account" value={<a href="mailto:bullseye.gauntlet@gmail.com" className="text-[#C09E5A] hover:text-[#D4B575] underline">bullseye.gauntlet@gmail.com</a>} />
            </Card>
            <Card title="GitHub">
              <Row label="Account" value={<a href="https://github.com/bullseyegauntlet" target="_blank" rel="noopener noreferrer" className="text-[#C09E5A] hover:text-[#D4B575] underline">bullseyegauntlet</a>} />
            </Card>
          </div>
        )}

      </div>
    </div>
  );
}

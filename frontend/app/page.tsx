"use client";

import { useEffect, useState } from "react";
import { ResultCard } from "@/components/result-card";
import { PopularFeed } from "@/components/popular-feed";
import { MentionsFeed } from "@/components/mentions-feed";
import {
  querySemanticWithSummary,
  getHistory,
  getStats,
  formatRelativeTime,
  type QueryResult,
  type Post,
  type Stats,
  type HistoryEntry,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ActiveTab = "search" | "mentions" | "popular";

function SummaryBox({ summary }: { summary: string }) {
  return (
    <div className="border border-[rgba(192,158,90,0.2)] bg-[rgba(192,158,90,0.05)] p-4 mb-5" style={{ borderRadius: "4px" }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-semibold text-[#C09E5A] uppercase tracking-widest">AI Summary</span>
      </div>
      <p className="text-sm text-[rgba(255,255,255,0.75)] leading-relaxed">{summary}</p>
    </div>
  );
}

function RecentHistory({ onSelect }: { onSelect: (q: string) => void }) {
  const [items, setItems] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    getHistory(1, 5).then((d) => setItems(d.items)).catch(() => null);
  }, []);

  if (!items.length) return null;

  return (
    <div className="mt-8">
      <p className="text-[10px] font-semibold text-[rgba(255,255,255,0.25)] mb-2 uppercase tracking-widest px-1">
        Recent
      </p>
      <div className="space-y-px">
        {items.map((entry) => (
          <button
            key={entry.id}
            onClick={() => onSelect(entry.query_text)}
            className="w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left transition-all duration-150 group hover:bg-[rgba(255,255,255,0.03)] border border-transparent hover:border-[#2B2B2B]"
            style={{ borderRadius: "4px" }}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="text-[rgba(255,255,255,0.2)] text-xs shrink-0">→</span>
              <span className="text-sm text-[rgba(255,255,255,0.45)] truncate group-hover:text-[rgba(255,255,255,0.7)] transition-colors">
                {entry.query_text}
              </span>
            </div>
            <span className="text-[10px] text-[rgba(255,255,255,0.2)] shrink-0 tabular-nums">
              {formatRelativeTime(entry.created_at)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function useNextDataPull() {
  const getSecondsUntilNext = () => {
    const now = new Date();
    // Jobs run at every even UTC hour (0,2,4,6,8,10,12,14,16,18,20,22)
    // Next even hour = ceil current hour to next even number
    const nowHour = now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600;
    const nextHour = Math.ceil(nowHour / 2) * 2;
    const nextRun = new Date(now);
    nextRun.setUTCHours(nextHour % 24, 0, 0, 0);
    if (nextHour >= 24) nextRun.setUTCDate(nextRun.getUTCDate() + 1);
    return Math.max(0, Math.floor((nextRun.getTime() - now.getTime()) / 1000));
  };

  const [secs, setSecs] = useState(getSecondsUntilNext);

  useEffect(() => {
    const id = setInterval(() => setSecs(getSecondsUntilNext()), 1000);
    return () => clearInterval(id);
  }, []);

  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return h > 0
    ? `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`
    : `${m}m ${String(s).padStart(2, "0")}s`;
}

function TabBar({
  activeTab,
  setActiveTab,
  mentionsBadge,
  popularBadge,
}: {
  activeTab: ActiveTab;
  setActiveTab: (t: ActiveTab) => void;
  mentionsBadge: number;
  popularBadge: number;
}) {
  const countdown = useNextDataPull();

  const tabs: { id: ActiveTab; label: string; badge?: number }[] = [
    { id: "search",   label: "Search" },
    { id: "mentions", label: "@Mentions", badge: mentionsBadge },
    { id: "popular",  label: "🔥 Popular",  badge: popularBadge },
  ];

  return (
    <div className="flex items-center gap-0 mb-8 border-b border-[#2B2B2B]">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={cn(
            "flex items-center gap-2 px-5 py-3 text-sm font-medium transition-all duration-150 border-b-2 -mb-px",
            activeTab === tab.id
              ? "text-[#C09E5A] border-[#C09E5A]"
              : "text-[rgba(255,255,255,0.4)] border-transparent hover:text-[rgba(255,255,255,0.7)] hover:border-[rgba(255,255,255,0.15)]"
          )}
        >
          {tab.label}
          {tab.badge !== undefined && tab.badge > 0 && (
            <span className="inline-flex items-center justify-center w-4 h-4 text-[9px] font-bold bg-[#C09E5A] text-[#080808]" style={{ borderRadius: "2px" }}>
              {tab.badge > 9 ? "9+" : tab.badge}
            </span>
          )}
        </button>
      ))}
      <div className="ml-auto flex items-center gap-2 pb-px pr-1">
        <span className="text-[11px] text-[rgba(255,255,255,0.45)] tracking-wide font-medium">Next Data Pull</span>
        <span className="text-[11px] font-mono font-bold text-[#C09E5A] tabular-nums">{countdown}</span>
      </div>
    </div>
  );
}

function CardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <div
      className="animate-card border border-[#2B2B2B] p-4 space-y-3"
      style={{ borderRadius: "4px", animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-center gap-2">
        <div className="skeleton-shimmer h-4 w-14" style={{ borderRadius: "2px" }} />
        <div className="skeleton-shimmer h-3 w-28" style={{ borderRadius: "2px" }} />
      </div>
      <div className="skeleton-shimmer h-3 w-full" style={{ borderRadius: "2px" }} />
      <div className="skeleton-shimmer h-3 w-3/4" style={{ borderRadius: "2px" }} />
    </div>
  );
}

export default function QueryPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("search");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getStats().then(setStats).catch(() => null);
  }, []);

  const mentionsBadge = activeTab === "mentions" ? 0 : (stats?.mentions?.last_24h ?? 0);
  const popularBadge  = activeTab === "popular"  ? 0 : (stats?.popular?.last_24h  ?? 0);

  async function runQuery(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await querySemanticWithSummary(q.trim());
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    runQuery(query);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      runQuery(query);
    }
  }

  const hasResults = result !== null;

  return (
    <div className="relative z-10">
      <TabBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        mentionsBadge={mentionsBadge}
        popularBadge={popularBadge}
      />

      {activeTab === "mentions" && <MentionsFeed />}
      {activeTab === "popular"  && <PopularFeed />}

      {activeTab === "search" && (
        <div className="space-y-7">
          {/* Hero / search */}
          <div className={hasResults ? "" : "pt-6"}>
            {!hasResults && (
              <div className="mb-8">
                <p className="text-[10px] font-semibold text-[#C09E5A] tracking-widest uppercase mb-3">
                  Intelligence Console
                </p>
                <h1 className="text-4xl font-bold text-white mb-3 leading-tight" style={{ fontFamily: "var(--font-space-grotesk), sans-serif", letterSpacing: "-0.02em" }}>
                  What's the signal<br />
                  <span className="text-[rgba(255,255,255,0.4)]">in the noise?</span>
                </h1>
                <p className="text-sm text-[rgba(255,255,255,0.4)] max-w-md">
                  Ask anything across Slack, X, Reddit, and LinkedIn
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="search-glow relative flex items-center bg-[#121212] border border-[#2B2B2B] px-5 py-3.5 transition-all duration-200" style={{ borderRadius: "4px" }}>
                <svg className="w-4 h-4 text-[rgba(255,255,255,0.25)] shrink-0 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your marketing channels…"
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-[rgba(255,255,255,0.85)] placeholder:text-[rgba(255,255,255,0.2)] resize-none focus:outline-none leading-6"
                  style={{ minHeight: "24px", maxHeight: "120px" }}
                  onInput={(e) => {
                    const el = e.currentTarget;
                    el.style.height = "24px";
                    el.style.height = Math.min(el.scrollHeight, 120) + "px";
                  }}
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="ml-3 shrink-0 px-5 py-2 text-sm font-semibold transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed active:scale-95"
                  style={{
                    borderRadius: "4px",
                    backgroundColor: loading || !query.trim() ? "rgba(192,158,90,0.3)" : "#C09E5A",
                    color: "#080808",
                  }}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Searching
                    </span>
                  ) : "Search"}
                </button>
              </div>
            </form>

            {!hasResults && !loading && (
              <RecentHistory onSelect={(q) => { setQuery(q); runQuery(q); }} />
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-400" style={{ borderRadius: "4px" }}>
              {error}
            </div>
          )}

          {/* Results */}
          {(loading || hasResults) && (
            <div>
              {/* Summary skeleton */}
              {loading && (
                <div className="border border-[rgba(192,158,90,0.15)] bg-[rgba(192,158,90,0.04)] p-4 mb-5 space-y-2" style={{ borderRadius: "4px" }}>
                  <div className="skeleton-shimmer h-2.5 w-20" style={{ borderRadius: "2px" }} />
                  <div className="skeleton-shimmer h-3 w-full" style={{ borderRadius: "2px" }} />
                  <div className="skeleton-shimmer h-3 w-4/5" style={{ borderRadius: "2px" }} />
                </div>
              )}

              {!loading && result?.summary && <SummaryBox summary={result.summary} />}

              {!loading && result && (
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs text-[rgba(255,255,255,0.3)]">
                    <span className="text-[rgba(255,255,255,0.6)] font-medium">{result.count ?? 0}</span> results
                    {result.latency_ms && (
                      <span className="ml-2 text-[rgba(255,255,255,0.2)]">{result.latency_ms}ms</span>
                    )}
                  </span>
                  <button
                    onClick={() => { setResult(null); setQuery(""); }}
                    className="text-xs text-[rgba(255,255,255,0.3)] hover:text-[#C09E5A] transition-colors"
                  >
                    ← New search
                  </button>
                </div>
              )}

              {loading ? (
                <div className="space-y-2">
                  {[...Array(4)].map((_, i) => <CardSkeleton key={i} index={i} />)}
                </div>
              ) : result?.posts.length === 0 ? (
                <div className="text-center py-16 text-[rgba(255,255,255,0.25)] text-sm">
                  No results found. Try a different query.
                </div>
              ) : (
                <div className="space-y-2">
                  {result?.posts.map((post: Post, i: number) => (
                    <ResultCard key={post.id} post={post} index={i} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!loading && !hasResults && !error && (
            <div className="mt-10 border-t border-[#1e1e1e] pt-8 text-center">
              <p className="text-xs text-[rgba(255,255,255,0.2)]">Type a question above to search across Slack, X, Reddit, and LinkedIn</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

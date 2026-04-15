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
    <div className="rounded-2xl border border-primary/20 bg-gradient-to-br from-accent to-white p-4 mb-5">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center">
          <svg className="w-3 h-3 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
          </svg>
        </div>
        <span className="text-xs font-semibold text-primary uppercase tracking-widest">AI Summary</span>
      </div>
      <p className="text-sm text-foreground/90 leading-relaxed">{summary}</p>
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
      <p className="text-[11px] font-semibold text-muted-foreground mb-2 uppercase tracking-widest px-1">
        Recent
      </p>
      <div className="space-y-0.5">
        {items.map((entry) => (
          <button
            key={entry.id}
            onClick={() => onSelect(entry.query_text)}
            className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl hover:bg-white hover:shadow-sm border border-transparent hover:border-border text-left transition-all duration-150 group"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <svg className="w-3.5 h-3.5 text-muted-foreground shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path d="M12 6v6l4 2M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z"/>
              </svg>
              <span className="text-sm text-foreground/80 truncate group-hover:text-primary transition-colors">
                {entry.query_text}
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground shrink-0">
              {formatRelativeTime(entry.created_at)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
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
  const tabs: { id: ActiveTab; label: string; badge?: number }[] = [
    { id: "search", label: "Search" },
    { id: "mentions", label: "@Mentions", badge: mentionsBadge },
    { id: "popular", label: "🔥 Popular", badge: popularBadge },
  ];

  return (
    <div className="flex items-center gap-1 mb-7 bg-white border border-border rounded-2xl p-1 shadow-sm">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200",
            activeTab === tab.id
              ? "bg-primary text-white shadow-sm shadow-primary/30"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary"
          )}
        >
          {tab.label}
          {tab.badge !== undefined && tab.badge > 0 && (
            <span className={cn(
              "inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold leading-none",
              activeTab === tab.id ? "bg-white/25 text-white" : "bg-primary text-white"
            )}>
              {tab.badge > 9 ? "9+" : tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function CardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <div
      className="animate-card bg-white border border-border rounded-2xl p-4 space-y-3"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-center gap-2">
        <div className="skeleton-shimmer h-5 w-14 rounded-full" />
        <div className="skeleton-shimmer h-4 w-28 rounded-lg" />
      </div>
      <div className="skeleton-shimmer h-3 w-full rounded-lg" />
      <div className="skeleton-shimmer h-3 w-3/4 rounded-lg" />
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
  const popularBadge = activeTab === "popular" ? 0 : (stats?.popular?.last_24h ?? 0);

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

  function handleHistorySelect(q: string) {
    setQuery(q);
    runQuery(q);
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
      {activeTab === "popular" && <PopularFeed />}

      {activeTab === "search" && (
        <div className="space-y-6">
          {/* Search area */}
          <div className={hasResults ? "" : "pt-8"}>
            {!hasResults && (
              <div className="text-center mb-8">
                <h1 className="text-3xl font-bold text-foreground mb-2 tracking-tight">
                  Marketing Intelligence
                </h1>
                <p className="text-muted-foreground text-base">
                  Ask anything across Slack, X, and Reddit
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="search-glow relative flex items-center bg-white border border-border rounded-2xl px-5 py-3.5 transition-all duration-200">
                <svg className="w-4 h-4 text-muted-foreground shrink-0 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your marketing channels…"
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/70 resize-none focus:outline-none leading-6"
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
                  className="ml-3 shrink-0 px-5 py-2 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-150 shadow-sm shadow-primary/20"
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
              <RecentHistory onSelect={handleHistorySelect} />
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Results */}
          {(loading || hasResults) && (
            <div>
              {/* Summary skeleton */}
              {loading && (
                <div className="rounded-2xl border border-primary/15 bg-gradient-to-br from-accent to-white p-4 mb-5 space-y-2">
                  <div className="skeleton-shimmer h-3 w-28 rounded-full" />
                  <div className="skeleton-shimmer h-3 w-full rounded-lg" />
                  <div className="skeleton-shimmer h-3 w-4/5 rounded-lg" />
                </div>
              )}

              {!loading && result?.summary && <SummaryBox summary={result.summary} />}

              {!loading && result && (
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm text-muted-foreground">
                    <span className="font-semibold text-foreground">{result.count ?? 0}</span> results
                    {result.latency_ms && (
                      <span className="text-xs ml-1.5 text-muted-foreground/60">({result.latency_ms}ms)</span>
                    )}
                  </span>
                  <button
                    onClick={() => { setResult(null); setQuery(""); }}
                    className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 font-medium"
                  >
                    ← New search
                  </button>
                </div>
              )}

              {loading ? (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => <CardSkeleton key={i} index={i} />)}
                </div>
              ) : result?.posts.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground text-sm">
                  No results found. Try a different query.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {result?.posts.map((post: Post, i: number) => (
                    <ResultCard key={post.id} post={post} index={i} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!loading && !hasResults && !error && (
            <div className="flex flex-col items-center justify-center py-10 text-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-white border border-border shadow-sm flex items-center justify-center">
                <svg className="w-6 h-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">What are you looking for?</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                  Try "What is the community saying about AI agents?" or "Latest Slack discussions on hiring"
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

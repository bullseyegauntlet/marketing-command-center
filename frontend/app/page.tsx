"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { ResultCard } from "@/components/result-card";
import { PopularFeed } from "@/components/popular-feed";
import { MentionsFeed } from "@/components/mentions-feed";
import {
  querySemanticWithSummary,
  getStats,
  type QueryResult,
  type Post,
  type Stats,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ActiveTab = "search" | "mentions" | "popular";

function SummaryBox({ summary }: { summary: string }) {
  return (
    <div className="rounded-xl border border-[#c5cae9] bg-[#e8f0fe] p-4 mb-6">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-primary uppercase tracking-wide">AI Summary</span>
      </div>
      <p className="text-sm text-foreground leading-relaxed">{summary}</p>
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
  function tabClass(id: ActiveTab) {
    return cn(
      "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
      activeTab === id
        ? "border-primary text-primary"
        : "border-transparent text-muted-foreground hover:text-foreground"
    );
  }

  function Badge({ count }: { count: number }) {
    if (count <= 0) return null;
    return (
      <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white text-[10px] font-bold leading-none">
        {count > 9 ? "9+" : count}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1 border-b border-border mb-6">
      <button onClick={() => setActiveTab("search")} className={tabClass("search")}>
        Search
      </button>
      <button onClick={() => setActiveTab("mentions")} className={tabClass("mentions")}>
        @Mentions
        <Badge count={mentionsBadge} />
      </button>
      <button onClick={() => setActiveTab("popular")} className={tabClass("popular")}>
        🔥 Popular
        <Badge count={popularBadge} />
      </button>
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

  // Load stats for popular badge count
  useEffect(() => {
    getStats().then(setStats).catch(() => null);
  }, []);

  const mentionsBadge = activeTab === "mentions" ? 0 : (stats?.mentions?.last_24h ?? 0);
  const popularBadge = activeTab === "popular" ? 0 : (stats?.popular?.last_24h ?? 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await querySemanticWithSummary(query.trim());
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }

  const hasResults = result !== null;

  return (
    <div className="space-y-0">
      <TabBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        mentionsBadge={mentionsBadge}
        popularBadge={popularBadge}
      />

      {/* ── Mentions tab ── */}
      {activeTab === "mentions" && <MentionsFeed />}

      {/* ── Popular tab ── */}
      {activeTab === "popular" && <PopularFeed />}

      {/* ── Search tab ── */}
      {activeTab === "search" && (
        <div className="space-y-8">
          {/* Search area */}
          <div className={hasResults ? "mb-2" : "pt-10 pb-4"}>
            {!hasResults && (
              <div className="text-center mb-8">
                <h1 className="text-3xl font-semibold text-foreground mb-2">
                  Marketing Intelligence
                </h1>
                <p className="text-muted-foreground text-base">
                  Search across your Slack channels and X posts
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="relative flex items-center border border-border rounded-full shadow-sm hover:shadow-md focus-within:shadow-md focus-within:border-primary/40 bg-white transition-all px-5 py-3">
                <svg className="w-4 h-4 text-muted-foreground shrink-0 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your marketing channels…"
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground resize-none focus:outline-none leading-6"
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
                  className="ml-3 shrink-0 px-5 py-1.5 rounded-full bg-primary text-white text-sm font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Searching
                    </span>
                  ) : "Search"}
                </button>
              </div>
            </form>
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Results area */}
          {(loading || hasResults) && (
            <div>
              {loading && (
                <div className="rounded-xl border border-[#c5cae9] bg-[#e8f0fe] p-4 mb-6 space-y-2">
                  <Skeleton className="h-3 w-24 bg-blue-200" />
                  <Skeleton className="h-3 w-full bg-blue-200" />
                  <Skeleton className="h-3 w-4/5 bg-blue-200" />
                </div>
              )}

              {!loading && result?.summary && <SummaryBox summary={result.summary} />}

              {!loading && result && (
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">{result.count ?? 0}</span> results
                  </span>
                  {result.latency_ms && (
                    <span className="text-xs text-muted-foreground">({result.latency_ms}ms)</span>
                  )}
                </div>
              )}

              {loading ? (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="border border-border rounded-xl p-4 bg-white space-y-3">
                      <div className="flex gap-2 items-center">
                        <Skeleton className="h-5 w-10 rounded-full" />
                        <Skeleton className="h-4 w-32" />
                      </div>
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="h-3 w-4/5" />
                    </div>
                  ))}
                </div>
              ) : result?.posts.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground text-sm">
                  No results found. Try a different query.
                </div>
              ) : (
                <div className="space-y-3">
                  {result?.posts.map((post: Post, i: number) => (
                    <ResultCard key={post.id} post={post} index={i} />
                  ))}
                </div>
              )}
            </div>
          )}

          {!loading && !hasResults && !error && (
            <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
              <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center">
                <svg className="w-7 h-7 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">What are you looking for?</p>
                <p className="text-xs text-muted-foreground mt-1">Try "What is the community saying about AI agents?" or "Latest Slack discussions on hiring"</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

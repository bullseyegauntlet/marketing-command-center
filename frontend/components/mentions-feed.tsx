"use client";

import { useEffect, useState } from "react";
import { getMentions, type Post } from "@/lib/api";
import { ResultCard } from "@/components/result-card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Platform = "all" | "x" | "linkedin" | "reddit";
type TimeRange = "1" | "7" | "30";

export function MentionsFeed() {
  const [platform, setPlatform] = useState<Platform>("all");
  const [timeRange, setTimeRange] = useState<TimeRange>("7");
  const [posts, setPosts] = useState<Post[]>([]);
  const [total, setTotal] = useState(0);
  const [byPlatform, setByPlatform] = useState({ x: 0, linkedin: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const PAGE_SIZE = 20;
  const days = parseInt(timeRange);

  useEffect(() => {
    setPage(1);
  }, [platform, timeRange]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getMentions({ platform, days, page, page_size: PAGE_SIZE })
      .then((data) => {
        setPosts(data.mentions);
        setTotal(data.total);
        setByPlatform(data.by_platform);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [platform, days, page]);

  const hasMore = page * PAGE_SIZE < total;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-foreground">@Mentions</h2>
        <p className="text-sm text-muted-foreground mt-1">
          People talking about Gauntlet AI
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Platform filter */}
        <div className="flex items-center bg-white border border-border rounded-xl p.0.5 text-xs font-medium shadow-sm">
          {(["all", "x", "reddit", "linkedin"] as Platform[]).map((p) => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={cn(
                "px-3 py-1.5 rounded-lg transition-all duration-150",
                platform === p
                  ? "bg-primary text-white shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {p === "all" ? "All" : p === "x" ? "X" : p === "reddit" ? "Reddit" : "LinkedIn"}
            </button>
          ))}
        </div>

        {/* Time range filter */}
        <div className="flex items-center bg-white border border-border rounded-xl p.0.5 text-xs font-medium shadow-sm">
          {([["1", "24h"], ["7", "7d"], ["30", "30d"]] as [TimeRange, string][]).map(
            ([val, label]) => (
              <button
                key={val}
                onClick={() => setTimeRange(val)}
                className={cn(
                  "px-3 py-1.5 rounded-lg transition-all duration-150",
                  timeRange === val
                    ? "bg-primary text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {label}
              </button>
            )
          )}
        </div>

        {/* Counts */}
        {!loading && total > 0 && (
          <div className="flex items-center gap-2 ml-1">
            <span className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{total}</span> mentions
            </span>
            {byPlatform.x > 0 && (
              <span className="text-xs text-muted-foreground">
                · <span className="font-medium text-foreground">{byPlatform.x}</span> X
              </span>
            )}
            {byPlatform.reddit !== undefined && byPlatform.reddit > 0 && (
              <span className="text-xs text-muted-foreground">
                · <span className="font-medium text-foreground">{byPlatform.reddit}</span> Reddit
              </span>
            )}
            {byPlatform.linkedin > 0 && (
              <span className="text-xs text-muted-foreground">
                · <span className="font-medium text-foreground">{byPlatform.linkedin}</span> LinkedIn
              </span>
            )}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="border border-border rounded-xl p-4 bg-white space-y-3">
              <div className="flex gap-2 items-center">
                <Skeleton className="h-5 w-10 rounded-full" />
                <Skeleton className="h-4 w-36" />
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && posts.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
          <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center text-2xl">
            📡
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              No mentions found in the last {timeRange === "1" ? "24 hours" : `${timeRange} days`}.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Try expanding the time range.
            </p>
          </div>
        </div>
      )}

      {/* Results */}
      {!loading && posts.length > 0 && (
        <div className="space-y-3">
          {posts.map((post: Post, i: number) => (
            <ResultCard key={post.id} post={post} index={i} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {!loading && (hasMore || page > 1) && (
        <div className="flex items-center justify-center gap-3 pt-2">
          {page > 1 && (
            <button
              onClick={() => setPage((p) => p - 1)}
              className="text-xs text-primary hover:underline font-medium"
            >
              ← Previous
            </button>
          )}
          <span className="text-xs text-muted-foreground">Page {page}</span>
          {hasMore && (
            <button
              onClick={() => setPage((p) => p + 1)}
              className="text-xs text-primary hover:underline font-medium"
            >
              Next →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

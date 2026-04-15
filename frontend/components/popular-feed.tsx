"use client";

import { useEffect, useState } from "react";
import { getPopularPosts, formatRelativeTime, type PopularPost } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

type Platform = "all" | "x" | "slack";
type TimeRange = "7" | "30" | "all";

const platformConfig: Record<string, { label: string; badgeClass: string }> = {
  x: { label: "X", badgeClass: "bg-gray-900 text-white" },
  slack: { label: "Slack", badgeClass: "bg-purple-600 text-white" },
};

const triggerLabels: Record<string, string> = {
  views: "views",
  likes: "likes",
  reposts: "reposts",
  replies: "replies",
  slack_thread_replies: "replies",
};

const triggerIcons: Record<string, string> = {
  views: "👁",
  likes: "❤",
  reposts: "🔁",
  replies: "💬",
  slack_thread_replies: "💬",
};

const TRUNCATE_AT = 280;

function PopularCard({ post, index = 0 }: { post: PopularPost; index?: number }) {
  const [expanded, setExpanded] = useState(false);
  const platform = platformConfig[post.platform] ?? platformConfig.slack;
  const isLong = post.content.length > TRUNCATE_AT;
  const displayContent =
    isLong && !expanded ? post.content.slice(0, TRUNCATE_AT).trimEnd() + "…" : post.content;

  const triggerIcon = triggerIcons[post.triggered_by] ?? "🔥";
  const triggerLabel = triggerLabels[post.triggered_by] ?? post.triggered_by;

  return (
    <div
      className="animate-card border border-border rounded-xl p-4 bg-white hover:shadow-sm hover:border-amber-200 transition-all duration-150"
      style={{ animationDelay: `${Math.min(index * 40, 400)}ms` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-base leading-none">🔥</span>
          <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full", platform.badgeClass)}>
            {platform.label}
          </span>
          {post.channel && (
            <span className="text-xs text-muted-foreground">#{post.channel}</span>
          )}
          <span className="text-sm font-medium text-foreground">@{post.author}</span>
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
          {formatRelativeTime(post.published_at)}
        </span>
      </div>

      {/* Content */}
      <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap break-words">
        {displayContent}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-primary hover:text-primary/80 font-medium transition-colors"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
        <div className="flex items-center gap-3">
          {post.platform === "x" && (
            <>
              {post.views !== undefined && post.views > 0 && (
                <span className="text-xs text-muted-foreground">👁 {post.views.toLocaleString()}</span>
              )}
              {post.likes !== undefined && (
                <span className="text-xs text-muted-foreground">❤ {post.likes.toLocaleString()}</span>
              )}
              {post.retweets !== undefined && (
                <span className="text-xs text-muted-foreground">🔁 {post.retweets.toLocaleString()}</span>
              )}
              {post.replies !== undefined && (
                <span className="text-xs text-muted-foreground">💬 {post.replies.toLocaleString()}</span>
              )}
            </>
          )}
          {post.platform === "slack" && post.metric_value > 0 && (
            <span className="text-xs text-muted-foreground">💬 {post.metric_value} replies</span>
          )}
          <span className="text-xs text-amber-600 font-medium">
            {triggerIcon} Flagged for {post.metric_value.toLocaleString()} {triggerLabel}
          </span>
        </div>
        <a
          href={post.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:underline font-medium"
          onClick={(e) => e.stopPropagation()}
        >
          View →
        </a>
      </div>
    </div>
  );
}

export function PopularFeed() {
  const [platform, setPlatform] = useState<Platform>("all");
  const [timeRange, setTimeRange] = useState<TimeRange>("30");
  const [posts, setPosts] = useState<PopularPost[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const PAGE_SIZE = 20;
  const days = timeRange === "all" ? 3650 : parseInt(timeRange);

  useEffect(() => {
    setPage(1);
  }, [platform, timeRange]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPopularPosts({ platform, days, page, page_size: PAGE_SIZE })
      .then((data) => {
        setPosts(data.posts);
        setTotal(data.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [platform, days, page]);

  const hasMore = page * PAGE_SIZE < total;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-foreground">Popular Posts</h2>
        <p className="text-sm text-muted-foreground mt-1">
          High-engagement content from X and Slack
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Platform filter */}
        <div className="flex items-center rounded-full border border-border bg-white overflow-hidden text-xs font-medium">
          {(["all", "x", "slack"] as Platform[]).map((p) => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={cn(
                "px-3 py-1.5 transition-colors",
                platform === p
                  ? "bg-primary text-white"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {p === "all" ? "All" : p === "x" ? "X" : "Slack"}
            </button>
          ))}
        </div>

        {/* Time range filter */}
        <div className="flex items-center rounded-full border border-border bg-white overflow-hidden text-xs font-medium">
          {([["7", "7d"], ["30", "30d"], ["all", "All time"]] as [TimeRange, string][]).map(
            ([val, label]) => (
              <button
                key={val}
                onClick={() => setTimeRange(val)}
                className={cn(
                  "px-3 py-1.5 transition-colors",
                  timeRange === val
                    ? "bg-primary text-white"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {label}
              </button>
            )
          )}
        </div>

        {!loading && total > 0 && (
          <span className="text-xs text-muted-foreground ml-1">
            <span className="font-medium text-foreground">{total}</span> flagged
          </span>
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
          {[...Array(4)].map((_, i) => (
            <div key={i} className="border border-border rounded-xl p-4 bg-white space-y-3">
              <div className="flex gap-2 items-center">
                <Skeleton className="h-5 w-5 rounded-full" />
                <Skeleton className="h-5 w-10 rounded-full" />
                <Skeleton className="h-4 w-32" />
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {!loading && posts.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
          <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center text-2xl">
            🔥
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              No posts have crossed the popularity threshold yet.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Check back after the next engagement recheck runs.
            </p>
          </div>
        </div>
      )}

      {!loading && posts.length > 0 && (
        <div className="space-y-3">
          {posts.map((post, i) => (
            <PopularCard key={post.id} post={post} index={i} />
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

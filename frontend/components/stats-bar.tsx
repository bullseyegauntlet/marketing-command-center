"use client";

import { useEffect, useState } from "react";
import { getStats, formatRelativeTime, type Stats } from "@/lib/api";

export function StatsBar() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setError(true));
  }, []);

  const lastRun = stats?.last_ingestion
    ?.filter((i) => i.status === "success")
    .sort((a, b) => new Date(b.last_run_at).getTime() - new Date(a.last_run_at).getTime())[0];

  if (error) return null;
  if (!stats) return null;

  return (
    <div className="bg-secondary border-b border-border">
      <div className="container mx-auto px-6 max-w-4xl">
        <div className="flex items-center gap-4 h-9 overflow-x-auto">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs text-emerald-600 font-medium">Live</span>
          </div>
          <span className="text-border">·</span>
          <span className="text-xs text-muted-foreground shrink-0">
            <span className="font-medium text-foreground">{stats.total_posts.toLocaleString()}</span> posts
          </span>
          {stats.posts_by_platform?.slack && (
            <>
              <span className="text-border">·</span>
              <span className="text-xs text-muted-foreground shrink-0">
                <span className="font-medium text-foreground">{stats.posts_by_platform.slack.toLocaleString()}</span> Slack
              </span>
            </>
          )}
          {stats.posts_by_platform?.x && (
            <>
              <span className="text-border">·</span>
              <span className="text-xs text-muted-foreground shrink-0">
                <span className="font-medium text-foreground">{stats.posts_by_platform.x.toLocaleString()}</span> X
              </span>
            </>
          )}
          {lastRun && (
            <>
              <span className="text-border">·</span>
              <span className="text-xs text-muted-foreground shrink-0">
                Updated <span className="font-medium text-foreground">{formatRelativeTime(lastRun.last_run_at)}</span>
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

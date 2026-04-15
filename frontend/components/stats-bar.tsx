"use client";

import { useEffect, useState } from "react";
import { getStats, formatRelativeTime, type Stats } from "@/lib/api";

export function StatsBar() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getStats().then(setStats).catch(() => null);
  }, []);

  if (!stats) return null;

  const lastRun = stats.last_ingestion
    ?.filter((i) => i.status === "success")
    .sort((a, b) => new Date(b.last_run_at).getTime() - new Date(a.last_run_at).getTime())[0];

  return (
    <div className="bg-white/60 backdrop-blur-sm border-b border-border/60">
      <div className="container mx-auto px-6 max-w-5xl">
        <div className="flex items-center gap-3 h-8 overflow-x-auto">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-300" />
            <span className="text-[11px] text-emerald-600 font-semibold tracking-wide uppercase">Live</span>
          </div>
          <div className="w-px h-3 bg-border shrink-0" />
          <span className="text-[11px] text-muted-foreground shrink-0">
            <span className="font-semibold text-foreground">{stats.total_posts.toLocaleString()}</span> posts
          </span>
          {stats.posts_by_platform?.slack > 0 && (
            <>
              <div className="w-px h-3 bg-border shrink-0" />
              <span className="text-[11px] text-muted-foreground shrink-0">
                <span className="font-semibold text-foreground">{stats.posts_by_platform.slack.toLocaleString()}</span> Slack
              </span>
            </>
          )}
          {stats.posts_by_platform?.x > 0 && (
            <>
              <div className="w-px h-3 bg-border shrink-0" />
              <span className="text-[11px] text-muted-foreground shrink-0">
                <span className="font-semibold text-foreground">{stats.posts_by_platform.x.toLocaleString()}</span> X
              </span>
            </>
          )}
          {lastRun && (
            <>
              <div className="w-px h-3 bg-border shrink-0" />
              <span className="text-[11px] text-muted-foreground shrink-0">
                Updated <span className="font-semibold text-foreground">{formatRelativeTime(lastRun.last_run_at)}</span>
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

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
    <div className="border-b border-[#1e1e1e] bg-[#0c0c0c]">
      <div className="container mx-auto px-6 max-w-5xl">
        <div className="flex items-center gap-4 h-8 overflow-x-auto">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] text-emerald-500 font-semibold tracking-widest uppercase">Live</span>
          </div>
          <span className="text-[#2B2B2B]">|</span>
          <span className="text-[10px] text-[rgba(255,255,255,0.3)] shrink-0">
            <span className="text-[rgba(255,255,255,0.6)] font-medium">{stats.total_posts.toLocaleString()}</span> posts indexed
          </span>
          {stats.posts_by_platform?.slack > 0 && (
            <>
              <span className="text-[#2B2B2B]">·</span>
              <span className="text-[10px] text-[rgba(255,255,255,0.3)] shrink-0">
                <span className="text-[rgba(255,255,255,0.6)] font-medium">{stats.posts_by_platform.slack.toLocaleString()}</span> Slack
              </span>
            </>
          )}
          {stats.posts_by_platform?.x > 0 && (
            <>
              <span className="text-[#2B2B2B]">·</span>
              <span className="text-[10px] text-[rgba(255,255,255,0.3)] shrink-0">
                <span className="text-[rgba(255,255,255,0.6)] font-medium">{stats.posts_by_platform.x.toLocaleString()}</span> X
              </span>
            </>
          )}
          {lastRun && (
            <>
              <span className="text-[#2B2B2B]">·</span>
              <span className="text-[10px] text-[rgba(255,255,255,0.3)] shrink-0">
                Updated <span className="text-[rgba(255,255,255,0.6)] font-medium">{formatRelativeTime(lastRun.last_run_at)}</span>
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { getStats, formatRelativeTime, type Stats } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

function StatItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      <span className="text-muted-foreground text-xs font-mono uppercase tracking-widest">{label}</span>
      <span className="text-foreground text-xs font-mono font-semibold">{value}</span>
    </div>
  );
}

function StatDivider() {
  return <div className="w-px h-4 bg-border" />;
}

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

  return (
    <div className="border-b border-border bg-card/30 overflow-x-auto">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex items-center h-9 gap-0">
          {error ? (
            <span className="text-xs text-muted-foreground font-mono px-3">
              ⚠ stats unavailable — backend offline?
            </span>
          ) : !stats ? (
            <>
              <Skeleton className="h-3 w-20 mx-3" />
              <StatDivider />
              <Skeleton className="h-3 w-16 mx-3" />
              <StatDivider />
              <Skeleton className="h-3 w-16 mx-3" />
              <StatDivider />
              <Skeleton className="h-3 w-24 mx-3" />
            </>
          ) : (
            <>
              <div className="flex items-center">
                <span className="w-2 h-2 rounded-full bg-emerald-500 ml-3 mr-1.5 animate-pulse" />
                <span className="text-emerald-500 text-xs font-mono">LIVE</span>
              </div>
              <StatDivider />
              <StatItem label="total posts" value={stats.total_posts.toLocaleString()} />
              <StatDivider />
              <StatItem label="X" value={stats.posts_by_platform?.x?.toLocaleString() ?? "—"} />
              <StatDivider />
              <StatItem label="Slack" value={stats.posts_by_platform?.slack?.toLocaleString() ?? "—"} />
              {lastRun && (
                <>
                  <StatDivider />
                  <StatItem
                    label="last ingest"
                    value={formatRelativeTime(lastRun.last_run_at)}
                  />
                </>
              )}
              {stats.active_projects !== undefined && (
                <>
                  <StatDivider />
                  <StatItem label="projects" value={stats.active_projects} />
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

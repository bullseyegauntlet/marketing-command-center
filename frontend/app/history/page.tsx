"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ResultCard } from "@/components/result-card";
import {
  getHistory,
  getHistoryDetail,
  exportHistoryMarkdown,
  formatRelativeTime,
  formatAbsoluteTime,
  type HistoryEntry,
  type HistoryDetail,
  type PaginatedHistory,
  type Post,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const engineColors: Record<string, string> = {
  keyword: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  semantic: "text-sky-400 bg-sky-400/10 border-sky-400/20",
  side_by_side: "text-violet-400 bg-violet-400/10 border-violet-400/20",
  semantic_with_summary: "text-violet-400 bg-violet-400/10 border-violet-400/20",
};

const engineLabels: Record<string, string> = {
  keyword: "Keyword",
  semantic: "Semantic",
  side_by_side: "Side-by-Side",
  semantic_with_summary: "With Summary",
};

function HistoryRowSkeleton() {
  return (
    <div className="border border-border rounded-lg p-4 bg-card space-y-2">
      <div className="flex items-center gap-3">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-4 w-16 ml-auto" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  );
}

function HistoryRow({
  entry,
  isExpanded,
  onToggle,
}: {
  entry: HistoryEntry;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const engineClass = engineColors[entry.engine] ?? engineColors.semantic;

  useEffect(() => {
    if (isExpanded && !detail) {
      setDetailLoading(true);
      getHistoryDetail(entry.id)
        .then(setDetail)
        .catch(console.error)
        .finally(() => setDetailLoading(false));
    }
  }, [isExpanded, detail, entry.id]);

  async function handleExport() {
    setExporting(true);
    try {
      const md = await exportHistoryMarkdown(entry.id);
      const blob = new Blob([md], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mcc-query-${entry.id.slice(0, 8)}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setExporting(false);
    }
  }

  const posts: Post[] = detail?.results_snapshot ?? [];

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden transition-all">
      {/* Row header — always visible */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-4 py-3 hover:bg-secondary/50 transition-colors"
      >
        <div className="flex items-start gap-3">
          {/* Engine badge */}
          <span className={cn("text-xs font-mono font-semibold px-1.5 py-0.5 rounded border shrink-0 mt-0.5", engineClass)}>
            {engineLabels[entry.engine]}
          </span>

          {/* Query text */}
          <span className="flex-1 text-sm text-foreground font-mono truncate text-left">
            {entry.query_text}
          </span>

          {/* Meta */}
          <div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground font-mono">
            <span>{entry.result_count} posts</span>
            {entry.latency_ms && <span>{entry.latency_ms}ms</span>}
            <span>{formatRelativeTime(entry.created_at)}</span>
            <span className={cn("transition-transform duration-200", isExpanded ? "rotate-90" : "")}>▶</span>
          </div>
        </div>

        {/* Absolute time */}
        <div className="mt-1 ml-[calc(theme(spacing.1)+64px+theme(spacing.3))] text-xs text-muted-foreground/60 font-mono">
          {formatAbsoluteTime(entry.created_at)}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-border px-4 pb-4 pt-3 space-y-4">
          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handleExport}
              disabled={exporting}
              className="text-xs font-mono h-7"
            >
              {exporting ? "Exporting…" : "Export .md ↓"}
            </Button>
            {entry.summary && (
              <span className="text-xs text-muted-foreground font-mono">AI summary available</span>
            )}
          </div>

          {/* Summary */}
          {detail?.summary && (
            <div className="border border-primary/20 rounded-lg p-3 bg-primary/5">
              <div className="text-xs font-mono text-primary uppercase tracking-widest mb-1.5">Claude Summary</div>
              <p className="text-sm text-foreground/90 leading-relaxed">{detail.summary}</p>
            </div>
          )}

          {/* Results */}
          {detailLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="border border-border rounded-lg p-4 space-y-2">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                </div>
              ))}
            </div>
          ) : posts.length === 0 ? (
            <p className="text-sm text-muted-foreground font-mono text-center py-4">
              No result snapshot available.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
                {posts.length} result{posts.length !== 1 ? "s" : ""} at query time
              </div>
              {posts.map((post, i) => (
                <ResultCard key={post.id} post={post} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const [data, setData] = useState<PaginatedHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const pageSize = 20;

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getHistory(p, pageSize);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page);
  }, [load, page]);

  function toggleRow(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Query History</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every query saved with full result snapshots
          </p>
        </div>
        {data && (
          <span className="text-xs font-mono text-muted-foreground">
            {data.total} total queries
          </span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="border border-destructive/30 bg-destructive/10 rounded-lg px-4 py-3 text-sm text-destructive font-mono">
          ✕ {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => <HistoryRowSkeleton key={i} />)}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="text-4xl mb-4 opacity-20">◎</div>
          <p className="text-muted-foreground text-sm font-mono">No queries yet.</p>
          <p className="text-muted-foreground/50 text-xs font-mono mt-1">
            Run a query on the Query page to see it here.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.items.map((entry) => (
            <HistoryRow
              key={entry.id}
              entry={entry}
              isExpanded={expandedId === entry.id}
              onToggle={() => toggleRow(entry.id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => p - 1)}
            className="font-mono text-xs h-7"
          >
            ← Prev
          </Button>

          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const p = totalPages <= 7
                ? i + 1
                : page <= 4
                ? i + 1
                : page >= totalPages - 3
                ? totalPages - 6 + i
                : page - 3 + i;
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={cn(
                    "w-7 h-7 rounded text-xs font-mono transition-colors",
                    p === page
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                  )}
                >
                  {p}
                </button>
              );
            })}
          </div>

          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
            className="font-mono text-xs h-7"
          >
            Next →
          </Button>
        </div>
      )}
    </div>
  );
}

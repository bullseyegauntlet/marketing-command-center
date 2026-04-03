"use client";

import { useEffect, useState, useCallback } from "react";
import { Skeleton } from "@/components/ui/skeleton";
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

const engineLabels: Record<string, string> = {
  keyword: "Keyword",
  semantic: "Semantic",
  side_by_side: "Side-by-Side",
  semantic_with_summary: "With Summary",
};

const engineColors: Record<string, string> = {
  keyword: "bg-amber-100 text-amber-700",
  semantic: "bg-blue-100 text-blue-700",
  side_by_side: "bg-purple-100 text-purple-700",
  semantic_with_summary: "bg-blue-100 text-blue-700",
};

function HistoryRowSkeleton() {
  return (
    <div className="border border-border rounded-xl p-4 bg-white space-y-2">
      <div className="flex items-center gap-3">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-4 w-16 ml-auto" />
      </div>
      <Skeleton className="h-3 w-32" />
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
    <div className="border border-border rounded-xl bg-white overflow-hidden transition-all hover:shadow-sm">
      {/* Row header */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-4 py-3.5 hover:bg-secondary/60 transition-colors"
      >
        <div className="flex items-start gap-3">
          <span className={cn("text-xs font-semibold px-2.5 py-0.5 rounded-full shrink-0 mt-0.5", engineClass)}>
            {engineLabels[entry.engine] ?? entry.engine}
          </span>
          <span className="flex-1 text-sm text-foreground truncate text-left">
            {entry.query_text}
          </span>
          <div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground">
            <span>{entry.result_count} results</span>
            <span>{formatRelativeTime(entry.created_at)}</span>
            <svg
              className={cn("w-4 h-4 transition-transform duration-200", isExpanded ? "rotate-180" : "")}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </div>
        </div>
        <div className="mt-0.5 ml-[calc(theme(spacing.2)+80px+theme(spacing.3))] text-xs text-muted-foreground">
          {formatAbsoluteTime(entry.created_at)}
        </div>
      </button>

      {/* Expanded */}
      {isExpanded && (
        <div className="border-t border-border px-4 pb-5 pt-4 space-y-4 bg-secondary/30">
          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="text-xs text-primary hover:underline font-medium disabled:opacity-50"
            >
              {exporting ? "Exporting…" : "Export as Markdown ↓"}
            </button>
          </div>

          {detail?.summary && (
            <div className="rounded-xl border border-[#c5cae9] bg-[#e8f0fe] p-4">
              <div className="text-xs font-semibold text-primary uppercase tracking-wide mb-1.5">AI Summary</div>
              <p className="text-sm text-foreground leading-relaxed">{detail.summary}</p>
            </div>
          )}

          {detailLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="border border-border rounded-xl p-4 bg-white space-y-2">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                </div>
              ))}
            </div>
          ) : posts.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No result snapshot available.
            </p>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                {posts.length} result{posts.length !== 1 ? "s" : ""} at query time
              </p>
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
          <h1 className="text-2xl font-semibold text-foreground">Query History</h1>
          <p className="text-sm text-muted-foreground mt-1">
            All past searches with saved results
          </p>
        </div>
        {data && (
          <span className="text-sm text-muted-foreground">
            {data.total.toLocaleString()} queries
          </span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => <HistoryRowSkeleton key={i} />)}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center gap-3">
          <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center">
            <svg className="w-7 h-7 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">No history yet</p>
            <p className="text-xs text-muted-foreground mt-1">Your searches will appear here</p>
          </div>
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
        <div className="flex items-center justify-center gap-1 pt-2">
          <button
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1.5 rounded-full text-sm text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            ← Prev
          </button>

          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            const p = totalPages <= 7 ? i + 1 : page <= 4 ? i + 1 : page >= totalPages - 3 ? totalPages - 6 + i : page - 3 + i;
            return (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={cn(
                  "w-8 h-8 rounded-full text-sm transition-colors",
                  p === page
                    ? "bg-primary text-white font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                {p}
              </button>
            );
          })}

          <button
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1.5 rounded-full text-sm text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

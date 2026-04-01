"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ResultCard } from "@/components/result-card";
import {
  querySemantic,
  querySemanticWithSummary,
  type QueryResult,
  type Post,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Mode = "semantic" | "with-summary";

const modes: { id: Mode; label: string; desc: string }[] = [
  { id: "semantic", label: "Semantic", desc: "pgvector similarity search" },
  { id: "with-summary", label: "With Summary", desc: "Semantic search + Claude AI summary" },
];

function ResultsColumn({
  result,
  loading,
}: {
  result: QueryResult | null;
  loading: boolean;
}) {
  return (
    <div className="flex-1 min-w-0">
      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="border border-border rounded-lg p-4 bg-card space-y-2">
              <div className="flex gap-2">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-24" />
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
              <Skeleton className="h-3 w-3/5" />
            </div>
          ))}
        </div>
      ) : result === null ? null : result.posts.length === 0 ? (
        <div className="border border-border rounded-lg p-8 text-center text-muted-foreground text-sm font-mono">
          No results found.
        </div>
      ) : (
        <div className="space-y-3">
          {result.posts.map((post: Post, i: number) => (
            <ResultCard key={post.id} post={post} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryBox({ summary }: { summary: string }) {
  return (
    <div className="border border-primary/20 rounded-lg p-4 bg-primary/5 mb-6">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-mono text-primary uppercase tracking-widest">Claude Summary</span>
        <div className="flex-1 h-px bg-primary/20" />
      </div>
      <p className="text-sm text-foreground/90 leading-relaxed">{summary}</p>
    </div>
  );
}

export default function QueryPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("semantic");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);

  const hasResults = result !== null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      if (mode === "semantic") {
        const res = await querySemantic(query.trim());
        setResult(res);
      } else {
        const res = await querySemanticWithSummary(query.trim());
        setResult(res);
      }
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Intelligence Query</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Search across ingested X and Slack content
        </p>
      </div>

      {/* Query Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Mode Selector */}
        <div className="flex gap-1 p-1 bg-secondary rounded-lg w-fit">
          {modes.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMode(m.id)}
              className={cn(
                "px-4 py-1.5 rounded text-xs font-mono font-medium transition-all duration-150",
                mode === m.id
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Active mode description */}
        <p className="text-xs text-muted-foreground font-mono -mt-2">
          {modes.find((m) => m.id === mode)?.desc}
        </p>

        {/* Input area */}
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What is Gauntlet AI's community saying about AI agents?"
              rows={2}
              className="w-full rounded-lg bg-secondary border border-border px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground font-mono resize-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary/50 transition-all"
            />
            <span className="absolute bottom-2 right-3 text-xs text-muted-foreground/50 font-mono">⏎ run</span>
          </div>
          <Button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-6 bg-primary hover:bg-primary/90 text-primary-foreground font-mono self-stretch"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Running
              </span>
            ) : (
              "Run →"
            )}
          </Button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="border border-destructive/30 bg-destructive/10 rounded-lg px-4 py-3 text-sm text-destructive font-mono">
          ✕ {error}
        </div>
      )}

      {/* Results */}
      {(loading || hasResults) && (
        <div>
          {/* Meta row */}
          {!loading && result && (
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
                Semantic results
              </span>
              <span className="text-xs font-mono text-primary/70">
                {result.count ?? 0} posts
              </span>
              {result.latency_ms && (
                <span className="text-xs font-mono text-muted-foreground ml-auto">
                  {result.latency_ms}ms
                </span>
              )}
            </div>
          )}

          {/* Summary loading skeleton */}
          {loading && mode === "with-summary" && (
            <div className="border border-primary/20 rounded-lg p-4 bg-primary/5 mb-4 space-y-2">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
            </div>
          )}

          {/* Claude summary (with-summary mode) */}
          {!loading && result?.summary && (
            <SummaryBox summary={result.summary} />
          )}

          <ResultsColumn result={result} loading={loading} />
        </div>
      )}

      {/* Empty state */}
      {!loading && !hasResults && !error && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="text-4xl mb-4 opacity-20">◎</div>
          <p className="text-muted-foreground text-sm font-mono">
            Run a query to search across X and Slack content
          </p>
          <p className="text-muted-foreground/50 text-xs font-mono mt-1">
            Shift+Enter for newline · Enter to run
          </p>
        </div>
      )}
    </div>
  );
}

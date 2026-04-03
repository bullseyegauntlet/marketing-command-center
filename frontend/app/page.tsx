"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ResultCard } from "@/components/result-card";
import {
  queryKeyword,
  querySemantic,
  queryCompare,
  type QueryResult,
  type CompareResult,
  type Post,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Mode = "keyword" | "semantic" | "side-by-side";

const modes: { id: Mode; label: string; desc: string }[] = [
  { id: "keyword", label: "Keyword", desc: "Full-text PostgreSQL search" },
  { id: "semantic", label: "Semantic", desc: "pgvector similarity search" },
  { id: "side-by-side", label: "Side-by-Side", desc: "Both engines + AI summary" },
];

function ResultsColumn({
  label,
  result,
  loading,
}: {
  label?: string;
  result: QueryResult | null;
  loading: boolean;
}) {
  return (
    <div className="flex-1 min-w-0">
      {label && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">{label}</span>
          {result && (
            <span className="text-xs font-mono text-primary/70">{result.count} results</span>
          )}
          {result?.latency_ms && (
            <span className="text-xs font-mono text-muted-foreground ml-auto">{result.latency_ms}ms</span>
          )}
        </div>
      )}
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
  const [mode, setMode] = useState<Mode>("keyword");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [keywordResult, setKeywordResult] = useState<QueryResult | null>(null);
  const [semanticResult, setSemanticResult] = useState<QueryResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);

  const hasResults = keywordResult !== null || semanticResult !== null || compareResult !== null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setKeywordResult(null);
    setSemanticResult(null);
    setCompareResult(null);

    try {
      if (mode === "keyword") {
        const res = await queryKeyword(query.trim());
        setKeywordResult(res);
      } else if (mode === "semantic") {
        const res = await querySemantic(query.trim());
        setSemanticResult(res);
      } else {
        const res = await queryCompare(query.trim());
        setCompareResult(res);
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
          {/* Side-by-Side Mode */}
          {mode === "side-by-side" && (
            <div className="space-y-4">
              {/* Summary */}
              {compareResult?.summary && !loading && (
                <SummaryBox summary={compareResult.summary} />
              )}
              {loading && (
                <div className="border border-primary/20 rounded-lg p-4 bg-primary/5 mb-4 space-y-2">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-5/6" />
                </div>
              )}

              {/* Latency */}
              {compareResult?.latency_ms && !loading && (
                <div className="text-xs font-mono text-muted-foreground text-right">
                  total: {compareResult.latency_ms}ms
                </div>
              )}

              {/* Columns */}
              <div className="flex gap-4">
                <ResultsColumn
                  label="KEYWORD"
                  result={compareResult?.keyword ?? null}
                  loading={loading}
                />
                <div className="w-px bg-border" />
                <ResultsColumn
                  label="SEMANTIC"
                  result={compareResult?.semantic ?? null}
                  loading={loading}
                />
              </div>
            </div>
          )}

          {/* Single column modes */}
          {mode !== "side-by-side" && (
            <div>
              {/* Meta row */}
              {!loading && (keywordResult || semanticResult) && (
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
                    {mode === "keyword" ? "Keyword" : "Semantic"} results
                  </span>
                  <span className="text-xs font-mono text-primary/70">
                    {(keywordResult ?? semanticResult)?.count ?? 0} posts
                  </span>
                  {(keywordResult ?? semanticResult)?.latency_ms && (
                    <span className="text-xs font-mono text-muted-foreground ml-auto">
                      {(keywordResult ?? semanticResult)?.latency_ms}ms
                    </span>
                  )}
                </div>
              )}

              {/* Summary if semantic */}
              {!loading && semanticResult?.summary && (
                <SummaryBox summary={semanticResult.summary} />
              )}

              <ResultsColumn
                result={keywordResult ?? semanticResult}
                loading={loading}
              />
            </div>
          )}
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

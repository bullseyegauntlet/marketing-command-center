const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Post {
  id: string;
  platform: "x" | "slack" | "reddit" | "linkedin";
  external_id: string;
  author: string;
  content: string;
  source_url: string;
  published_at: string;
  ingested_at: string;
  likes?: number;
  retweets?: number;
  replies?: number;
  channel?: string;
  links?: string[];
  score?: number;
}

export interface QueryResult {
  posts: Post[];
  summary?: string;
  latency_ms?: number;
  count: number;
}

export interface HistoryEntry {
  id: string;
  user_id?: string;
  query_text: string;
  filters?: Record<string, unknown>;
  engine: "semantic" | "semantic_with_summary";
  summary?: string;
  results_snapshot?: unknown;
  result_count: number;
  latency_ms?: number;
  created_at: string;
}

export interface HistoryDetail extends HistoryEntry {
  results_snapshot: Post[];
}

export interface Stats {
  total_posts: number;
  posts_by_platform: {
    x: number;
    slack: number;
    linkedin?: number;
  };
  last_ingestion: {
    source: string;
    last_run_at: string;
    status: string;
  }[];
  active_projects?: number;
  mentions?: {
    total: number;
    last_24h: number;
    x: number;
    linkedin: number;
  };
  popular?: {
    total: number;
    last_24h: number;
  };
}

export interface MentionsFeed {
  mentions: Post[];
  total: number;
  page: number;
  page_size: number;
  by_platform: { x: number; linkedin: number; reddit?: number };
}

export interface PopularPost extends Post {
  views?: number;
  flagged_at: string;
  triggered_by: string;
  metric_value: number;
}

export interface PopularFeed {
  posts: PopularPost[];
  total: number;
  page: number;
  page_size: number;
  by_platform: { x: number; slack: number };
}

export interface PaginatedHistory {
  items: HistoryEntry[];
  total: number;
  page: number;
  page_size: number;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

function normalizeQueryResult(raw: Record<string, unknown>): QueryResult {
  const posts = (raw.posts ?? raw.results ?? []) as Post[];
  return {
    posts,
    count: (raw.count as number) ?? posts.length,
    latency_ms: raw.latency_ms as number | undefined,
    summary: raw.summary as string | undefined,
  };
}

export async function querySemantic(
  q: string,
  filters?: Record<string, unknown>
): Promise<QueryResult> {
  const raw = await apiFetch<Record<string, unknown>>("/api/query/semantic", {
    method: "POST",
    body: JSON.stringify({ query: q, filters }),
  });
  return normalizeQueryResult(raw);
}

export async function querySemanticWithSummary(
  q: string,
  filters?: Record<string, unknown>
): Promise<QueryResult> {
  const raw = await apiFetch<Record<string, unknown>>("/api/query/semantic-with-summary", {
    method: "POST",
    body: JSON.stringify({ query: q, filters }),
  });
  return normalizeQueryResult(raw);
}

export async function getStats(): Promise<Stats> {
  const raw = await apiFetch<Record<string, unknown>>("/api/stats");
  // Normalize backend key variations
  const byPlatform = (raw.posts_by_platform ?? raw.by_platform ?? {}) as { x?: number; slack?: number };
  // Pull last_ingestion from the stats response, or synthesize from pipelines if missing
  let lastIngestion = (raw.last_ingestion as Stats["last_ingestion"]) ?? [];
  if (!lastIngestion.length && raw.pipelines) {
    const pipelines = raw.pipelines as Record<string, { status: string; last_run_at: string | null }>;
    lastIngestion = Object.entries(pipelines).map(([source, p]) => ({
      source,
      status: p.status,
      last_run_at: p.last_run_at ?? "",
    }));
  }
  return {
    total_posts: raw.total_posts as number,
    posts_by_platform: { x: byPlatform.x ?? 0, slack: byPlatform.slack ?? 0 },
    last_ingestion: lastIngestion,
    active_projects: raw.active_projects as number | undefined,
  };
}

export async function getHistory(
  page = 1,
  pageSize = 20
): Promise<PaginatedHistory> {
  const raw = await apiFetch<Record<string, unknown>>(
    `/api/query/history?page=${page}&page_size=${pageSize}`
  );
  const items = (raw.items ?? raw.results ?? []) as HistoryEntry[];
  return {
    items,
    total: (raw.total as number) ?? items.length,
    page: (raw.page as number) ?? page,
    page_size: (raw.page_size as number) ?? pageSize,
  };
}

export async function getHistoryDetail(id: string): Promise<HistoryDetail> {
  return apiFetch(`/api/query/history/${id}`);
}

export async function exportHistoryMarkdown(id: string): Promise<string> {
  const res = await fetch(`${API_URL}/api/query/history/${id}/export`);
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  return res.text();
}

export async function getMentions(params: {
  platform?: "x" | "linkedin" | "reddit" | "all";
  days?: number;
  page?: number;
  page_size?: number;
} = {}): Promise<MentionsFeed> {
  const { platform = "all", days = 7, page = 1, page_size = 20 } = params;
  const qs = new URLSearchParams({
    days: String(days),
    page: String(page),
    page_size: String(page_size),
  });
  if (platform && platform !== "all") qs.set("platform", platform);
  const raw = await apiFetch<Record<string, unknown>>(`/api/mentions?${qs.toString()}`);
  return {
    mentions: (raw.mentions ?? raw.posts ?? []) as Post[],
    total: (raw.total as number) ?? 0,
    page: (raw.page as number) ?? page,
    page_size: (raw.page_size as number) ?? page_size,
    by_platform: (raw.by_platform as { x: number; linkedin: number }) ?? { x: 0, linkedin: 0 },
  };
}

export async function getPopularPosts(params: {
  platform?: "x" | "slack" | "all";
  days?: number;
  page?: number;
  page_size?: number;
} = {}): Promise<PopularFeed> {
  const { platform = "all", days = 30, page = 1, page_size = 20 } = params;
  const qs = new URLSearchParams({
    days: String(days),
    page: String(page),
    page_size: String(page_size),
  });
  if (platform && platform !== "all") qs.set("platform", platform);
  return apiFetch<PopularFeed>(`/api/popular?${qs.toString()}`);
}

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatAbsoluteTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

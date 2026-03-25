"use client";

import { type Post, formatRelativeTime } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface ResultCardProps {
  post: Post;
  index?: number;
}

const platformConfig = {
  x: {
    label: "X",
    color: "text-sky-400",
    bg: "bg-sky-400/10 border-sky-400/20",
  },
  slack: {
    label: "Slack",
    color: "text-emerald-400",
    bg: "bg-emerald-400/10 border-emerald-400/20",
  },
};

export function ResultCard({ post, index = 0 }: ResultCardProps) {
  const platform = platformConfig[post.platform] ?? platformConfig.slack;

  return (
    <div
      className="animate-card group border border-border rounded-lg p-4 bg-card hover:border-primary/30 hover:bg-card/80 transition-all duration-150 cursor-default"
      style={{ animationDelay: `${Math.min(index * 50, 500)}ms` }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded border ${platform.bg} ${platform.color}`}>
            {platform.label}
          </span>
          {post.channel && (
            <span className="text-xs text-muted-foreground font-mono">
              #{post.channel}
            </span>
          )}
          <span className="text-sm font-medium text-foreground">@{post.author}</span>
        </div>
        <span className="text-xs text-muted-foreground font-mono whitespace-nowrap shrink-0">
          {formatRelativeTime(post.published_at)}
        </span>
      </div>

      {/* Content */}
      <p className="text-sm text-foreground/90 leading-relaxed font-mono whitespace-pre-wrap break-words">
        {post.content}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/50">
        <div className="flex items-center gap-3">
          {post.platform === "x" && (
            <>
              {post.likes !== undefined && (
                <span className="text-xs text-muted-foreground font-mono">
                  ♥ {post.likes.toLocaleString()}
                </span>
              )}
              {post.retweets !== undefined && (
                <span className="text-xs text-muted-foreground font-mono">
                  ↩ {post.retweets.toLocaleString()}
                </span>
              )}
              {post.replies !== undefined && (
                <span className="text-xs text-muted-foreground font-mono">
                  💬 {post.replies.toLocaleString()}
                </span>
              )}
            </>
          )}
          {post.score !== undefined && (
            <span className="text-xs text-primary/70 font-mono">
              score: {post.score.toFixed(3)}
            </span>
          )}
        </div>
        <a
          href={post.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:text-primary/80 font-mono transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          view source →
        </a>
      </div>
    </div>
  );
}

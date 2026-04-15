"use client";

import { useState } from "react";
import { type Post, formatRelativeTime } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ResultCardProps {
  post: Post;
  index?: number;
}

const platformConfig: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  x: {
    label: "X",
    dot: "bg-gray-800",
    bg: "bg-gray-100",
    text: "text-gray-800",
  },
  slack: {
    label: "Slack",
    dot: "bg-violet-500",
    bg: "bg-violet-50",
    text: "text-violet-700",
  },
  reddit: {
    label: "Reddit",
    dot: "bg-orange-500",
    bg: "bg-orange-50",
    text: "text-orange-700",
  },
  linkedin: {
    label: "LinkedIn",
    dot: "bg-blue-600",
    bg: "bg-blue-50",
    text: "text-blue-700",
  },
};

const TRUNCATE_AT = 280;

export function ResultCard({ post, index = 0 }: ResultCardProps) {
  const [expanded, setExpanded] = useState(false);
  const platform = platformConfig[post.platform] ?? platformConfig.slack;
  const isLong = post.content.length > TRUNCATE_AT;
  const displayContent =
    isLong && !expanded ? post.content.slice(0, TRUNCATE_AT).trimEnd() + "…" : post.content;

  return (
    <div
      className="animate-card group relative bg-white border border-border rounded-2xl p-4 hover:border-primary/30 hover:shadow-md hover:shadow-primary/5 transition-all duration-200 cursor-default"
      style={{ animationDelay: `${Math.min(index * 35, 350)}ms` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded-full", platform.bg, platform.text)}>
            <span className={cn("w-1.5 h-1.5 rounded-full", platform.dot)} />
            {platform.label}
          </span>
          {post.channel && (
            <span className="text-xs text-muted-foreground font-medium">#{post.channel}</span>
          )}
          <span className="text-sm font-medium text-foreground">@{post.author}</span>
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
          {formatRelativeTime(post.published_at)}
        </span>
      </div>

      {/* Content */}
      <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap break-words">
        {displayContent}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-primary hover:text-primary/70 font-medium transition-colors"
        >
          {expanded ? "Show less ↑" : "Show more ↓"}
        </button>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/60">
        <div className="flex items-center gap-3">
          {post.platform === "x" && (
            <>
              {post.likes !== undefined && post.likes > 0 && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <span>♥</span> {post.likes.toLocaleString()}
                </span>
              )}
              {post.retweets !== undefined && post.retweets > 0 && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <span>↩</span> {post.retweets.toLocaleString()}
                </span>
              )}
            </>
          )}
          {post.platform === "reddit" && (
            <>
              {post.likes !== undefined && post.likes > 0 && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <span>⬆</span> {post.likes.toLocaleString()}
                </span>
              )}
              {post.replies !== undefined && post.replies > 0 && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <span>💬</span> {post.replies.toLocaleString()}
                </span>
              )}
            </>
          )}
          {post.score !== undefined && (
            <span className="text-xs font-medium text-primary/70 bg-accent px-1.5 py-0.5 rounded-full">
              {Math.round(post.score * 100)}%
            </span>
          )}
        </div>
        <a
          href={post.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:text-primary/70 font-semibold transition-colors flex items-center gap-1 opacity-0 group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          Open ↗
        </a>
      </div>
    </div>
  );
}

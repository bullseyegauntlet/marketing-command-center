"use client";

import { useState } from "react";
import { type Post, formatRelativeTime } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ResultCardProps {
  post: Post;
  index?: number;
}

const platformConfig: Record<string, { label: string; badgeClass: string }> = {
  x: {
    label: "X",
    badgeClass: "bg-gray-900 text-white",
  },
  slack: {
    label: "Slack",
    badgeClass: "bg-purple-600 text-white",
  },
  reddit: {
    label: "Reddit",
    badgeClass: "bg-orange-600 text-white",
  },
  linkedin: {
    label: "LinkedIn",
    badgeClass: "bg-blue-700 text-white",
  },
};

const TRUNCATE_AT = 280;

export function ResultCard({ post, index = 0 }: ResultCardProps) {
  const [expanded, setExpanded] = useState(false);
  const platform = platformConfig[post.platform] ?? platformConfig.slack;
  const isLong = post.content.length > TRUNCATE_AT;
  const displayContent = isLong && !expanded
    ? post.content.slice(0, TRUNCATE_AT).trimEnd() + "…"
    : post.content;

  return (
    <div
      className="animate-card border border-border rounded-xl p-4 bg-white hover:shadow-sm hover:border-[#c5cae9] transition-all duration-150"
      style={{ animationDelay: `${Math.min(index * 40, 400)}ms` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full", platform.badgeClass)}>
            {platform.label}
          </span>
          {post.channel && (
            <span className="text-xs text-muted-foreground">
              #{post.channel}
            </span>
          )}
          <span className="text-sm font-medium text-foreground">@{post.author}</span>
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
          {formatRelativeTime(post.published_at)}
        </span>
      </div>

      {/* Content */}
      <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap break-words">
        {displayContent}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-primary hover:text-primary/80 font-medium transition-colors"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
        <div className="flex items-center gap-3">
          {post.platform === "x" && (
            <>
              {post.likes !== undefined && (
                <span className="text-xs text-muted-foreground">♥ {post.likes.toLocaleString()}</span>
              )}
              {post.retweets !== undefined && (
                <span className="text-xs text-muted-foreground">↩ {post.retweets.toLocaleString()}</span>
              )}
            </>
          )}
          {post.score !== undefined && (
            <span className="text-xs text-muted-foreground">
              {Math.round(post.score * 100)}% match
            </span>
          )}
        </div>
        <a
          href={post.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:underline font-medium"
          onClick={(e) => e.stopPropagation()}
        >
          View →
        </a>
      </div>
    </div>
  );
}
